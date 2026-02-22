from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from src.config import settings
from src.api.routes import health
from src.api.routes import jobs, webhooks
from src.controllers import session, assets, training
from src.middleware.auth import AuthMiddleware

app = FastAPI(
    title=settings.APP_NAME,
    version="v1.0.0", 
    description="""
    ## ASTRA Orchestrator API
    
    Núcleo de gestión de sesiones para la plataforma ASTRA.
    
    ### Funcionalidades
    - **Gestión de Ciclo de Vida**: Inicio, pausas, finalización.
    - **Contexto Dinámico**: Actualización en tiempo real de oradores y temas.
    - **Ingesta de Audio**: Recepción de chunks con failover a S3.
    - **Gestión de Archivos**: Subida y optimización de imágenes (anexos).
    """,
    openapi_url="/openapi.json" if settings.ENVIRONMENT != "production" else None,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Configuración de Seguridad (JWT)
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    # Aplicar seguridad globalmente por defecto
    openapi_schema["security"] = [{"BearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Registrar Middleware de Seguridad (P0 - Multitenancy)
app.add_middleware(AuthMiddleware)

app.include_router(health.router)
app.include_router(session.router)
app.include_router(assets.router)
app.include_router(jobs.router)
app.include_router(training.router)
app.include_router(webhooks.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
