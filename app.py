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
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False

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

def process_single_file(s3_client, lambda_client, file, bucket_name, progress_bar, progress_text):
    try:
        # Upload to S3
        s3_client.upload_fileobj(
            file,
            bucket_name,
            file.name
        )
        progress_text.write(f"✅ Uploaded {file.name} to S3")
        
        # Process with Lambda
        payload = {
            "file_name": file.name
        }
        
        response = lambda_client.invoke(
            FunctionName='genaipocpdf',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        
        response_payload = json.loads(response['Payload'].read().decode('utf-8'))
        
        if response['StatusCode'] == 200:
            body = json.loads(response_payload.get('body', '{}'))
            flattened_data = flatten_dict(body)
            # Add filename to the data
            flattened_data['source_file'] = file.name
            progress_text.write(f"✅ Processed {file.name}")
            return flattened_data
        else:
            progress_text.write(f"❌ Error processing {file.name}: {response_payload.get('errorMessage', 'Unknown error')}")
            return None
            
    except Exception as e:
        progress_text.write(f"❌ Error with {file.name}: {str(e)}")
        return None

# Display the main title
st.title('PDF Processor')

# Create a container for the upload section
with st.container():
    st.markdown("### Upload PDF Files")
    st.markdown("Please select one or more PDF files to process:")
    
    # Multiple file uploader
    uploaded_files = st.file_uploader("Choose PDF files", type=['pdf'], accept_multiple_files=True)

# Initialize AWS clients
lambda_client, s3_client = get_aws_clients()

if lambda_client is None or s3_client is None:
    st.error("Unable to initialize AWS clients. Please check your credentials.")
else:
    try:
        S3_BUCKET_NAME = st.secrets["aws_credentials"]["S3_BUCKET_NAME"]
        
        # If files are uploaded, show details and process button
        if uploaded_files:
            st.success(f"{len(uploaded_files)} files uploaded successfully!")
            
            # Display file details in a table
            file_details = [{
                "File Name": file.name,
                "Size (bytes)": file.size,
                "Type": file.type
            } for file in uploaded_files]
            st.table(pd.DataFrame(file_details))
            
            # Process button
            if st.button('Process PDFs', key='process_button'):
                st.session_state.processed_data = []  # Reset processed data
                
                # Create progress bar and status text
                progress_bar = st.progress(0)
                progress_text = st.empty()
                
                # Process each file
                for idx, file in enumerate(uploaded_files):
                    progress_text.write(f"Processing {file.name}...")
                    result = process_single_file(s3_client, lambda_client, file, S3_BUCKET_NAME, progress_bar, progress_text)
                    if result:
                        st.session_state.processed_data.append(result)
                    progress_bar.progress((idx + 1) / len(uploaded_files))
                    time.sleep(0.5)  # Small delay to show progress
                
                progress_bar.progress(100)
                st.session_state.processing_complete = True
        
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
    
    except Exception as e:
        st.error(f"Configuration error: {str(e)}")

# Add some space at the bottom
st.write("")
st.markdown("---")
st.markdown("*Upload PDF files and click 'Process PDFs' to start processing.*")
