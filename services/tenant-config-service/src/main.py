from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db, init_db
from . import logic, schemas

app = FastAPI(title="ASTRA Tenant Config Service", version="1.0.0")

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "tenant-config"}

@app.get("/v1/config/{tenant_id}", response_model=schemas.TenantConfigResponse)
def get_tenant_configuration(tenant_id: str, db: Session = Depends(get_db)):
    """
    Retorna la configuración completa consolidada para un inquilino.
    Usado por ASTRA-ORCHESTRATOR al inicio de sesión.
    """
    return logic.get_config(db, tenant_id)

@app.patch("/v1/config/{tenant_id}", response_model=schemas.TenantConfigResponse)
def update_tenant_configuration(
    tenant_id: str, 
    payload: schemas.TenantConfigUpdate, 
    db: Session = Depends(get_db)
):
    """
    Actualiza parcial o totalmente la configuración.
    Usado por ASTRA-INGEST (automático) o ADMIN-UI (manual).
    Fuerza la invalidación de caché.
    """
    return logic.update_config(db, tenant_id, payload)
