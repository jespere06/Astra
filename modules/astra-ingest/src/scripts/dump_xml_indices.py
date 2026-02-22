import os
import sys
from lxml import etree

# Ajustar path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.mining.extractor import SemanticExtractor

BASE_DIR = "/Users/jesusandresmezacontreras/projects/astra"
DOCX_PATH = os.path.join(BASE_DIR, "minutes/ACTA N° 013 DE ENERO 16 DE 2024 - DTSC Condiciones y atenciones en salud mental.docx")
OUTPUT_PATH = os.path.join(BASE_DIR, "_reports/xml_indices_dump.txt")

def dump_indices():
    print(f"📄 Extrayendo fragmentos de: {os.path.basename(DOCX_PATH)}")
    
    # Usar el extractor para obtener los fragmentos dinámicos
    extractor = SemanticExtractor(static_hashes=set())
    fragments = extractor.extract_from_document(DOCX_PATH)
    
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("================================================================================\n")
        f.write(f"DUMP DE ÍNDICES XML (IDx) - ASTRA\n")
        f.write(f"Documento: {os.path.basename(DOCX_PATH)}\n")
        f.write(f"Total fragmentos: {len(fragments)}\n")
        f.write("================================================================================\n\n")
        
        for frag in fragments:
            idx = frag['index']
            text = frag['text'].strip()
            
            f.write(f"[{idx:03}] {text}\n")
            f.write("-" * 40 + "\n")

    print(f"✅ Dump completado. Archivo generado en: {OUTPUT_PATH}")

if __name__ == "__main__":
    dump_indices()
