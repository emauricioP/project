import streamlit as st
import boto3
import json
import pandas as pd
from io import BytesIO
from botocore.exceptions import ClientError

# Configure page settings first
st.set_page_config(
    page_title="PDF Processor",
    page_icon="📄",
    layout="wide"
)

# Initialize session state
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None

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

# Display the main title
st.title('PDF Processor')

# Add some space
st.write("")

# Create a container for the upload section
with st.container():
    st.markdown("### Upload PDF File")
    st.markdown("Please select a PDF file to process:")
    
    # File uploader
    uploaded_file = st.file_uploader("Choose a PDF file", type=['pdf'])

# Initialize AWS clients
lambda_client, s3_client = get_aws_clients()

if lambda_client is None or s3_client is None:
    st.error("Unable to initialize AWS clients. Please check your credentials.")
else:
    try:
        # Get S3 bucket name from secrets
        S3_BUCKET_NAME = st.secrets["aws_credentials"]["S3_BUCKET_NAME"]
        
        # If a file is uploaded, show file details and process button
        if uploaded_file is not None:
            st.success("File uploaded successfully!")
            
            # Create columns for file details
            col1, col2 = st.columns(2)
            with col1:
                st.write("File Details:")
                st.write(f"- Name: {uploaded_file.name}")
                st.write(f"- Size: {uploaded_file.size} bytes")
                st.write(f"- Type: {uploaded_file.type}")
            
            # Process button
            if st.button('Process PDF', key='process_button'):
                try:
                    # Upload to S3
                    with st.spinner('Uploading file to S3...'):
                        s3_client.upload_fileobj(
                            uploaded_file,
                            S3_BUCKET_NAME,
                            uploaded_file.name
                        )
                        st.success(f"File uploaded successfully to S3: {uploaded_file.name}")
                    
                    # Process with Lambda
                    with st.spinner('Processing PDF...'):
                        # Prepare payload
                        payload = {
                            "file_name": uploaded_file.name
                        }
                        
                        # Invoke Lambda
                        response = lambda_client.invoke(
                            FunctionName='genaipocpdf',
                            InvocationType='RequestResponse',
                            Payload=json.dumps(payload)
                        )
                        
                        # Process response
                        response_payload = json.loads(response['Payload'].read().decode('utf-8'))
                        
                        if response['StatusCode'] == 200:
                            st.success("PDF processed successfully!")
                            
                            # Parse and store results
                            body = json.loads(response_payload.get('body', '{}'))
                            flattened_data = flatten_dict(body)
                            st.session_state.processed_data = pd.DataFrame([flattened_data])
                        else:
                            st.error("Processing failed!")
                            st.error(response_payload.get('errorMessage', 'Unknown error'))
                
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        # Display results if available
        if st.session_state.processed_data is not None:
            st.markdown("### Results")
            st.dataframe(st.session_state.processed_data)
            
            # Download button
            excel_buffer = create_excel_download_link(st.session_state.processed_data)
            st.download_button(
                label="📥 Download Excel file",
                data=excel_buffer,
                file_name="extracted_info.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key='download_button'
            )
    
    except Exception as e:
        st.error(f"Configuration error: {str(e)}")

# Add some space at the bottom
st.write("")
st.markdown("---")
st.markdown("*Upload a PDF file and click 'Process PDF' to start processing.*")
