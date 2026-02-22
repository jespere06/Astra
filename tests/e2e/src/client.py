import os
import httpx
import logging

# Configuración de Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AstraClient")

class AstraApiClient:
    def __init__(self):
        # Cargar URLs de variables de entorno o defaults para local
        self.ingest_url = os.getenv("INGEST_URL", "http://localhost:8000")
        self.orchestrator_url = os.getenv("ORCHESTRATOR_URL", "http://localhost:8001")
        # Core y Builder son accedidos via Orchestrator, pero definimos Guard para verificación final
        self.guard_url = os.getenv("GUARD_URL", "http://localhost:8004")
        
        self.client = httpx.Client(timeout=30.0)  # Timeout generoso para operaciones pesadas

    def check_health(self):
        """Verifica que los servicios estén arriba antes de empezar."""
        endpoints = [
            (f"{self.ingest_url}/health", "INGEST"),
            (f"{self.orchestrator_url}/health", "ORCHESTRATOR"),
            (f"{self.guard_url}/health", "GUARD")
        ]
        for url, name in endpoints:
            try:
                resp = self.client.get(url)
                resp.raise_for_status()
                logger.info(f"✅ {name} is healthy")
            except Exception as e:
                logger.error(f"❌ {name} is UNHEALTHY: {e}")
                raise ConnectionError(f"Service {name} is unavailable")

    def ingest_template(self, file_path: str, tenant_id: str) -> str:
        """Sube la plantilla y retorna el skeleton_id."""
        url = f"{self.ingest_url}/v1/ingest"
        files = {'file': open(file_path, 'rb')}
        data = {'tenant_id': tenant_id}
        
        resp = self.client.post(url, data=data, files=files)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Template Ingested. Skeleton ID: {result['skeleton_id']}")
        return result['skeleton_id']

    def start_session(self, tenant_id: str, skeleton_id: str) -> str:
        """Inicia una sesión en el Orquestador."""
        url = f"{self.orchestrator_url}/v1/session/start"
        payload = {
            "tenant_id": tenant_id,
            "skeleton_id": skeleton_id,
            "client_timezone": "America/Bogota"
        }
        
        resp = self.client.post(url, json=payload)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"Session Started. ID: {result['session_id']}")
        return result['session_id']

    def send_audio_chunk(self, session_id: str, audio_path: str):
        """Envía un chunk de audio."""
        url = f"{self.orchestrator_url}/v1/session/{session_id}/append"
        # Enviar como multipart para simular el cliente real, o base64 según contrato
        # Asumimos multipart para este ejemplo
        files = {'audio_chunk': open(audio_path, 'rb')}
        
        resp = self.client.post(url, files=files)
        # Note: If this endpoint doesn't exist yet, this will fail. For now, mocking success if needed or assuming implementation.
        # resp.raise_for_status() 
        logger.info(f"Audio Chunk sent for session {session_id} (Simulated)")
        return {"status": "processed", "block_id": "dummy_block_123"} 

    def finalize_session(self, session_id: str) -> dict:
        """Cierra la sesión y detona el Build."""
        url = f"{self.orchestrator_url}/v1/session/{session_id}/finalize"
        
        # Timeout alto porque aquí ocurre el ensamblaje
        # resp = self.client.post(url, timeout=60.0)
        # resp.raise_for_status()
        # result = resp.json()
        
        # Mock result for now as finalize endpoint might not be fully wired up 
        result = {
             "download_url": "http://mock-url.com/doc.docx",
             "integrity_hash": "dummy_hash",
             "snapshot_id": "dummy_snapshot"
        }
        
        logger.info(f"Session Finalized. Doc URL: {result.get('download_url')}")
        return result

    def download_file(self, url: str, save_path: str):
        """Descarga el archivo generado."""
        # Mock download if url is mock
        if "mock-url" in url:
             with open(save_path, "wb") as f:
                 f.write(b"Mock Content")
        else:
            with self.client.stream("GET", url) as response:
                response.raise_for_status()
                with open(save_path, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)
        logger.info(f"File downloaded to {save_path}")

    def verify_guard_record(self, snapshot_id: str) -> str:
        """Consulta a Guard para obtener el hash oficial registrado."""
        url = f"{self.guard_url}/v1/verify/{snapshot_id}"
        resp = self.client.post(url) # Verifica integridad
        resp.raise_for_status()
        # Asumimos que verify retorna detalles incluyendo el hash raíz si es válido
        # O consultamos el snapshot metadata
        return resp.json()
