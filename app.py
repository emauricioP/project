import streamlit as st
import boto3
import json
import pandas as pd
from io import BytesIO
from botocore.exceptions import ClientError
import time

# Configure page settings first
st.set_page_config(
    page_title="PDF Processor",
    page_icon="📄",
    layout="wide"
)

# Initialize session state
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = []
if 'selected_file_index' not in st.session_state:
    st.session_state.selected_file_index = 0
if 'files_to_process' not in st.session_state:
    st.session_state.files_to_process = []

def get_aws_clients():
    """Create AWS clients with error handling"""
    try:
        credentials = st.secrets["aws_credentials"]
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=credentials["AWS_ACCESS_KEY_ID"].strip(),
            aws_secret_access_key=credentials["AWS_SECRET_ACCESS_KEY"].strip(),
            region_name=credentials["AWS_REGION"].strip()
        )
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

def process_single_file(s3_client, lambda_client, file, bucket_name, status_container):
    try:
        # Upload to S3
        s3_client.upload_fileobj(
            file,
            bucket_name,
            file.name
        )
        status_container.success(f"✅ Uploaded {file.name} to S3")
        
        # Process with Lambda
        payload = {
            "file_name": file.name
        }
        
        status_container.info("Processing with Lambda function...")
        response = lambda_client.invoke(
            FunctionName='genaipocpdf',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        response_payload = json.loads(response['Payload'].read().decode('utf-8'))
        
        if response['StatusCode'] == 200:
            body = json.loads(response_payload.get('body', '{}'))
            flattened_data = flatten_dict(body)
            flattened_data['source_file'] = file.name
            status_container.success(f"✅ Successfully processed {file.name}")
            return flattened_data
        else:
            status_container.error(f"❌ Error processing {file.name}: {response_payload.get('errorMessage', 'Unknown error')}")
            return None
            
    except Exception as e:
        status_container.error(f"❌ Error with {file.name}: {str(e)}")
        return None

# Display the main title
st.title('PDF Processor')

# Create a container for the upload section
with st.container():
    st.markdown("### Upload PDF Files")
    st.markdown("Please select PDF files to process:")
    
    # Multiple file uploader
    uploaded_files = st.file_uploader("Choose PDF files", type=['pdf'], accept_multiple_files=True)

    if uploaded_files:
        st.session_state.files_to_process = uploaded_files
        st.success(f"{len(uploaded_files)} files ready for processing")

# Initialize AWS clients
lambda_client, s3_client = get_aws_clients()

if lambda_client is None or s3_client is None:
    st.error("Unable to initialize AWS clients. Please check your credentials.")
else:
    try:
        S3_BUCKET_NAME = st.secrets["aws_credentials"]["S3_BUCKET_NAME"]
        
        # If files are uploaded, show the current file to process
        if st.session_state.files_to_process:
            st.markdown("### Files to Process")
            
            # Display file list with status
            for idx, file in enumerate(st.session_state.files_to_process):
                status = "✅" if idx < st.session_state.selected_file_index else "⏳"
                st.text(f"{status} {file.name}")
            
            # Get current file
            current_file = st.session_state.files_to_process[st.session_state.selected_file_index]
            
            st.markdown(f"### Currently Processing: {current_file.name}")
            status_container = st.empty()
            
            # Process button for current file
            if st.button(f'Process {current_file.name}', key='process_button'):
                result = process_single_file(s3_client, lambda_client, current_file, 
                                          S3_BUCKET_NAME, status_container)
                
                if result:
                    st.session_state.processed_data.append(result)
                    st.session_state.selected_file_index += 1
                    
                    if st.session_state.selected_file_index >= len(st.session_state.files_to_process):
                        st.success("All files processed!")
                    else:
                        st.rerun()
        
        # Display combined results if available
        if st.session_state.processed_data:
            st.markdown("### Results")
            
            # Combine all results into a single DataFrame
            df = pd.DataFrame(st.session_state.processed_data)
            
            # Display the combined DataFrame
            st.dataframe(df)
            
            # Download button for combined results
            excel_buffer = create_excel_download_link(df)
            st.download_button(
                label="📥 Download Combined Excel Report",
                data=excel_buffer,
                file_name="combined_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key='download_button'
            )
            
            # Reset button
            if st.button("Process New Files"):
                st.session_state.processed_data = []
                st.session_state.selected_file_index = 0
                st.session_state.files_to_process = []
                st.rerun()
    
    except Exception as e:
        st.error(f"Configuration error: {str(e)}")

# Add some space at the bottom
st.write("")
st.markdown("---")
st.markdown("*Select files and process them one at a time.*")
