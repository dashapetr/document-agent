import boto3
import os
import time
from collections import defaultdict
from typing import Dict, Any, List

# Initialize AWS Clients
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
textract = boto3.client("textract")
translate = boto3.client("translate")


def get_kv_relationship(key_map: Dict[str, Any], value_map: Dict[str, Any], block_map: Dict[str, Any]) -> Dict[
    str, List[str]]:
    """Extracts key-value relationships from Textract response blocks."""
    kvs = defaultdict(list)
    for block_id, key_block in key_map.items():
        value_block = find_value_block(key_block, value_map)
        key = get_text(key_block, block_map)
        val = get_text(value_block, block_map)
        kvs[key].append(val)
    return kvs


def find_value_block(key_block: Dict[str, Any], value_map: Dict[str, Any]) -> Dict[str, Any]:
    """Finds the corresponding value block for a given key block."""
    for relationship in key_block.get("Relationships", []):
        if relationship["Type"] == "VALUE":
            for value_id in relationship["Ids"]:
                return value_map[value_id]
    return {}


def get_text(result: Dict[str, Any], blocks_map: Dict[str, Any]) -> str:
    """Extracts text from a Textract block."""
    text = ""
    for relationship in result.get("Relationships", []):
        if relationship["Type"] == "CHILD":
            for child_id in relationship["Ids"]:
                word = blocks_map[child_id]
                if word["BlockType"] == "WORD":
                    text += word["Text"] + " "
                elif word["BlockType"] == "SELECTION_ELEMENT" and word.get("SelectionStatus") == "SELECTED":
                    text += "X "
    return text.strip()


def extract_text_from_pdf(s3_path: str, table_name: str) -> Dict[str, str]:
    """Retrieves a PDF from S3, extracts text using Amazon Textract, and saves structured data to DynamoDB."""
    bucket, key = s3_path.replace("s3://", "").split("/", 1)
    document_name = os.path.splitext(os.path.basename(key))[0]

    # Download the file from S3
    local_file = f"/tmp/{document_name}.pdf"
    s3.download_file(bucket, key, local_file)

    # Process with Textract
    with open(local_file, "rb") as document:
        response = textract.analyze_document(Document={"Bytes": document.read()}, FeatureTypes=["FORMS"])

    # Organize blocks
    key_map, value_map, block_map = {}, {}, {}
    for block in response.get("Blocks", []):
        block_id = block["Id"]
        block_map[block_id] = block
        if block["BlockType"] == "KEY_VALUE_SET":
            (key_map if "KEY" in block.get("EntityTypes", []) else value_map)[block_id] = block

    kvs = get_kv_relationship(key_map, value_map, block_map)
    os.remove(local_file)

    # Save extracted data to DynamoDB
    table = dynamodb.Table(table_name)
    table.put_item(Item={"doc-name": document_name, "document_path": s3_path, "tables": kvs})

    return {"status": "success", "message": f"Table extracted and saved for {document_name}."}


def translate_document(document_name: str, table_name: str) -> Dict[str, str]:
    """Retrieves a document from DynamoDB, extracts and translates its text if necessary, and stores the translated version in S3."""
    table = dynamodb.Table(table_name)
    response = table.get_item(Key={"doc-name": document_name})

    if "Item" not in response:
        return {"error": "Document not found."}

    item = response["Item"]
    language = item.get("language", "en")
    s3_path = item["document_path"]

    if language != "en":
        bucket, key = s3_path.replace("s3://", "").split("/", 1)

        # Start Textract job
        job_response = textract.start_document_text_detection(
            DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}})
        job_id = job_response["JobId"]

        # Wait for job to complete
        while True:
            job_status = textract.get_document_text_detection(JobId=job_id)
            if job_status["JobStatus"] == "SUCCEEDED":
                break
            time.sleep(5)

        # Extract text
        extracted_text = "\n".join(
            [block["Text"] for block in job_status.get("Blocks", []) if block["BlockType"] == "LINE"])

        # Translate text
        translated_text = \
        translate.translate_text(Text=extracted_text, SourceLanguageCode=language, TargetLanguageCode="en")[
            "TranslatedText"]

        # Save translation as a .txt file
        translated_key = f"translated/{key.replace('.pdf', '_translated.txt')}"
        s3.put_object(Bucket=bucket, Key=translated_key, Body=translated_text.encode("utf-8"))

        # Update DynamoDB
        table.update_item(
            Key={"doc-name": document_name},
            UpdateExpression="SET translated_document_path = :tp",
            ExpressionAttributeValues={":tp": f"s3://{bucket}/{translated_key}"}
        )

    return {"status": "success", "message": "Document translated and updated."}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler that routes events to the appropriate function."""
    function = event.get("function")
    parameters = {param["name"]: param["value"] for param in event.get("parameters", [])}

    if function == "extract_text_from_pdf":
        body = extract_text_from_pdf(parameters["s3_path"], parameters["table_name"])
    elif function == "translate_document":
        body = translate_document(parameters["document_name"], parameters["table_name"])
    else:
        body = {"error": f"{function} is not a valid function."}

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event["actionGroup"],
            "function": function,
            "functionResponse": {"responseBody": {"TEXT": {"body": str(body)}}}
        },
        "sessionAttributes": event.get("sessionAttributes", {}),
        "promptSessionAttributes": event.get("promptSessionAttributes", {})
    }
