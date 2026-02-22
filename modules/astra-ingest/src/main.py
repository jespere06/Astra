from fastapi import FastAPI
from src.infrastructure.database import engine
from src.infrastructure.models import Base

# Importar los routers de los submódulos
from src.api.routes.ingest import router as ingest_router
from src.api.routes.mapping import router as mapping_router
from src.api.routes.admin import router as admin_router
from src.api.routes.document import router as document_router

# Crear tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ASTRA Ingest Service")

# Registrar todos los routers bajo /v1
app.include_router(ingest_router, prefix="/v1")   # /v1/ingest/batch, /v1/ingest/mining/sync
app.include_router(mapping_router, prefix="/v1")  # /v1/config/...
app.include_router(admin_router)                  # /v1/admin/...
app.include_router(document_router, prefix="/v1") # /v1/ingest (Documento único)