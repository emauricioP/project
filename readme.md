# PDF Processor Streamlit App

This Streamlit application processes PDF files using AWS Lambda and displays the extracted information.

## Setup Instructions

1. The app is deployed on Streamlit Cloud
2. Requires AWS credentials configured in Streamlit Cloud secrets
3. Uses AWS Lambda function 'genaipocpdf'

## Features

- Process PDF files stored in S3
- Display extracted information in a table
- Download results as Excel file

## Configuration

The application requires the following secrets to be configured in Streamlit Cloud:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_REGION
