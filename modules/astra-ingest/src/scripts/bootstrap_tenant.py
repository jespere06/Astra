import os
import sys
import logging
import argparse
import uuid
import hashlib
from typing import List, Dict
from tqdm import tqdm
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime

# Setup path to import src modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.db.base import SessionLocal
from src.db.models import TenantConfig
from src.core.parser.xml_engine import DocxAtomizer
from src.core.nlp.embedder import TextEmbedder
from src.core.extractors import EntityExtractor
from src.vector.client import get_qdrant_client
from src.config import settings
from src.mining.pipeline import DataMiningPipeline
from qdrant_client.http import models

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ASTRA-BOOTSTRAP")

class TenantBootstrapper:
    def __init__(self, tenant_id: str, source_dir: str, transcripts_dir: str = None, dataset_output: str = None):
        self.tenant_id = tenant_id
        self.source_dir = source_dir
        self.transcripts_dir = transcripts_dir
        self.dataset_output = dataset_output
        self.db = SessionLocal()
        self.qdrant = get_qdrant_client()
        self.embedder = TextEmbedder()
        self.extractor = EntityExtractor()
        
        self.collection_name = "templates" # Usamos la colección principal de conocimiento
        self.vector_size = 768
        self.batch_size = 50 # Puntos por lote a Qdrant

    def _init_qdrant_collection(self):
        """Asegura que la colección exista."""
        collections = self.qdrant.get_collections()
        exists = any(c.name == self.collection_name for c in collections.collections)
        if not exists:
            logger.info(f"Creando colección {self.collection_name}...")
            self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE
                )
            )

    def _get_file_hash(self, filepath: str) -> str:
        """Calcula SHA256 del archivo para idempotencia."""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def process_files(self):
        self._init_qdrant_collection()
        
        files = [f for f in os.listdir(self.source_dir) if f.endswith(".docx")]
        logger.info(f"📂 Encontrados {len(files)} documentos en {self.source_dir}")

        total_points_uploaded = 0
        total_entities_found = 0
        
        # Diccionario acumulado en memoria
        current_entities = {}
        
        # Intentar cargar diccionario existente
        existing_config = self.db.query(TenantConfig).filter_by(tenant_id=self.tenant_id).first()
        if existing_config and existing_config.entities_dictionary:
            current_entities = existing_config.entities_dictionary
            logger.info(f"Cargadas {len(current_entities)} entidades existentes de la DB.")

        points_buffer = []

        for filename in tqdm(files, desc="Procesando Documentos"):
            filepath = os.path.join(self.source_dir, filename)
            
            try:
                # 1. Parsear Documento
                atomizer = DocxAtomizer(filepath)
                content_blocks = atomizer.extract_content()
                
                # 2. Filtrar y Procesar Bloques
                valid_texts = []
                metadatas = []
                
                for block in content_blocks:
                    text = block['text'].strip()
                    
                    # Filtros de Calidad
                    if len(text) < 20: continue # Muy corto
                    if text.isdigit(): continue # Solo números
                    
                    valid_texts.append(text)
                    metadatas.append(block['metadata'])
                    
                    # 3. Extracción de Entidades (Heurística)
                    new_entities = self.extractor.extract_entities(text)
                    if new_entities:
                        current_entities = self.extractor.merge_dictionaries(current_entities, new_entities)
                        total_entities_found += len(new_entities)

                if not valid_texts:
                    continue

                # 4. Generar Embeddings (Batch por documento)
                vectors = self.embedder.embed_batch(valid_texts)

                # 5. Preparar Puntos Qdrant
                for text, vector, meta in zip(valid_texts, vectors, metadatas):
                    # ID Determinista: Tenant + Texto Hash
                    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{self.tenant_id}-{text}"))
                    
                    payload = {
                        "text": text,
                        "tenant_id": self.tenant_id,
                        "source_file": filename,
                        "style": meta.get('style', 'Normal'),
                        "is_seed": True # Marca de origen histórico
                    }
                    
                    points_buffer.append(models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload
                    ))

                # 6. Flush Buffer si es necesario
                if len(points_buffer) >= self.batch_size:
                    self.qdrant.upsert(
                        collection_name=self.collection_name,
                        points=points_buffer
                    )
                    total_points_uploaded += len(points_buffer)
                    points_buffer = []

            except Exception as e:
                logger.error(f"Error procesando {filename}: {e}")
                continue

        # Flush final de vectores
        if points_buffer:
            self.qdrant.upsert(
                collection_name=self.collection_name,
                points=points_buffer
            )
            total_points_uploaded += len(points_buffer)

        # 7. Guardar Entidades en Postgres
        logger.info(f"Guardando {len(current_entities)} entidades en Postgres...")
        
        stmt = insert(TenantConfig).values(
            tenant_id=self.tenant_id,
            entities_dictionary=current_entities
        ).on_conflict_do_update(
            index_elements=['tenant_id'],
            set_={'entities_dictionary': current_entities, 'updated_at': datetime.utcnow()}
        )
        
        self.db.execute(stmt)
        self.db.commit()
        
        # Reporte Final
        logger.info("="*40)
        logger.info("RESUMEN DE BOOTSTRAP")
        logger.info(f"Tenant ID: {self.tenant_id}")
        logger.info(f"Docs Procesados: {len(files)}")
        logger.info(f"Vectores Indexados: {total_points_uploaded}")
        logger.info(f"Entidades en Diccionario: {len(current_entities)}")
        logger.info("="*40)
        
        # 8. Data Mining Pipeline (Optional)
        if self.transcripts_dir and os.path.exists(self.transcripts_dir):
            logger.info("🚀 Iniciando Pipeline de Minería de Datos (DataMiningPipeline)...")
            output_path = self.dataset_output or os.path.join(self.source_dir, "../dataset")
            try:
                pipeline = DataMiningPipeline(
                    docs_dir=self.source_dir,
                    transcripts_dir=self.transcripts_dir,
                    output_dir=output_path
                )
                pipeline.run()
                logger.info(f"✅ Dataset guardado en: {output_path}")
            except Exception as e:
                logger.error(f"❌ Error en DataMiningPipeline: {e}")
        else:
            if self.transcripts_dir:
                logger.warning(f"⚠️ Directorio de transcripciones no encontrado: {self.transcripts_dir}")

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="ASTRA Tenant Bootstrap Tool")
    parser.add_argument("--tenant_id", required=True, help="ID único del inquilino")
    parser.add_argument("--source_dir", required=True, help="Directorio con archivos .docx")
    parser.add_argument("--transcripts_dir", required=False, help="Directorio con archivos .json (transcripciones)")
    parser.add_argument("--dataset_output", required=False, help="Directorio de salida para el dataset")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.source_dir):
        logger.error(f"El directorio {args.source_dir} no existe.")
        sys.exit(1)
        
    bootstrapper = TenantBootstrapper(
        args.tenant_id, 
        args.source_dir, 
        transcripts_dir=args.transcripts_dir, 
        dataset_output=args.dataset_output
    )
    bootstrapper.process_files()
