import unittest
import os
import boto3
from unittest.mock import patch, MagicMock
from src.mining.downloader import MediaDownloader, DownloadError

class TestMediaDownloader(unittest.TestCase):
    
    def setUp(self):
        # Configuramos variables de entorno dummy si no existen para evitar errores de conexión en CI puro
        if not os.getenv("MINIO_ENDPOINT"):
            os.environ["MINIO_ENDPOINT"] = "localhost:9000"
            os.environ["MINIO_ACCESS_KEY"] = "admin"
            os.environ["MINIO_SECRET_KEY"] = "password"
            
        self.downloader = MediaDownloader()
        self.tenant_id = "test_tenant_integration"
        # Video de prueba "Me at the zoo" (muy corto, bajo riesgo de copyright)
        self.test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw" 

    def test_validation_empty_url(self):
        """Debe lanzar ValueError si la URL es vacía."""
        with self.assertRaises(ValueError):
            self.downloader.download_and_upload("", self.tenant_id)

    @patch('src.mining.downloader.subprocess.run')
    @patch('src.mining.downloader.boto3.client')
    def test_download_flow_mock(self, mock_boto_client, mock_subprocess):
        """
        Test unitario con Mocks para validar la lógica sin internet/ffmpeg.
        Simula una descarga exitosa creando un archivo dummy.
        """
        # 1. Mock S3 Client
        mock_s3 = MagicMock()
        self.downloader.s3_client = mock_s3
        
        # 2. Mock Subprocess para evitar llamar yt-dlp real
        mock_subprocess.return_value.returncode = 0
        
        # 3. Interceptar la apertura del archivo para evitar FileNotFoundError
        # ya que yt-dlp no correrá realmente para crear el archivo
        with patch("builtins.open", unittest.mock.mock_open(read_data=b"dummy audio data")) as mock_file:
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=1024):
                    with patch("os.remove") as mock_remove:
                        
                        # Ejecutar
                        uri = self.downloader.download_and_upload("http://fake.url", "tenant_x")
                        
                        # Verificaciones
                        self.assertTrue(uri.startswith("s3://astra-raw/mining/tenant_x/"))
                        self.assertTrue(uri.endswith(".wav"))
                        
                        # Verificar que se llamó a yt-dlp con los argumentos correctos
                        args, _ = mock_subprocess.call_args
                        cmd_list = args[0]
                        self.assertIn("yt-dlp", cmd_list)
                        self.assertIn("ffmpeg:-ac 1 -ar 16000 -acodec pcm_s16le", " ".join(cmd_list))
                        
                        # Verificar subida a S3
                        mock_s3.upload_fileobj.assert_called_once()
                        
                        # Verificar limpieza
                        mock_remove.assert_called_once()

    # Este test se salta si no estamos en un entorno con yt-dlp instalado o si es CI estricto
    @unittest.skipIf(os.getenv("CI") == "true", "Skipping integration test in CI environment")
    def test_live_download_integration(self):
        """
        Test de integración real. Requiere internet, yt-dlp y MinIO accesible.
        Intenta descargar un video real y subirlo.
        """
        try:
            # Ejecutar descarga real
            s3_uri = self.downloader.download_and_upload(self.test_url, self.tenant_id)
            print(f"Integration Success: {s3_uri}")
            
            # Verificar existencia en S3
            bucket, key = s3_uri.replace("s3://", "").split("/", 1)
            
            # Head object para verificar metadata
            response = self.downloader.s3_client.head_object(Bucket=bucket, Key=key)
            self.assertEqual(response['ContentType'], 'audio/wav')
            self.assertGreater(response['ContentLength'], 0)
            
            # Limpieza remota (S3)
            self.downloader.s3_client.delete_object(Bucket=bucket, Key=key)
            
        except Exception as e:
            # Si falla por conexión o falta de herramientas, fallamos el test con detalle
            self.fail(f"Live integration failed: {e}")

if __name__ == "__main__":
    unittest.main()
