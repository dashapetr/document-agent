# Building an Amazon Bedrock Agent for Document Processing 

Welcome to building document assistant using Amazon Bedrock Agents.

![Agent Architecture Diagram](/images/document-processing-bedrock-agent.png)

## What Document Processing Agent Can Do

### Basic tasks:

1. Summarize: given a document, return its summary
2. Retrieve info: question-answer based on a document
3. Analyze data: simple quantitative data analysis
4. Generate plot: based on the document data
5. Make changes: adjust content formats

![Alter dates](/images/alter-dates.png)

![Answer questions](/images/question-answering.png)

### Advanced tasks:

1. AWS services: integrate with various services, ex. Textract, Translate, etc.
2. Complex pipelines: accomplish multi-step changes and tasks
3. Knowledge bases: RAG-based search across documents

![Complex task](/images/complex-task.png)

![Query KB](/images/knowledge-base.png)

## What is Bedrock Agent?

Agents for Amazon Bedrock helps you accelerate generative artificial intelligence (AI) application development by orchestrating multistep tasks.
They can make different API calls. 
Agents extend FMs to understand user requests, break down complex tasks into multiple steps, carry on a conversation to collect additional information, and take actions to fulfill the request.

- [How Agents for Amazon Bedrock works](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-how.html)

## Let's build!

### :one: Step 1: Create Bedrock agent

**Prerequisites**: we will use `Amazon Nova Lite v1` as model, make sure that you [have access to it in your account](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html).

1. Go to [Bedrock console](https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/overview), select `Agents` in the left navigation panel, then click on the `Create Agent` button
2. Provide `agent-for-document-processing` as Agent name, provide a description (optional). Click on the `Create` button.

![Create agent](/images/create-agent.png)

3. You can now open the `Agent builder`, the place where you can access and edit the overall configuration of an agent. 
We will select `Amazon Nova Lite v1` as model ([Pricing](https://aws.amazon.com/bedrock/pricing/)); Paste the following text as Instructions for the Agent:
```markdown
You are a document processing agent skilled at extracting key information from documents, translating content, summarizing text, and manipulating data formats. 
Your tasks include finding key points in documents, locating documents in Amazon S3 and querying them, altering date formats in Excel files, summarizing long documents, 
parsing PDFs with Amazon Textract and saving results to Amazon DynamoDB, and translating documents to required languages. 
Use your capabilities to assist users with efficiently processing and analyzing document data.
```
4. In Additional settings, select `Enabled` for Code Interpreter

![Edit agent](/images/edit-agent-builder.png)

Leave all the rest as default. Then, choose `Save and Exit` to update the configuration of the agent.
In the test chat, click `Prepare` to update the agent.

Now, you can test the agent! 
 
Append `sample-company-report.docx` (can be found inside `example-documents`) and ask:
```markdown
what are the next crucial action items?
```
Append `sales_data.xlsx` (can be found inside `example-documents`) TO THE CODE EDITOR and ask:
```markdown
alter sales dates to american format: instead of using YYYY-MM-DD, use YYYY-DD-MM, output updated file
```

### :two: Step 2: Add action group

Action group config

Lambda function

S3 

DynamoDB

### :three: Step 3: Add knowledge base

S3 files 

Knowledge base

## Possible errors

#### 1. Incorrectly formatted overridden prompt: 

![Incorrect prompt](/images/incorrect-prompt.png)

To resolve: **Enable Code Editor**

#### 2. Access denied while invoking Lambda function:

![Access denied](/images/access-denied.png)

To resolve: **[add a resource-based policy statement on the Lambda](https://repost.aws/questions/QUXk7QWdzGTh-c5MIWch9NNQ/error-when-bedrock-agent-invoke-lambda)**

#### 3. Error processing the Lambda response: 

![lambda response](/images/lambda-response-error.png)

To resolve: **[Check Lambda output format](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-lambda.html#agents-lambda-response)**