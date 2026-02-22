import re
import logging
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from jose import JWTError
import redis.asyncio as redis

from src.core.security import SecurityUtils
from src.infrastructure.redis_client import redis_pool
from src.config import settings

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    # Rutas públicas que no requieren autenticación
    PUBLIC_PATHS = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health"
    ]

    # Regex para extraer session_id de la URL (ej: /v1/session/{uuid}/append)
    SESSION_PATH_REGEX = re.compile(r"/v1/session/([a-f0-9\-]+)")

    async def dispatch(self, request: Request, call_next):
        # 1. Skip rutas públicas
        if request.url.path in self.PUBLIC_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        # 2. Validación de Header Authorization
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid Authorization header"}
            )

        token = auth_header.split(" ")[1]

        try:
            # 3. Validación de JWT
            payload = SecurityUtils.validate_token(token)
            tenant_id = payload.get("tenant_id")
            user_id = payload.get("sub")

            if not tenant_id:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Token missing tenant_id claim"}
                )

            # Inyección de contexto en el request state
            request.state.tenant_id = tenant_id
            request.state.user_id = user_id

        except HTTPException as he:
            # CAPTURAR EXCEPCIONES HTTP PARA EVITAR EL 500
            return JSONResponse(status_code=he.status_code, content={"detail": he.detail})
        except JWTError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired token"}
            )

        # 4. Session Guard (Aislamiento Cross-Tenant)
        # Verificar si la ruta accede a un recurso de sesión específico
        match = self.SESSION_PATH_REGEX.search(request.url.path)
        if match:
            session_id = match.group(1)
            
            # Consultar Redis para verificar propiedad
            # Usamos un cliente Redis efímero conectado al pool global
            try:
                async with redis.Redis(connection_pool=redis_pool) as r:
                    session_key = f"session:{session_id}:meta"
                    stored_tenant = await r.hget(session_key, "tenant_id")

                    if stored_tenant:
                        # Si la sesión existe, verificar que pertenezca al tenant del token
                        if stored_tenant != tenant_id:
                            logger.warning(f"SECURITY ALERT: Tenant {tenant_id} attempted access to Session {session_id} belonging to {stored_tenant}")
                            return JSONResponse(
                                status_code=status.HTTP_403_FORBIDDEN,
                                content={"detail": "Access to this session is forbidden for your tenant"}
                            )
                    else:
                        # Si la sesión no existe en Redis (puede haber expirado o ser un ID inválido),
                        # dejamos pasar para que el controlador maneje el 404, 
                        # o podemos bloquear si somos estrictos. 
                        # Para evitar fugas de información sobre existencia de IDs, dejamos pasar al 404 del controller.
                        pass
            except Exception as e:
                logger.error(f"Redis error in AuthMiddleware: {e}")
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={"detail": "Authorization service unavailable"}
                )

        # Continuar con el request
        response = await call_next(request)
        return response


async def get_current_tenant(request: Request) -> str:
    """
    FastAPI dependency que extrae el tenant_id del request state.
    El AuthMiddleware ya lo valida y lo inyecta en request.state.tenant_id.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authenticated tenant found"
        )
    return tenant_id
