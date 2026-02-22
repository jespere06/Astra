import boto3
import json
import logging
import io
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

class S3DatasetGateway:
    def __init__(self, bucket_name: str = "astra-models"):
        self.s3 = boto3.client('s3') # Credenciales por ENV
        self.bucket = bucket_name

    def upload_batch(self, tenant_id: str, rows: List[Dict]) -> str:
        """
        Sube un lote de ejemplos de entrenamiento a S3 en formato JSONL.
        """
        if not rows:
            return ""

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        date_folder = datetime.utcnow().strftime("%Y-%m-%d")
        
        file_key = f"learning_data/datasets/{tenant_id}/{date_folder}/batch_{timestamp}.jsonl"
        
        # Convertir a JSONL en memoria
        buffer = io.BytesIO()
        for row in rows:
            line = json.dumps(row, ensure_ascii=False) + "\n"
            buffer.write(line.encode('utf-8'))
        
        buffer.seek(0)

        try:
            self.s3.upload_fileobj(
                buffer, 
                self.bucket, 
                file_key,
                ExtraArgs={'ServerSideEncryption': 'AES256'}
            )
            logger.info(f"Dataset batch subido: {file_key} ({len(rows)} items)")
            return f"s3://{self.bucket}/{file_key}"
        except Exception as e:
            logger.error(f"Error subiendo dataset a S3: {e}")
            raise e
