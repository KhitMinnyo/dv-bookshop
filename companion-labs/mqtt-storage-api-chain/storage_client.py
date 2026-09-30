import boto3
from botocore.config import Config


def create_storage_client(endpoint_url: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id="training-only-access",
        aws_secret_access_key="training-only-secret",
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
