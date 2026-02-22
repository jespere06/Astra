import hashlib
import logging
from typing import List, Dict
from sqlalchemy.orm import Session
from src.db.models import Skeleton, Template, TableTemplate
from src.core.parser.xml_engine import DocxAtomizer
from src.core.nlp.embedder import TextEmbedder
from src.core.nlp.cleaner import TextSanitizer
from src.core.analytics.cluster_engine import ClusterEngine
from src.core.nlp.alignment_engine import SequenceAligner
from src.core.builder.xml_factory import XmlFactory
from src.core.qa.validator import TemplateValidator
from src.core.nlp.seed_engine import SeedEngine
from src.core.mapping.auto_mapper import HeuristicMapper, BlockOccurrence
from src.core.parser.style_parser import StyleParser
from src.core.parser.style_mapper import StyleMapper
from src.db.repositories import StyleMapRepository
from src.core.admin.label_manager import LabelManager
from src.db.models import EntityType
from src.core.constants import PATH_STYLES
from src.core.utils.storage import StorageManager
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

class IngestOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.embedder = TextEmbedder()
        self.sanitizer = TextSanitizer()
        self.cluster_engine = ClusterEngine()
        self.aligner = SequenceAligner()
        self.xml_factory = XmlFactory()
        self.validator = TemplateValidator()
        self.seed_engine = SeedEngine(self.embedder)
        self.mapper = HeuristicMapper(self.db)
        self.label_manager = LabelManager(self.db)
        self.storage = StorageManager()

    def process_styles(self, file_path: str, tenant_id: str):
        """
        Extrae, mapea y persiste los estilos de un documento.
        Debe ejecutarse antes o durante el procesamiento del batch.
        """
        atomizer = DocxAtomizer(file_path)
        
        try:
            # 1. Extraer XML de estilos
            # Nota: DocxAtomizer tiene _load_xml que parsea styles.xml
            styles_tree = atomizer._load_xml(PATH_STYLES) 
            
            # 2. Parsear
            parser = StyleParser()
            definitions = parser.parse_styles_xml(styles_tree)
            
            # 3. Mapear
            mapper = StyleMapper()
            canonical_map = mapper.map_styles(definitions)
            
            # 4. Persistir
            repo = StyleMapRepository(self.db)
            repo.upsert_mapping(tenant_id, canonical_map)
            
            logger.info(f"Mapa de estilos actualizado para tenant {tenant_id}: {len(canonical_map)} estilos mapeados.")
            
        except Exception as e:
            logger.warning(f"No se pudieron procesar los estilos para {file_path}: {e}")
        finally:
            atomizer.close()

    def process_document(self, file_path: str, tenant_id: str):
        """
        Ejecuta el flujo completo de ingesta para un documento (o lote simulado).
        Nota: En producción, esto procesaría un lote de N documentos. 
        Aquí simulamos la lógica para un documento extrayendo sus propios patrones repetitivos
        o asumiendo que recibimos una lista de paths.
        """
        # Para el ejemplo, procesaremos un solo doc, pero la lógica de clustering
        # idealmente requiere varios docs.
        # Imaginemos que 'file_path' es una lista de archivos para este tenant.
        pass
    
    def process_batch(self, file_paths: List[str], tenant_id: str) -> str:
        """
        Procesa un lote de documentos para inducir plantillas y guardar skeletons.
        """
        all_blocks = []
        doc_maps = {} # file_index -> [block_indices]

        # 1. Extracción y Vectorización Global
        logger.info("Iniciando extracción y vectorización...")
        global_idx = 0
        
        for f_idx, path in enumerate(file_paths):
            atomizer = DocxAtomizer(path)
            content = atomizer.extract_content() # Lista de dicts {id, text, metadata}
            
            doc_block_indices = []
            for b_idx, block in enumerate(content):
                if block['type'] == 'paragraph' and len(block['text']) > 10: # Ignorar textos muy cortos
                    # --- NUEVO: LIMPIEZA Y ANONIMIZACIÓN (Fase 1-T04) ---
                    # Limpiamos el texto antes de vectorizar para que el clustering
                    # agrupe por estructura semántica y no por nombres propios.
                    sanitized_text = self.sanitizer.sanitize(block['text'], anonymize=True)
                    
                    # Vectorizar el texto SANITIZADO
                    vec = self.embedder.embed_batch([sanitized_text])[0]
                    
                    all_blocks.append({
                        "text": block['text'],          # Guardamos original para inducir plantilla
                        "sanitized_text": sanitized_text, # Guardamos limpio para debug/comparación
                        "vector": vec,              # Vector basado en texto limpio
                        "metadata": block['metadata'],
                        "original_doc": path,
                        "node_id": block['id'], # ID interno del DOCX
                        "block_index": b_idx,
                        "total_blocks": len(content)
                    })
                    doc_block_indices.append(global_idx)
                    global_idx += 1
            
            doc_maps[f_idx] = doc_block_indices
            atomizer.close()

        if not all_blocks:
            return "No content found"

        # 2. Anchored Search (Fase 2-T01)
        # Comparar bloques contra las anclas del Manual Maestro
        anchors = self.seed_engine.get_anchors()
        if anchors:
            logger.info(f"🔎 Ejecutando Anchored Search contra {len(anchors)} anclas...")
            anchor_vectors = np.array([a.vector for a in anchors])
            block_vectors = np.array([b['vector'] for b in all_blocks])
            
            # Matriz de similitud coseno
            similarities = cosine_similarity(block_vectors, anchor_vectors)
            
            for i, sim_row in enumerate(similarities):
                best_match_idx = np.argmax(sim_row)
                if sim_row[best_match_idx] > 0.85: # Threshold de anclaje
                    anchor = anchors[best_match_idx]
                    all_blocks[i]['anchor_label'] = f"seed_{best_match_idx}"
                    all_blocks[i]['is_seed_match'] = True
                    # logger.info(f"📍 Bloque anclado a: {anchor.text[:50]}...")

        # Validación de que se encontraron bloques
        if not all_blocks:
             return f"Procesados {len(file_paths)} documentos. No se extrajo contenido válido (posiblemente archivos vacíos o muy cortos)."

        # 3. Clustering
        logger.info("Ejecutando clustering...")
        vectors = [b['vector'] for b in all_blocks]
        clustering_result = self.cluster_engine.perform_clustering(vectors, tenant_id)
        
        # Mapear labels a bloques
        raw_cluster_groups = {}
        for i, label in enumerate(clustering_result.labels):
            # Prioridad: Si está anclado por semilla, forzar un label especial
            if all_blocks[i].get('is_seed_match'):
                label = all_blocks[i]['anchor_label']
            
            if label == -1: continue # Ruido
            if label not in raw_cluster_groups:
                raw_cluster_groups[label] = []
            raw_cluster_groups[label].append(all_blocks[i])

        # 2.1 Fusión Semántica de Clusters (Boilerplate/Textual)
        # Unir clusters que son idénticos ignorando mayúsculas/minúsculas
        cluster_groups = {}
        merged_labels = {} # original_label -> target_label
        
        seen_patterns = {} # lower_text -> label
        
        for label, blocks in raw_cluster_groups.items():
            # Usamos el texto SANITIZADO para la fusión semántica estricta
            # Esto mejora la detección de boilerplate (texto idéntico salvo nombres)
            sample_text = blocks[0]['sanitized_text'].strip().lower()
            
            if sample_text in seen_patterns:
                target_label = seen_patterns[sample_text]
                merged_labels[label] = target_label
                cluster_groups[target_label].extend(blocks)
                logger.info(f"Fusionando cluster {label} en {target_label} (patrón sanitizado idéntico)")
            else:
                seen_patterns[sample_text] = label
                cluster_groups[label] = blocks
                merged_labels[label] = label

        # 3. Inducción de Plantillas y Persistencia
        logger.info("Induciendo plantillas...")
        template_map = {} # cluster_label -> template_db_id

        for label, blocks in cluster_groups.items():
            texts = [b['text'] for b in blocks]
            
            # Generar modelo lógico (Alineación)
            template_model = self.aligner.induce_template(texts)
            
            # Generar Hash de estructura para deduplicación
            struct_hash = hashlib.sha256(template_model.raw_pattern.encode()).hexdigest()
            
            # Determinar si es Boilerplate (0 variables)
            variables = [t.variable_name for t in template_model.tokens if t.is_variable]
            is_boilerplate = len(variables) == 0

            # [NUEVO] Paso de Auto-Resolución de Etiquetas
            auto_label = None
            
            # A. Si viene de una semilla, tiene prioridad (lógica simplificada para Fase 2)
            if str(label).startswith("seed_"):
                auto_label = None # Se mantiene is_seed logic
            else:
                # B. Consultar Catálogo Histórico
                auto_label = self.label_manager.get_label_for_hash(
                    tenant_id, 
                    struct_hash, 
                    EntityType.TEMPLATE
                )

            # Verificar si ya existe en DB
            existing_tmpl = self.db.query(Template).filter_by(
                tenant_id=tenant_id, structure_hash=struct_hash
            ).first()

            if existing_tmpl:
                # Si existe, actualizamos el label y el preview si son nulos
                needs_commit = False
                if auto_label and not existing_tmpl.user_label:
                    existing_tmpl.user_label = auto_label
                    needs_commit = True
                
                if not existing_tmpl.preview_text:
                    existing_tmpl.preview_text = template_model.raw_pattern[:2000]
                    needs_commit = True
                
                if needs_commit:
                    self.db.commit()
                template_map[label] = str(existing_tmpl.id)
            else:
                # Generar XML físico usando el primer bloque como referencia de estilo
                ref_doc_path = blocks[0]['original_doc']
                ref_node_id = blocks[0]['node_id']
                
                with DocxAtomizer(ref_doc_path) as atm:
                    ns = atm.namespaces
                    w = f"{{{ns['w']}}}"
                    nodes = atm.document_tree.xpath(f'//*[@w:rsidR="{ref_node_id}"]', namespaces=ns)
                    ref_node = nodes[0] if nodes else None
                    
                    if ref_node is not None:
                        xml_bytes = self.xml_factory.generate_ooxml_template(template_model, ref_node)
                        
                        # VALIDACIÓN DE CALIDAD (Fase 1-T07.2)
                        is_valid, reason = self.validator.validate(
                            template_model.raw_pattern, 
                            len(blocks), 
                            xml_bytes,
                            tenant_id=tenant_id
                        )
                        
                        if not is_valid:
                            logger.warning(f"Plantilla RECHAZADA por calidad ({reason}): {template_model.raw_pattern[:50]}...")
                            continue

                        s3_key = f"s3://astra-templates/{tenant_id}/{struct_hash}.xml"
                        
                        # PERSISTENCIA FÍSICA (Fase 1-T11.2)
                        tmpl_upload_res = self.storage.upload_bytes(xml_bytes, s3_key)
                        s3_key = tmpl_upload_res["uri"]

                        new_tmpl = Template(
                            tenant_id=tenant_id,
                            structure_hash=struct_hash,
                            storage_path=s3_key,
                            variables_metadata=variables,
                            cluster_source_id=str(label),
                            preview_text=template_model.raw_pattern[:2000],
                            is_boilerplate=is_boilerplate,
                            is_seed=str(label).startswith("seed_"),
                            seed_label=str(label) if str(label).startswith("seed_") else None,
                            user_label=auto_label
                        )
                        self.db.add(new_tmpl)
                        self.db.commit()
                        
                        if auto_label:
                            logger.info(f"🤖 AUTO-LABELED: Template {new_tmpl.id} reconocido como '{auto_label}'")

                        template_map[label] = str(new_tmpl.id)
                
                # 3.1 MAPEO DE ZONAS (Fase 1-T07.1a)
                # Calcular ocurrencias para este cluster
                occurrences = [
                    BlockOccurrence(
                        doc_id=b['original_doc'], 
                        block_index=b['block_index'], 
                        total_blocks=b['total_blocks']
                    ) for b in blocks
                ]
                self.mapper.process_mapping(tenant_id, template_map[label], occurrences)

        # 4. Construcción de Skeletons (JSON)
        logger.info("Construyendo Skeletons...")
        # Corregir mapeo de labels originales a los fusionados
        final_labels = []
        for l in clustering_result.labels:
            final_labels.append(merged_labels.get(l, -1))
        
        for f_idx, path in enumerate(file_paths):
            block_indices = doc_maps[f_idx]
            skeleton_structure = []
            
            for b_idx in block_indices:
                original_label = clustering_result.labels[b_idx]
                label = merged_labels.get(original_label, -1)
                block_data = all_blocks[b_idx]
                
                if label != -1 and label in template_map:
                    # Es una plantilla
                    skeleton_structure.append({
                        "type": "template",
                        "template_id": template_map[label]
                    })
                else:
                    # Es ruido / texto estático
                    skeleton_structure.append({
                        "type": "static_text",
                        "content": block_data['text']
                    })
            
            # Guardar Skeleton en DB
            skel_hash = hashlib.sha256(str(skeleton_structure).encode()).hexdigest()
            
            existing_skel = self.db.query(Skeleton).filter_by(
                tenant_id=tenant_id, content_hash=skel_hash
            ).first()

            if not existing_skel:
                # 4.1 [NUEVO] Generar y Persistir Esqueleto OOXML Físico (Fase 1-T11.2)
                ooxml_path = None
                ooxml_version_id = None
                
                with DocxAtomizer(path) as atm:
                    # Este método ahora inyecta anclas y CAPTURA tablas dinámicas
                    skel_tree = atm.get_skeleton_tree()
                    ooxml_bytes = atm.to_string(skel_tree)
                    
                    # A. Guardar Esqueleto OOXML
                    ooxml_key = f"s3://astra-skeletons/{tenant_id}/{skel_hash}.xml"
                    
                    # [MODIFICADO] Capturar respuesta estructurada de almacenamiento (Fase 1-T13)
                    upload_result = self.storage.upload_bytes(ooxml_bytes, ooxml_key)
                    ooxml_path = upload_result["uri"]
                    ooxml_version_id = upload_result.get("version_id")
                    
                    if ooxml_version_id:
                        logger.info(f"Pinned Skeleton version: {ooxml_version_id}")
                    
                    # B. Guardar Tablas Dinámicas (Row Templates)
                    for astra_id, table_xml in atm.dynamic_tables.items():
                        table_key = f"s3://astra-templates/tables/{astra_id}.xml"
                        
                        # [MODIFICADO] Adaptarse al nuevo tipo de retorno
                        table_upload_res = self.storage.upload_bytes(table_xml, table_key)
                        
                        # Registrar en DB
                        if not self.db.query(TableTemplate).filter_by(id=astra_id).first():
                            new_table_tmpl = TableTemplate(
                                id=astra_id,
                                tenant_id=tenant_id,
                                storage_path=table_upload_res["uri"]
                            )
                            self.db.add(new_table_tmpl)
                    
                    self.db.commit()

                new_skel = Skeleton(
                    tenant_id=tenant_id,
                    s3_path=f"s3://astra-skeletons/{tenant_id}/{skel_hash}.json",
                    ooxml_path=ooxml_path,
                    # [NUEVO] Persistencia del Version ID (Fase 1-T13)
                    s3_version_id=ooxml_version_id,
                    meta_xml=skeleton_structure,
                    content_hash=skel_hash
                )
                self.db.add(new_skel)
                self.db.commit()
                logger.info(f"Skeleton OOXML y JSON guardados para {path} (Version: {ooxml_version_id})")

        return f"Procesamiento completado. Plantillas detectadas: {len(template_map)}"
