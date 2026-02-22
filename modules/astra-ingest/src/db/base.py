from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.config import settings

# Crear el motor de conexión usando la URL de config.py
engine = create_engine(settings.DATABASE_URL, echo=True)

# Crear la fábrica de sesiones
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para los modelos (importada aquí para evitar dependencias circulares)
from src.db.models import Base

# Dependencia para inyección en FastAPI/Workers (útil a futuro)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()