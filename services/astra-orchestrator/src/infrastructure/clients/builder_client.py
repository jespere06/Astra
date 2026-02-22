import httpx
import logging
from src.config import settings
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class BuilderClient:
    def __init__(self):
        self.base_url = settings.BUILDER_URL
        self.timeout = httpx.Timeout(60.0) # Building can take time

    async def generate_document(self, payload: dict) -> str:
        """
        Sends session data (or reference) to Builder to generate DOCX.
        Returns the signed URL or ID of the generated document.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                # Assuming Builder API: POST /v1/build
                response = await client.post(f"{self.base_url}/v1/build", json=payload)
                response.raise_for_status()
                
                result = response.json()
                return result.get("document_url", "")
                
            except httpx.HTTPError as e:
                logger.error(f"Error calling Builder Service: {e}")
                # Mock if dev env and service unavailable
                if settings.ENVIRONMENT == "development":
                     logger.warning("Builder unavailable, returning mock document URL")
                     return "https://astra-dev.s3.amazonaws.com/mock-minutes.docx"
                raise HTTPException(status_code=503, detail="Builder Service Unavailable")
