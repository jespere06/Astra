"""
Cliente de almacenamiento S3/R2 para descarga de audio y subida de resultados.
"""
import os
import logging
import requests
import boto3
from botocore.config import Config as BotoConfig
from src.config import settings

logger = logging.getLogger(__name__)


def _get_s3_client():
    """Crea un cliente S3 compatible (AWS, MinIO, Cloudflare R2)."""
    kwargs = {
        "region_name": settings.AWS_DEFAULT_REGION,
        "config": BotoConfig(
            retries={"max_attempts": 3, "mode": "adaptive"},
            signature_version="s3v4",
        ),
    }

    if settings.AWS_ACCESS_KEY_ID:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL

    return boto3.client("s3", **kwargs)


def download_audio(url: str, local_path: str) -> str:
    """
    Descarga el audio desde una URL (presigned o HTTP directo).

    Soporta:
      - Presigned S3/R2 URLs (https://...)
      - S3 URI directo (s3://bucket/key)
      - Cualquier URL HTTP pública
    """
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)

    if url.startswith("s3://"):
        # Descarga directa via SDK
        parts = url.replace("s3://", "").split("/", 1)
        bucket, key = parts[0], parts[1]
        logger.info(f"📥 Descargando desde S3: {bucket}/{key}")
        client = _get_s3_client()
        client.download_file(bucket, key, local_path)
    else:
        # Presigned URL o HTTP
        logger.info(f"📥 Descargando audio ({url[:80]}...)")
        response = requests.get(url, stream=True, timeout=600)
        response.raise_for_status()

        total = 0
        with open(local_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8 * 1024 * 1024):  # 8MB chunks
                f.write(chunk)
                total += len(chunk)

        logger.info(f"   Descargado: {total / (1024*1024):.1f} MB")

    return local_path


def upload_result(local_path: str, bucket: str, key: str) -> str:
    """
    Sube el JSON de resultado a S3/R2.
    Retorna la URI s3:// del objeto subido.
    """
    client = _get_s3_client()

    logger.info(f"📤 Subiendo resultado a s3://{bucket}/{key}")
    client.upload_file(
        local_path,
        bucket,
        key,
        ExtraArgs={"ContentType": "application/json"},
    )

    s3_uri = f"s3://{bucket}/{key}"
    logger.info(f"   ✅ Subido exitosamente: {s3_uri}")
    return s3_uri
