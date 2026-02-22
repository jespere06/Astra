import os
import sys
import json
import logging
from pathlib import Path

# Ajustar path para importar módulos internos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.mining.extractor import SemanticExtractor
from src.mining.aligner import SemanticAligner, AlignerConfig # Usará la lógica mejorada que definimos
from src.core.nlp.embedder import TextEmbedder

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ALIGN-TEST-V2")

# CONFIGURACIÓN DE RUTAS REALES SEGÚN TU PROYECTO
BASE_DIR = "/Users/jesusandresmezacontreras/projects/astra"
DOCX_PATH = os.path.join(BASE_DIR, "minutes/ACTA N° 013 DE ENERO 16 DE 2024 - DTSC Condiciones y atenciones en salud mental.docx")
TRANSCRIPT_PATH = os.path.join(BASE_DIR, "cache_test/QHjkSjtiAyc_transcript.json")

def run_test():
    # 1. Cargar Transcripción
    with open(TRANSCRIPT_PATH, 'r') as f:
        full_transcript = json.load(f)
    
    # 2. Extraer fragmentos XML del acta
    # (Usamos el extractor que ya tienes para obtener los targets)
    extractor = SemanticExtractor(static_hashes=set())
    xml_fragments = extractor.extract_from_document(DOCX_PATH)
    
    # 3. Ejecutar el nuevo Aligner (Lógica N-a-1)
    # Bajamos el threshold a 0.40 para capturar resúmenes más agresivos
    aligner = SemanticAligner(config=AlignerConfig(threshold=0.40)) 
    
    logger.info("🚀 Iniciando Test de Alineación Mejorada...")
    pairs = aligner.align(full_transcript, xml_fragments)

    # 4. Mostrar Resultados
    print("\n" + "="*100)
    print(f"📊 RESULTADO DE LA PRUEBA: {len(pairs)} PARES ENCONTRADOS")
    print("="*100)

    for i, p in enumerate(pairs[:10]): # Mostrar los primeros 10
        print(f"\n🔹 PAREJA #{i+1} [Score: {p['score']:.4f}]")
        print(f"🎧 AUDIO (Origen Agrupado):")
        print(f"   {p['input'][:300]}...") # Mostramos el inicio del grupo
        print(f"📄 ACTA (XML Target):")
        # Extraer texto del XML para ver qué dice
        from lxml import etree
        root = etree.fromstring(p['output'])
        text = "".join(root.xpath(".//text()"))
        print(f"   {text[:300]}...")
        print("-" * 50)

if __name__ == "__main__":
    run_test()