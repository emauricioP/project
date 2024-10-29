import streamlit as st
import boto3
import json
import pandas as pd
from io import BytesIO
from botocore.exceptions import ClientError
import base64

# Configure page settings
st.set_page_config(
    page_title="PDF Processor",
    page_icon="📄",
    layout="wide"
)

def validate_aws_credentials(access_key, secret_key, region):
    """Validate AWS credentials format"""
    if not access_key or len(access_key.strip()) < 16:
        return False, "Invalid Access Key format"
    if not secret_key or len(secret_key.strip()) < 32:
        return False, "Invalid Secret Key format"
    if not region or not region.strip().startswith('us-') and not region.strip().startswith('eu-'):
        return False, "Invalid Region format"
    return True, "Valid credentials"

def check_secrets():
    """Check and validate AWS credentials in secrets"""
    try:
        secrets = st.secrets["aws_credentials"]
        required_secrets = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"]
        
        # Check for missing secrets
        missing_secrets = [secret for secret in required_secrets if secret not in secrets]
        if missing_secrets:
            st.error(f"Missing required secrets: {', '.join(missing_secrets)}")
            st.error("Please configure AWS credentials in Streamlit Cloud secrets.")
            return False

        # Validate credentials format
        valid, message = validate_aws_credentials(
            secrets["AWS_ACCESS_KEY_ID"],
            secrets["AWS_SECRET_ACCESS_KEY"],
            secrets["AWS_REGION"]
        )
        
        if not valid:
            st.error(f"Invalid AWS credentials: {message}")
            return False
            
        return True
    except Exception as e:
        st.error(f"Error checking secrets: {str(e)}")
        return False

@st.cache_resource
def get_lambda_client():
    """Create AWS Lambda client with error handling"""
    if not check_secrets():
        return None
    
    try:
        # Clean up credentials by removing any whitespace
        credentials = st.secrets["aws_credentials"]
        client = boto3.client(
            'lambda',
            aws_access_key_id=credentials["AWS_ACCESS_KEY_ID"].strip(),
            aws_secret_access_key=credentials["AWS_SECRET_ACCESS_KEY"].strip(),
            region_name=credentials["AWS_REGION"].strip()
        )
        
        # Test the credentials with a simple Lambda operation
        try:
            client.get_account_settings()
            return client
        except ClientError as e:
            if e.response['Error']['Code'] == 'InvalidSignatureException':
                st.error("AWS credentials are invalid. Please check your Access Key and Secret Key.")
            else:
                st.error(f"Error validating AWS credentials: {str(e)}")
            return None
            
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

# Lambda function name
LAMBDA_FUNCTION_NAME = 'genaipocpdf'

st.title('PDF Processor')

# Display current AWS configuration (for debugging)
if st.checkbox("Show AWS Configuration"):
    try:
        credentials = st.secrets["aws_credentials"]
        st.write("AWS Region:", credentials["AWS_REGION"])
        st.write("Access Key ID (first 4 chars):", credentials["AWS_ACCESS_KEY_ID"][:4] + "****")
        st.write("Secret Key is configured:", bool(credentials["AWS_SECRET_ACCESS_KEY"]))
    except Exception as e:
        st.error("Could not display AWS configuration")

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
                # Invoke Lambda function
                try:
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
                
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    error_message = e.response['Error']['Message']
                    st.error(f"AWS Error ({error_code}): {error_message}")
                    if error_code == 'InvalidSignatureException':
                        st.error("Please verify your AWS credentials in the Streamlit Cloud secrets.")

        except Exception as e:
            st.error(f"Error executing Lambda function: {str(e)}")
            st.error(f"Error details: {type(e).__name__}")

    st.text("Click 'Process PDF' to start processing Fuji_pdfFile.pdf")
else:
    st.warning("Application is not properly configured. Please check the error messages above.")
