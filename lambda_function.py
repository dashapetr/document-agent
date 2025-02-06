import boto3
import os
from collections import defaultdict
from io import BytesIO

dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')
textract = boto3.client('textract')
translate = boto3.client('translate')


def get_kv_relationship(key_map, value_map, block_map):
    kvs = defaultdict(list)
    for block_id, key_block in key_map.items():
        value_block = find_value_block(key_block, value_map)
        key = get_text(key_block, block_map)
        val = get_text(value_block, block_map)
        kvs[key].append(val)
    return kvs


def find_value_block(key_block, value_map):
    for relationship in key_block['Relationships']:
        if relationship['Type'] == 'VALUE':
            for value_id in relationship['Ids']:
                value_block = value_map[value_id]
    return value_block


def get_text(result, blocks_map):
    text = ''
    if 'Relationships' in result:
        for relationship in result['Relationships']:
            if relationship['Type'] == 'CHILD':
                for child_id in relationship['Ids']:
                    word = blocks_map[child_id]
                    if word['BlockType'] == 'WORD':
                        text += word['Text'] + ' '
                    if word['BlockType'] == 'SELECTION_ELEMENT':
                        if word['SelectionStatus'] == 'SELECTED':
                            text += 'X '

    return text


def extract_text_from_pdf(s3_path, table_name):
    """Retrieve PDF from S3, parse it as a table using Amazon Textract, and save structured data to DynamoDB."""
    bucket, key = s3_path.replace("s3://", "").split('/', 1)
    local_file = f"/tmp/{key.split('/')[-1]}"

    # Extract document name from S3 path (removing extensions)
    document_name = os.path.splitext(os.path.basename(key))[0]

    # Download the file from S3
    s3.download_file(bucket, key, local_file)

    # Open file and send to Textract for text extraction
    with open(local_file, 'rb') as document:
        response = textract.analyze_document(
            Document={'Bytes': document.read()},
            FeatureTypes=['FORMS']
        )

    blocks = response['Blocks']

    key_map = {}
    value_map = {}
    block_map = {}
    for block in blocks:
        block_id = block['Id']
        block_map[block_id] = block
        if block['BlockType'] == "KEY_VALUE_SET":
            if 'KEY' in block['EntityTypes']:
                key_map[block_id] = block
            else:
                value_map[block_id] = block

    kvs = get_kv_relationship(key_map, value_map, block_map)

    print(kvs)

    # Remove temporary file
    os.remove(local_file)

    # Save structured table data to DynamoDB
    table = dynamodb.Table(table_name)
    table.put_item(
        Item={
            "doc-name": document_name,  # Using extracted document name as partition key
            "document_path": s3_path,
            "tables": kvs  # Save table as a nested attribute
        }
    )

    return {"status": "success", "message": f"Table extracted and saved for {document_name}."}


def translate_document(document_name, table_name):
    """Retrieve a PDF document by name, check its language, translate if needed, save and update DB."""
    table = dynamodb.Table(table_name)
    response = table.get_item(Key={"doc-name": document_name})

    if 'Item' not in response:
        return {"error": "Document not found."}

    item = response['Item']
    language = item.get("language", "en")
    s3_path = item["document_path"]

    if language != 'en':
        # Extract bucket and key from S3 path
        bucket, key = s3_path.replace("s3://", "").split('/', 1)

        # Download PDF file from S3
        pdf_stream = s3.get_object(Bucket=bucket, Key=key)['Body'].read()

        # Use Textract to extract text from the PDF
        response = textract.start_document_text_detection(
            DocumentLocation={'S3Object': {'Bucket': bucket, 'Name': key}})

        # Wait for Textract to process the document (this can take some time)
        job_id = response['JobId']
        result = textract.get_document_text_detection(JobId=job_id)

        # Gather text from the response
        text = ""
        for item in result['Blocks']:
            if item['BlockType'] == 'LINE':
                text += item['Text'] + "\n"

        # Translate text
        translated_text = translate.translate_text(Text=text, SourceLanguageCode=language, TargetLanguageCode='en')[
            "TranslatedText"]

        # Write translated text to a .txt file
        translated_txt_stream = BytesIO()
        translated_txt_stream.write(translated_text.encode('utf-8'))
        translated_txt_stream.seek(0)

        # Upload translated .txt file to S3
        translated_key = f"translated/{key.replace('.pdf', '_translated.txt')}"
        s3.put_object(Bucket=bucket, Key=translated_key, Body=translated_txt_stream.getvalue())

        # Update DynamoDB with translated document path
        table.update_item(
            Key={"doc-name": document_name},
            UpdateExpression="SET translated_document_path = :tp",
            ExpressionAttributeValues={":tp": f"s3://{bucket}/{translated_key}"}
        )

    return {"status": "success", "message": "Document translated and updated."}


def lambda_handler(event, context):
    print(event)
    function = event['function']
    parameters = event.get('parameters', [])

    if function == 'extract_text_from_pdf':
        s3_path = next(item["value"] for item in parameters if item["name"] == "s3_path")
        table_name = next(item["value"] for item in parameters if item["name"] == "table_name")
        body = extract_text_from_pdf(s3_path, table_name)
    elif function == 'translate_document':
        document_name = next(item["value"] for item in parameters if item["name"] == "document_name")
        table_name = next(item["value"] for item in parameters if item["name"] == "table_name")
        body = translate_document(document_name, table_name)
    else:
        body = {"error": f"{function} is not a valid function."}

    return {"response": body}
