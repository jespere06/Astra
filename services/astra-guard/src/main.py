from fastapi import FastAPI
import logging
from src.api.routes import snapshots, recovery, internal
from src.middleware.auth import TenantFirewallMiddleware

# Configuración de Logging Estructurado
logging.basicConfig(
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "message": "%(message)s"}',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ASTRA-GUARD (The Vault)",
    description="Servicio de Integridad Inmutable y Preservación Legal",
    version="0.1.0"
)

# Registrar Middleware de Seguridad
app.add_middleware(TenantFirewallMiddleware)

# Registrar Rutas
app.include_router(snapshots.router)
app.include_router(recovery.router)
app.include_router(internal.router)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "module": "astra-guard",
        "version": "0.1.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
