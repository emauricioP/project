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
def get_lambda_client():
    """Create AWS Lambda client with error handling"""
    try:
        # Clean up credentials by removing any whitespace
        credentials = st.secrets["aws_credentials"]
        client = boto3.client(
            'lambda',
            aws_access_key_id=credentials["AWS_ACCESS_KEY_ID"].strip(),
            aws_secret_access_key=credentials["AWS_SECRET_ACCESS_KEY"].strip(),
            region_name=credentials["AWS_REGION"].strip()
        )
        return client
            
    except Exception as e:
        st.error(f"Error creating AWS client: {str(e)}")
        return None

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

# Lambda function name
LAMBDA_FUNCTION_NAME = 'genaipocpdf'

st.title('PDF Processor')

# Initialize Lambda client
lambda_client = get_lambda_client()

if lambda_client is not None:
    if st.button('Process PDF'):
        try:
            # Prepare payload for Lambda function
            payload = {
                "file_name": "Fuji_pdfFile.pdf"
            }

            with st.spinner('Processing PDF...'):
                try:
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
                    error_code = e.response['Error']['Code']
                    error_message = e.response['Error']['Message']
                    st.error(f"AWS Error ({error_code}): {error_message}")

        except Exception as e:
            st.error(f"Error executing Lambda function: {str(e)}")
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

st.text("Click 'Process PDF' to start processing Fuji_pdfFile.pdf")
