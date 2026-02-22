import logging
import requests
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ConfigServiceClient:
    """
    Cliente para comunicarse con el Tenant Config Service.
    Maneja la propagación de configuraciones.
    """
    
    def __init__(self, base_url: str = "http://tenant-config-service:8080", api_key: str = ""):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def update_zone_mappings(self, tenant_id: str, mappings: Dict[str, Any]) -> bool:
        """
        Envía los mapeos al servicio de configuración.
        
        Args:
            tenant_id: ID del inquilino.
            mappings: Payload con formato {"mappings": [{"template_id": "...", "zone": "..."}]}
            
        Returns:
            True si fue exitoso (200 OK), False o Exception en caso contrario.
        """
        url = f"{self.base_url}/config/{tenant_id}/zones"
        
        try:
            # En producción, usar requests.put o .post según contrato
            # response = requests.post(url, json=mappings, headers=self.headers, timeout=5)
            # response.raise_for_status()
            
            # Simulación de éxito para desarrollo local sin el servicio levantado
            logger.info(f"📡 [SIMULACIÓN] Enviando a {url}: {len(mappings.get('mappings', []))} reglas.")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error comunicando con Tenant Config Service: {e}")
            raise e