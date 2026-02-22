import pytest
import uuid
import os
from src.client import AstraApiClient
from src.utils import ensure_test_assets

@pytest.fixture(scope="session")
def api_client():
    client = AstraApiClient()
    # client.check_health() # Descomentar cuando los servicios estén arriba
    return client

@pytest.fixture(scope="session")
def tenant_id():
    # Generar un tenant único para esta ejecución para evitar colisiones
    return f"tenant_e2e_{uuid.uuid4().hex[:8]}"

@pytest.fixture(scope="session")
def samples_dir():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    samples = os.path.join(base_dir, "samples")
    ensure_test_assets(samples)
    return samples

@pytest.fixture(scope="session")
def artifacts_dir():
    # Directorio para descargar resultados
    base_dir = os.path.dirname(os.path.abspath(__file__))
    artifacts = os.path.join(base_dir, "artifacts")
    os.makedirs(artifacts, exist_ok=True)
    return artifacts
