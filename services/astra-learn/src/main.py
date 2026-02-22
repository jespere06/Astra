from fastapi import FastAPI
import logging
from src.api.routes import compare, learning, review, sessions

# Configuración de Logging
logging.basicConfig(
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "message": "%(message)s"}',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ASTRA-LEARN",
    description="Motor de Auto-Aprendizaje y Alineación Semántica",
    version="0.1.0"
)

# Inicializar Base de Datos (Para desarrollo/demo)
from src.db.database import engine, Base
from src.db.models import queue, job, session # Asegurar que modelos están cargados
Base.metadata.create_all(bind=engine)

# Registrar Rutas
app.include_router(compare.router)
app.include_router(learning.router)
app.include_router(review.router)
app.include_router(sessions.router)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "module": "astra-learn",
        "version": "0.1.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
