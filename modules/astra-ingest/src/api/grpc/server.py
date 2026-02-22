
import grpc
from concurrent import futures
import logging
from sqlalchemy.orm import Session

# Imports generados (asumiendo que se ejecutó el script de generación)
from src.generated import asset_pb2
from src.generated import asset_pb2_grpc

from src.db.base import SessionLocal
from src.core.media.processor import MediaProcessor
from src.core.exceptions import AstraIngestError

# Configuración de Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AssetService(asset_pb2_grpc.AssetServiceServicer):
    
    def _get_db(self):
        return SessionLocal()

    def CheckDuplicate(self, request, context):
        """
        Implementación del RPC CheckDuplicate.
        """
        db: Session = self._get_db()
        try:
            if not request.image_data:
                context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Image data is empty")

            processor = MediaProcessor(db)
            is_dup, asset_id, conf = processor.find_duplicate(
                tenant_id=request.tenant_id,
                image_data=request.image_data
            )
            
            return asset_pb2.CheckResp(
                is_duplicate=is_dup,
                asset_id=asset_id or "",
                confidence=conf
            )
            
        except AstraIngestError as e:
            logger.error(f"Error procesando asset: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))
        except Exception as e:
            logger.exception("Error no controlado en CheckDuplicate")
            context.abort(grpc.StatusCode.UNKNOWN, "Internal Server Error")
        finally:
            db.close()

    def RegisterAsset(self, request, context):
        """
        Implementación del RPC RegisterAsset.
        """
        db: Session = self._get_db()
        try:
            processor = MediaProcessor(db)
            asset = processor.register_new_asset(
                tenant_id=request.tenant_id,
                image_data=request.image_data,
                filename=request.original_filename or "unknown.png"
            )
            
            return asset_pb2.RegisterResp(
                asset_id=str(asset.id),
                storage_url=asset.storage_url
            )
        except Exception as e:
            logger.exception("Error en RegisterAsset")
            context.abort(grpc.StatusCode.INTERNAL, str(e))
        finally:
            db.close()

def serve(port: str = "50051"):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    asset_pb2_grpc.add_AssetServiceServicer_to_server(AssetService(), server)
    server.add_insecure_port(f'[::]:{port}')
    logger.info(f"🚀 ASTRA-INGEST gRPC Server corriendo en el puerto {port}")
    server.start()
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
