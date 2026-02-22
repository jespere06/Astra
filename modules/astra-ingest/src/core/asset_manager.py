import io
import imagehash
from PIL import Image
import boto3
from botocore.client import Config
from src.config import settings

class AssetManager:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(
                signature_version='s3v4', 
                s3={'addressing_style': 'path'}
            ),
            use_ssl=settings.MINIO_SECURE
        )
        self._ensure_buckets()

    def _ensure_buckets(self):
        for bucket in [settings.MINIO_BUCKET_ASSETS, settings.MINIO_BUCKET_SKELETONS]:
            try:
                self.s3_client.head_bucket(Bucket=bucket)
            except:
                self.s3_client.create_bucket(Bucket=bucket)

    def process_image(self, file_name: str, file_bytes: bytes) -> dict:
        """
        Calcula pHash y sube si no existe.
        Retorna metadatos del asset.
        """
        try:
            image = Image.open(io.BytesIO(file_bytes))
            # Calcular Perceptual Hash (dHash es rápido y efectivo)
            p_hash = str(imagehash.dhash(image))
            
            # Nombre del objeto en S3 basado en el hash (Deduplicación automática)
            extension = file_name.split('.')[-1]
            object_name = f"{p_hash}.{extension}"
            
            # Verificar si existe (Deduplicación)
            exists = False
            try:
                self.s3_client.head_object(Bucket=settings.MINIO_BUCKET_ASSETS, Key=object_name)
                exists = True
            except:
                pass

            if not exists:
                # Resetear puntero del stream
                data_stream = io.BytesIO(file_bytes)
                self.s3_client.upload_fileobj(
                    data_stream, 
                    settings.MINIO_BUCKET_ASSETS, 
                    object_name,
                    ExtraArgs={'ContentType': f'image/{extension}'}
                )

            return {
                "p_hash": p_hash,
                "s3_path": f"{settings.MINIO_BUCKET_ASSETS}/{object_name}",
                "original_name": file_name.split('/')[-1] # Quitar 'word/media/'
            }

        except Exception as e:
            print(f"Error procesando imagen {file_name}: {e}")
            return None

    def upload_skeleton(self, skeleton_xml: str, tenant_id: str) -> str:
        object_name = f"{tenant_id}/skeleton_{str(hash(skeleton_xml))}.xml"
        self.s3_client.put_object(
            Bucket=settings.MINIO_BUCKET_SKELETONS,
            Key=object_name,
            Body=skeleton_xml.encode('utf-8'),
            ContentType='application/xml'
        )
        return f"{settings.MINIO_BUCKET_SKELETONS}/{object_name}"
