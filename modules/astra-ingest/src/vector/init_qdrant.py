import os
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Configuración desde env
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = "templates"
VECTOR_SIZE = 768  # Dimensión del modelo MPNet

def init_vector_db():
    client = QdrantClient(url=QDRANT_URL)
    
    # Verificar si la colección existe
    collections = client.get_collections()
    exists = any(c.name == COLLECTION_NAME for c in collections.collections)

    if not exists:
        print(f"Creando colección '{COLLECTION_NAME}'...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE
            )
        )
        
        # Crear índice para tenant_id (Filtrado rápido Multi-tenant)
        print("Creando índice de payload para 'tenant_id'...")
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="tenant_id",
            field_schema=models.PayloadSchemaType.KEYWORD
        )
        print("Inicialización de Qdrant completada.")
    else:
        print(f"La colección '{COLLECTION_NAME}' ya existe. Saltando creación.")

if __name__ == "__main__":
    try:
        init_vector_db()
    except Exception as e:
        print(f"Error inicializando Qdrant: {e}")
        exit(1)