
import asyncio
import json
import logging
import sys
import os
import uuid

# Add src to python path
sys.path.append(os.path.join(os.path.dirname(__file__), "../../.."))

from src.infrastructure.qdrant_adapter import QdrantAdapter
from src.nlp.embeddings import EmbeddingService
from src.config import get_settings

# Config logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bootstrap")

async def bootstrap_qdrant():
    settings = get_settings()
    logger.info(f"🚀 Iniciando Bootstrap de Qdrant en {settings.QDRANT_HOST}...")

    # 1. Instanciar Servicios
    # Instanciamos el adaptador que wrappea la lógica de conexión
    adapter = QdrantAdapter() 
    embedder = EmbeddingService()

    if not adapter.client:
        logger.error("❌ Cliente Qdrant no disponible. Abortando bootstrap.")
        return

    # 2. Cargar Seed Data
    seed_path = os.path.join(os.path.dirname(__file__), "templates_seed.json")
    try:
        with open(seed_path, "r") as f:
            templates = json.load(f)
    except FileNotFoundError:
        logger.error(f"❌ Archivo seed no encontrado: {seed_path}")
        return

    tenant_id = "tenant_default" # Tenant de pruebas inicial
    logger.info(f"🌱 Cargando {len(templates)} plantillas para tenant '{tenant_id}'...")

    # 3. Procesar y Vectorizar
    for tpl in templates:
        # Generar embedding del texto crudo
        logger.info(f"Generating vector for: {tpl['id']}")
        vector = embedder.embed(tpl["raw_text"])
        
        # Preparar payload
        # Copiamos para no mutar el tpl original de manera inesperada
        payload = {
            "template_id": tpl["id"],
            "raw_text": tpl["raw_text"],
            "variables": tpl.get("variables", []),
            "metadata": tpl.get("metadata", {}),
            "structure_hash": tpl.get("metadata", {}).get("structure_hash", "")
        }

        # Qdrant Points requieren UUIDs
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, tpl["id"]))

        success = adapter.index_template(
            tenant_id=tenant_id,
            template_id=point_id, # Usamos UUID generado
            text=tpl["raw_text"],
            metadata=payload,
            vector=vector
        )
        
        if success:
             logger.info(f"✅ Indexado: {tpl['id']} -> {point_id}")
        else:
             logger.error(f"❌ Falló indexación: {tpl['id']}")

    logger.info("✨ Bootstrap completado exitosamente.")

if __name__ == "__main__":
    asyncio.run(bootstrap_qdrant())
