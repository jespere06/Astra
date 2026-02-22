import asyncio
import logging
import grpc
from src.config import settings

# Mocking imports if generated code doesn't exist yet in local env
# In production, these will be real generated files
try:
    from src.generated import session_service_pb2_grpc
    from src.api.grpc.servicers import OrchestratorServicer
except ImportError:
    print("⚠️ Generated protos not found. Skipping gRPC server start.")
    exit(0)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gRPC-Server")

async def serve():
    server = grpc.aio.server()
    session_service_pb2_grpc.add_SessionOrchestratorServicer_to_server(
        OrchestratorServicer(), server
    )
    
    listen_addr = f"[::]:{settings.GRPC_PORT}"
    server.add_insecure_port(listen_addr)
    
    logger.info(f"🚀 ASTRA Orchestrator gRPC Hub listening on {listen_addr}")
    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())
