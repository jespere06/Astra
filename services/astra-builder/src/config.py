from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    AWS_ACCESS_KEY_ID: str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str = "minioadmin"
    AWS_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str = "http://minio:9000" # Para local
    S3_BUCKET_SKELETONS: str = "astra-skeletons"
    S3_BUCKET_OUTPUT: str = "astra-output"
    
    TEMP_DIR: str = "/tmp/astra-builds"

    class Config:
        env_file = ".env"

settings = Settings()
