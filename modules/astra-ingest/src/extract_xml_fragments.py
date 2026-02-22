import os
import sys
import hashlib
import logging
import shutil
from src.db.base import SessionLocal
from src.core.ingest_orchestrator import IngestOrchestrator
from src.core.parser.xml_engine import DocxAtomizer

# Inyectar path para encontrar 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def generate_physical_xml_files():
    minutes_dir = "/Users/jesusandresmezacontreras/projects/astra/minutes"
    output_dir = "/Users/jesusandresmezacontreras/projects/astra/modules/astra-ingest/minutes-templates"
    
    # Limpiar directorio de salida para evitar confusión con runs anteriores
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Preparar docs (los mismos 10 de la prueba anterior)
    docx_files = [os.path.join(minutes_dir, f) for f in os.listdir(minutes_dir) if f.endswith('.docx')]
    test_files = docx_files[:10]
    
    db = SessionLocal()
    manual_path = "/Users/jesusandresmezacontreras/projects/astra/minutes-txt/Formato actas 2025.docx"
    tenant_id = "concejo_manizales_seed_mastering"
    try:
        orchestrator = IngestOrchestrator(db)
        # Ingestar manual
        orchestrator.seed_engine.ingest_manual(manual_path)
        
        # Re-ejecutar extracción y clustering localmente para obtener los modelos
        all_blocks = []
        for path in test_files:
            with DocxAtomizer(path) as atm:
                content = atm.extract_content()
                for block in content:
                    if block['type'] == 'paragraph' and len(block['text']) > 15:
                        all_blocks.append({
                            "text": block['text'],
                            "original_doc": path,
                            "node_id": block['id'],
                            "vector": orchestrator.embedder.embed_batch([block['text']])[0]
                        })

        if not all_blocks:
            print("No blocks found.")
            return

        # Clustering
        vectors = [b['vector'] for b in all_blocks]
        clustering_result = orchestrator.cluster_engine.perform_clustering(vectors, tenant_id)
        
        # Mapear labels a bloques (Raw)
        raw_cluster_groups = {}
        for i, label in enumerate(clustering_result.labels):
            if label == -1: continue
            if label not in raw_cluster_groups: raw_cluster_groups[label] = []
            raw_cluster_groups[label].append(all_blocks[i])

        # Fusión Semántica (Igual que en Orchestrator)
        cluster_groups = {}
        seen_patterns = {}
        for label, blocks in raw_cluster_groups.items():
            sample_text = blocks[0]['text'].strip().lower()
            if sample_text in seen_patterns:
                target_label = seen_patterns[sample_text]
                cluster_groups[target_label].extend(blocks)
            else:
                seen_patterns[sample_text] = label
                cluster_groups[label] = blocks

        print(f"✅ Evaluando {len(cluster_groups)} clusters con la Valla de Calidad...")

        saved_count = 0
        for label, blocks in cluster_groups.items():
            texts = [b['text'] for b in blocks]
            template_model = orchestrator.aligner.induce_template(texts)
            
            # Usar el primer bloque para estilos
            ref_path = blocks[0]['original_doc']
            ref_node_id = blocks[0]['node_id']
            
            with DocxAtomizer(ref_path) as atm:
                ns = atm.namespaces
                nodes = atm.document_tree.xpath(f'//*[@w:rsidR="{ref_node_id}"]', namespaces=ns)
                ref_node = nodes[0] if nodes else None
                
                if ref_node is not None:
                    xml_bytes = orchestrator.xml_factory.generate_ooxml_template(template_model, ref_node)
                    
                    # VALIDACIÓN DE CALIDAD ASTRA
                    is_valid, reason = orchestrator.validator.validate(
                        template_model.raw_pattern,
                        len(blocks),
                        xml_bytes,
                        tenant_id=tenant_id
                    )
                    
                    if not is_valid:
                        continue

                    # Guardar con hash como nombre
                    struct_hash = hashlib.sha256(template_model.raw_pattern.encode()).hexdigest()[:12]
                    filename = f"template_c{label}_{struct_hash}.xml"
                    file_path = os.path.join(output_dir, filename)
                    
                    with open(file_path, "wb") as f:
                        f.write(xml_bytes)
                    
                    saved_count += 1
                    print(f"📄 [{saved_count}] Guardado: {filename} | Variables: {template_model.raw_pattern[:100]}...")

    finally:
        db.close()

if __name__ == "__main__":
    generate_physical_xml_files()
