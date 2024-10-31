import streamlit as st
import boto3
import json
import pandas as pd
from io import BytesIO
from botocore.exceptions import ClientError

# Initialize session state if not already done
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None

# Configure page settings
st.set_page_config(
    page_title="PDF Processor",
    page_icon="📄",
    layout="wide"
)

@st.cache_resource
def get_aws_clients():
    """Create AWS clients with error handling"""
    try:
        # Clean up credentials by removing any whitespace
        credentials = st.secrets["aws_credentials"]
        # Create Lambda client
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=credentials["AWS_ACCESS_KEY_ID"].strip(),
            aws_secret_access_key=credentials["AWS_SECRET_ACCESS_KEY"].strip(),
            region_name=credentials["AWS_REGION"].strip()
        )
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=credentials["AWS_ACCESS_KEY_ID"].strip(),
            aws_secret_access_key=credentials["AWS_SECRET_ACCESS_KEY"].strip(),
            region_name=credentials["AWS_REGION"].strip()
        )
        return lambda_client, s3_client
            
    except Exception as e:
        st.error(f"Error creating AWS clients: {str(e)}")
        return None, None

def flatten_dict(d, parent_key='', sep='_'):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def create_excel_download_link(df):
    """Create an Excel file in memory and return it as a binary object"""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Sheet1', index=False)
    buffer.seek(0)
    return buffer

# Lambda function name and S3 bucket
LAMBDA_FUNCTION_NAME = 'genaipocpdf'
S3_BUCKET_NAME = st.secrets["aws_credentials"]["S3_BUCKET_NAME"]

st.title('PDF Processor')

# Initialize AWS clients
lambda_client, s3_client = get_aws_clients()

if lambda_client is not None and s3_client is not None:
    # File uploader
    uploaded_file = st.file_uploader("Choose a PDF file", type=['pdf'])
    
    if uploaded_file is not None:
        st.write("File details:")
        st.write(f"- File name: {uploaded_file.name}")
        st.write(f"- File size: {uploaded_file.size} bytes")
        
        if st.button('Process PDF'):
            try:
                # First upload to S3
                with st.spinner('Uploading file to S3...'):
                    try:
                        s3_client.upload_fileobj(
                            uploaded_file,
                            S3_BUCKET_NAME,
                            uploaded_file.name
                        )
                        st.success(f"File uploaded successfully to S3: {uploaded_file.name}")
                        
                        # Prepare payload for Lambda function
                        payload = {
                            "file_name": uploaded_file.name
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
                                
                                # Create a DataFrame and store in session state
                                st.session_state.processed_data = pd.DataFrame([flattened_data])
                                
                            else:
                                st.error(f"Lambda function execution failed with status code: {response['StatusCode']}")
                                st.error(f"Error message: {response_payload.get('errorMessage', 'Unknown error')}")
                    
                    except ClientError as e:
                        st.error(f"Error uploading to S3: {str(e)}")
                        return

            except Exception as e:
                st.error(f"Error processing PDF: {str(e)}")
                st.error(f"Error details: {type(e).__name__}")

    # Display results if available
    if st.session_state.processed_data is not None:
        # Display the DataFrame
        st.subheader("Extracted Information:")
        st.dataframe(st.session_state.processed_data)
        
        # Create download button
        excel_buffer = create_excel_download_link(st.session_state.processed_data)
        
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.download_button(
                label="📥 Download Excel file",
                data=excel_buffer,
                file_name="extracted_info.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key='download_button'
            )

else:
    st.error("Unable to initialize AWS clients. Please check your credentials.")

st.text("Upload a PDF file and click 'Process PDF' to start processing.")
