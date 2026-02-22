import boto3
from botocore.config import Config
from src.config import settings

class S3Client:
    def __init__(self):
        self.client = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            config=Config(signature_version='s3v4')
        )

    def download_file(self, bucket: str, key: str, download_path: str, version_id: str = None):
        """Descarga con soporte explícito de VersionId."""
        kwargs = {'Bucket': bucket, 'Key': key, 'Filename': download_path}
        if version_id:
            kwargs['ExtraArgs'] = {'VersionId': version_id}
            
        self.client.download_file(**kwargs)

    def upload_file(self, file_path: str, bucket: str, key: str):
        self.client.upload_file(file_path, bucket, key)
