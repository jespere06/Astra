import logging
from typing import List, Dict
from src.core.parser.xml_engine import DocxAtomizer
from src.core.nlp.embedder import TextEmbedder

logger = logging.getLogger(__name__)

class SeedAnchor:
    def __init__(self, text: str, vector: List[float], metadata: Dict = None):
        self.text = text
        self.vector = vector
        self.metadata = metadata or {}

class SeedEngine:
    def __init__(self, embedder: TextEmbedder):
        self.embedder = embedder
        self.anchors: List[SeedAnchor] = []

    def ingest_manual(self, file_path: str):
        """
        Procesa el manual de referencia y genera los anclajes (anchors).
        """
        logger.info(f"📚 Ingestando Manual Maestro: {file_path}")
        
        with DocxAtomizer(file_path) as atomizer:
            content = atomizer.extract_content()
            
            texts_to_embed = []
            valid_metadata = []
            
            for block in content:
                # Solo nos interesan párrafos con contenido semántico
                if block['type'] == 'paragraph' and len(block['text'].strip()) > 10:
                    texts_to_embed.append(block['text'].strip())
                    valid_metadata.append(block['metadata'])
            
            if not texts_to_embed:
                logger.warning("⚠️ No se encontró contenido aprovechable en el manual.")
                return

            # Vectorizar en bloque
            vectors = self.embedder.embed_batch(texts_to_embed)
            
            self.anchors = [
                SeedAnchor(text, vec, meta) 
                for text, vec, meta in zip(texts_to_embed, vectors, valid_metadata)
            ]
            
            logger.info(f"✅ Manual listo con {len(self.anchors)} anclas semánticas.")

    def get_anchors(self) -> List[SeedAnchor]:
        return self.anchors

    def save_anchors_to_db(self, db_session, tenant_id: str):
        """
        Guarda las anclas en la base de datos para persistencia.
        """
        from src.db.models import SeedAnchor
        
        # Limpiar anclas previas para este tenant
        db_session.query(SeedAnchor).filter_by(tenant_id=tenant_id).delete()
        
        for anchor in self.anchors:
            db_anchor = SeedAnchor(
                tenant_id=tenant_id,
                text=anchor.text,
                vector=anchor.vector.tolist() if hasattr(anchor.vector, 'tolist') else anchor.vector,
                label=anchor.metadata.get('label')
            )
            db_session.add(db_anchor)
        
        db_session.commit()
        logger.info(f"✅ {len(self.anchors)} anclas persistidas en DB para el tenant: {tenant_id}")

    def load_anchors_from_db(self, db_session, tenant_id: str):
        """
        Carga las anclas desde la base de datos.
        """
        from src.db.models import SeedAnchor
        db_anchors = db_session.query(SeedAnchor).filter_by(tenant_id=tenant_id).all()
        self.anchors = [
            SeedAnchor(a.text, a.vector, {"label": a.label})
            for a in db_anchors
        ]
        if self.anchors:
            logger.info(f"✅ {len(self.anchors)} anclas cargadas desde DB para el tenant: {tenant_id}")
        return self.anchors
