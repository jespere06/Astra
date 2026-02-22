import httpx
import logging

logger = logging.getLogger(__name__)

class TenantConfigClient:
    def __init__(self, base_url: str = None):
        import os
        self.base_url = base_url or os.getenv("TENANT_CONFIG_URL", "http://tenant-config-service:8080")

    async def update_dictionary(self, tenant_id: str, new_entries: dict) -> bool:
        """
        Envía los nuevos pares al servicio de configuración para mergear.
        """
        if not new_entries:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/v1/config/{tenant_id}/dictionary",
                    json={"updates": new_entries},
                    timeout=5.0
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Fallo actualizando diccionario del tenant {tenant_id}: {e}")
            return False
