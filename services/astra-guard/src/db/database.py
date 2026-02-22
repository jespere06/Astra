from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.config import settings

# En un entorno real, DATABASE_URL vendría de config
SQLALCHEMY_DATABASE_URL = "postgresql://astra:astra_secure_pass@postgres:5432/astra_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
