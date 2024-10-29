import streamlit as st
import boto3
import json
import pandas as pd
from io import BytesIO

# Configure AWS Lambda client using Streamlit secrets
@st.cache_resource
def get_lambda_client():
    return boto3.client(
        'lambda',
        aws_access_key_id=st.secrets["aws_credentials"]["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["aws_credentials"]["AWS_SECRET_ACCESS_KEY"],
        region_name=st.secrets["aws_credentials"]["AWS_REGION"]
    )

# Lambda function name
LAMBDA_FUNCTION_NAME = 'genaipocpdf'

def flatten_dict(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

# Configure page settings
st.set_page_config(
    page_title="PDF Processor",
    page_icon="📄",
    layout="wide"
)

# Initialize Lambda client
lambda_client = get_lambda_client()

st.title('PDF Processor')

if st.button('Process PDF'):
    try:
        # Prepare payload for Lambda function
        payload = {
            "file_name": "Fuji_pdfFile.pdf"
        }

        with st.spinner('Processing PDF...'):
            # Invoke Lambda function
            response = lambda_client.invoke(
                FunctionName=LAMBDA_FUNCTION_NAME,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )

            # Read and parse the Lambda function response
            response_payload = json.loads(response['Payload'].read().decode('utf-8'))
            
            # Check if the execution was successful
            if response['StatusCode'] == 200:
                st.success("Lambda function executed successfully")
                
                # Parse the body of the Lambda function result
                body = json.loads(response_payload.get('body', '{}'))
                
                # Flatten the nested dictionary
                flattened_data = flatten_dict(body)
                
                # Create a DataFrame
                df = pd.DataFrame([flattened_data])
                
                # Display the DataFrame
                st.subheader("Extracted Information:")
                st.dataframe(df)
                
                # Create a download button for Excel file
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Sheet1', index=False)
                buffer.seek(0)
                
                st.download_button(
                    label="📥 Download Excel file",
                    data=buffer,
                    file_name="extracted_info.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.error(f"Lambda function execution failed with status code: {response['StatusCode']}")
                st.error(f"Error message: {response_payload.get('errorMessage', 'Unknown error')}")

    except Exception as e:
        st.error(f"Error executing Lambda function: {str(e)}")
        st.error(f"Error details: {type(e).__name__}")

st.text("Click 'Process PDF' to start processing Fuji_pdfFile.pdf")
