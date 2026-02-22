import os
import uuid
import logging
import subprocess
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from src.config import settings

logger = logging.getLogger(__name__)

class DownloadError(Exception):
    """Excepción lanzada cuando falla la descarga o conversión del medio."""
    pass

class MediaDownloader:
    """
    Servicio encargado de adquirir medios desde fuentes externas (YouTube, etc.),
    normalizarlos a formatos estándar para ML (WAV 16kHz Mono) y persistirlos en S3.
    """
    
    # Bucket destino para audios crudos de minería
    BUCKET_NAME = "astra-raw"

    def __init__(self):
        # Configuración del cliente S3 (MinIO/AWS)
        self.s3_client = boto3.client(
            's3',
            endpoint_url=f"http://{settings.MINIO_ENDPOINT}",
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'},
                retries={'max_attempts': 3, 'mode': 'standard'}
            ),
            use_ssl=settings.MINIO_SECURE
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Garantiza que el bucket de destino exista."""
        try:
            self.s3_client.head_bucket(Bucket=self.BUCKET_NAME)
        except ClientError:
            try:
                self.s3_client.create_bucket(Bucket=self.BUCKET_NAME)
                logger.info(f"Bucket '{self.BUCKET_NAME}' creado exitosamente.")
            except Exception as e:
                logger.error(f"No se pudo crear el bucket '{self.BUCKET_NAME}': {e}")
                raise

    def download_and_upload(self, url: str, tenant_id: str) -> str:
        """
        Orquesta el flujo de descarga -> normalización -> subida.

        Args:
            url (str): URL pública del video/audio.
            tenant_id (str): ID del inquilino para organizar el almacenamiento.

        Returns:
            str: URI interna del archivo en S3 (s3://astra-raw/mining/...).
        
        Raises:
            ValueError: Si la URL es inválida.
            DownloadError: Si falla yt-dlp o ffmpeg.
        """
        if not url:
            raise ValueError("La URL no puede estar vacía.")

        file_id = str(uuid.uuid4())
        temp_dir = "/tmp"
        
        # Plantilla de salida para yt-dlp. 
        # %(ext)s será reemplazado por 'mp3' debido a --audio-format mp3
        output_template = os.path.join(temp_dir, f"{file_id}.%(ext)s")
        expected_filename = os.path.join(temp_dir, f"{file_id}.mp3")

        logger.info(f"Iniciando descarga de {url} para tenant {tenant_id}...")

        # Construcción del comando yt-dlp
        # -x: Extraer audio
        # --audio-format mp3: Convertir contenedor a MP3
        # --postprocessor-args: Pasar argumentos a ffmpeg para forzar MP3 ultra-ligero
        #   -ac 1: 1 Canal (Mono)
        #   -ar 16000: Sample rate 16kHz
        #   -ab 64k: Bitrate 64kbps
        cmd = [
            "yt-dlp",
            "-x",
            "--audio-format", "mp3",
            "--output", output_template,
            "--postprocessor-args", "ffmpeg:-ac 1 -ar 16000 -ab 64k",
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            "--no-check-certificate", # Útil en entornos corporativos/dev con proxies SSL raros
            url
        ]

        try:
            # 1. Ejecutar descarga y conversión
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True,
                timeout=600 # 10 minutos máximo
            )
            
            # Validar existencia física del archivo
            if not os.path.exists(expected_filename):
                raise DownloadError(f"El archivo esperado no se creó: {expected_filename}")
            
            file_size = os.path.getsize(expected_filename)
            if file_size == 0:
                raise DownloadError("El archivo descargado está vacío.")

            logger.info(f"Audio descargado y normalizado ({file_size} bytes). Subiendo a S3...")

            # 2. Subir a S3
            s3_key = f"mining/{tenant_id}/{file_id}.mp3"
            
            with open(expected_filename, "rb") as f:
                self.s3_client.upload_fileobj(
                    f, 
                    self.BUCKET_NAME, 
                    s3_key,
                    ExtraArgs={'ContentType': 'audio/mpeg'}
                )

            s3_uri = f"s3://{self.BUCKET_NAME}/{s3_key}"
            logger.info(f"Persistencia exitosa: {s3_uri}")
            
            return s3_uri

        except subprocess.CalledProcessError as e:
            logger.error(f"Error en yt-dlp: {e.stderr}")
            raise DownloadError(f"Fallo en la descarga externa: {e.stderr}")
        except subprocess.TimeoutExpired:
            logger.error("Timeout en la descarga.")
            raise DownloadError("La descarga excedió el tiempo límite de 10 minutos.")
        except Exception as e:
            logger.error(f"Error inesperado en MediaDownloader: {e}")
            raise e
        finally:
            # 3. Limpieza Fail-Safe
            if os.path.exists(expected_filename):
                try:
                    os.remove(expected_filename)
                    logger.debug(f"Archivo temporal eliminado: {expected_filename}")
                except OSError as e:
                    logger.warning(f"No se pudo eliminar archivo temporal: {e}")
