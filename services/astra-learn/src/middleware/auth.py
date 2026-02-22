from fastapi import Header, HTTPException

async def get_current_tenant(x_tenant_id: str = Header(...)):
    """
    Dependency simple para extraer el tenant_id de los headers.
    En un entorno real, esto validaría un JWT.
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header is missing")
    return x_tenant_id
