import os
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configuración
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://astra:astra_pass@postgres:5432/astra_config")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Postgres
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Redis
try:
    redis_client = redis.from_url(REDIS_URL)
except Exception as e:
    print(f"Warning: Redis no disponible. {e}")
    redis_client = None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # En producción usar Alembic, aquí para dev rápido creamos tablas
    from .models import Base
    Base.metadata.create_all(bind=engine)
