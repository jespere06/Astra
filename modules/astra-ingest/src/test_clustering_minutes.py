import os
import sys
import logging

# Inyectar el path del proyecto para encontrar el módulo 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.parser.xml_engine import DocxAtomizer
from src.core.nlp.embedder import TextEmbedder
from src.core.analytics.cluster_engine import ClusterEngine

# Configuración de Logging
logging.basicConfig(level=logging.ERROR) # Solo errores para limpiar la salida
logger = logging.getLogger(__name__)

def run_integration_test():
    minutes_dir = "/Users/jesusandresmezacontreras/projects/astra/minutes"
    if not os.path.exists(minutes_dir):
        print(f"❌ No se encontró el directorio: {minutes_dir}")
        return

    # 1. Inicializar Componentes
    embedder = TextEmbedder()
    engine = ClusterEngine()
    
    document_vectors = []
    file_names = []
    
    # 2. Procesar todos los documentos de la carpeta
    docx_files = [f for f in os.listdir(minutes_dir) if f.endswith('.docx')]
    
    # Limitamos a 40 para un reporte manejable pero representativo
    docx_files = docx_files[:40]
    
    print(f"📂 Analizando {len(docx_files)} documentos de actas...")
    
    for filename in docx_files:
        path = os.path.join(minutes_dir, filename)
        try:
            atomizer = DocxAtomizer(path)
            content = atomizer.extract_content()
            full_text = " ".join([item['text'] for item in content if 'text' in item])
            
            if full_text.strip():
                vector = embedder.embed_batch([full_text])[0]
                document_vectors.append(vector)
                file_names.append(filename)
            
        except Exception:
            pass

    if not document_vectors:
        print("❌ No se pudieron generar vectores.")
        return

    # 3. Clustering
    result = engine.perform_clustering(document_vectors, tenant_id="test_minutes_tenant")
    
    # 4. Reporte Detallado
    print("\n" + "═"*60)
    print("📊 REPORTE DE INTELIGENCIA COMERCIAL - ASTRA ANALYTICS")
    print("═"*60)
    print(f"➤ Cantidad de Documentos: {result.total_samples}")
    print(f"➤ Patrones (Clusters) Unicos: {result.num_clusters}")
    print(f"➤ Documentos Atípicos (Ruido): {result.noise_count}")
    print(f"➤ Coherencia Semántica (Score): {result.silhouette_score:.4f}")
    print("─"*60)
    
    clusters_found = {}
    for i, label in enumerate(result.labels):
        if label not in clusters_found:
            clusters_found[label] = []
        clusters_found[label].append(file_names[i])
        
    for cluster_id, files in clusters_found.items():
        if cluster_id == -1:
            header = "🔸 DOCUMENTOS ATÍPICOS (Variedad alta)"
        else:
            header = f"🔹 CLUSTER #{cluster_id} (Patrón Detectado)"
            
        print(f"\n{header} [{len(files)} docs]:")
        for f in files[:8]:
            print(f"  • {f[:70]}...")
        if len(files) > 8:
            print(f"  ... (+{len(files)-8} documentos más)")
            
    print("\n" + "═"*60)

if __name__ == "__main__":
    run_integration_test()
