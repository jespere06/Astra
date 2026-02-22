import grpc
import logging
from src.config import settings

# In production use the real generated files
# from src.generated import asset_pb2, asset_pb2_grpc
# For development MVP without protoc step:
from src.generated.asset_mocks import asset_pb2, asset_pb2_grpc

logger = logging.getLogger(__name__)

class IngestGrpcClient:
    def __init__(self):
        # Canal inseguro para comunicación interna en el cluster
        self.channel = grpc.insecure_channel(settings.INGEST_GRPC_URL)
        # Using the mock or real stub
        self.stub = asset_pb2_grpc.AssetServiceStub(self.channel)

    async def check_duplicate(self, tenant_id: str, image_data: bytes):
        """
        Consulta si el activo ya existe. 
        Deadlines de 50ms (0.05s) para cumplir con el SLA de UX.
        """
        try:
            request = asset_pb2.CheckReq(
                tenant_id=tenant_id,
                image_data=image_data
            )
            # Política Fail-Open: Timeout agresivo (0.05s = 50ms)
            # Note: gRPC Python Sync stub blocks. 
            # In asyncio, we should ideally use grpc.aio or run in executor.
            # But prompt specifically uses sync stub calls possibly.
            # Let's check prompt code: "response = self.stub.CheckDuplicate(request, timeout=0.05)"
            # Sync calls block event loop. For 50ms it's barely acceptable, but risky.
            # However, we follow prompt strict implementation.
            response = self.stub.CheckDuplicate(request, timeout=0.05)
            
            # Mock check for dev environment
            if hasattr(response, 'is_duplicate'):
                return response.is_duplicate, response.asset_id, response.confidence
            return False, None, 0.0 # Just in case mock behaves weirdly
            
        except grpc.RpcError as e:
            # Si falla gRPC o hay timeout, logueamos y retornamos "no duplicado"
            logger.warning(f"gRPC Fail-Open activado: {e.code()} - {e.details()}")
            return False, None, 0.0
        except Exception as e:
            logger.warning(f"Unexpected error in duplicate check: {e}")
            return False, None, 0.0
