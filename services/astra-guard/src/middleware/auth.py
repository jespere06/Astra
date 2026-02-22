import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.core.security import SecurityUtils
from src.db.database import SessionLocal

logger = logging.getLogger(__name__)

class TenantFirewallMiddleware(BaseHTTPMiddleware):
    """
    Garantiza aislamiento estricto (Zero Trust) entre inquilinos.
    1. Valida autenticación (JWT).
    2. Extrae el tenant_id del token.
    3. Si la ruta accede a un recurso específico (snapshot_id), valida la propiedad en DB.
    """
    
    # Rutas exentas de validación de propiedad (pero no de auth)
    RESOURCE_AGNOSTIC_PATHS = ["/v1/snapshots", "/health", "/docs", "/openapi.json"]

    async def dispatch(self, request: Request, call_next):
        # 0. Skip Health/Docs
        if request.url.path in ["/health", "/docs", "/openapi.json"] or request.url.path.startswith("/v1/health"):
            return await call_next(request)

        # 1. Extracción de Token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401, 
                content={"detail": "Missing Authorization Header"}
            )
        
        token = auth_header.split(" ")[1]

        try:
            # 2. Validación de Identidad
            payload = SecurityUtils.validate_token(token)
            token_tenant = payload.get("tenant_id")
            
            # Inyectar contexto de seguridad en el request para uso en controladores
            request.state.user_id = payload.get("sub")
            request.state.tenant_id = token_tenant

            # 3. Validación de Propiedad del Recurso (Cross-Check)
            # Analizamos si el request intenta acceder a un recurso específico
            path_segments = [s for s in request.url.path.split("/") if s]
            
            # Ejemplo para rutas GET /v1/guard/time-travel/{session_id}
            if len(path_segments) >= 3 and path_segments[2] == "time-travel":
                session_id = path_segments[-1]
                if not self._check_session_ownership(session_id, token_tenant):
                     return JSONResponse(
                        status_code=403,
                        content={"detail": "ACCESO DENEGADO: Violación de aislamiento de inquilino."}
                    )

        except Exception as e:
            logger.error(f"Security Error: {e}")
            return JSONResponse(status_code=401, content={"detail": str(e)})

        return await call_next(request)

    def _check_session_ownership(self, session_id: str, tenant_id: str) -> bool:
        """Consulta ultrarrápida a DB para verificar propiedad."""
        db = SessionLocal()
        try:
            # Usamos SQL directo para máxima velocidad
            stmt = text("SELECT 1 FROM snapshots WHERE session_id = :sid AND tenant_id = :tid LIMIT 1")
            result = db.execute(stmt, {"sid": session_id, "tid": tenant_id}).fetchone()
            return result is not None
        except Exception as e:
            logger.error(f"DB Error checking ownership: {e}")
            return False # Fail-Closed
        finally:
            db.close()
