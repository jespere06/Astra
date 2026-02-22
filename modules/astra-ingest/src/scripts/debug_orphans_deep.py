import os
import sys
import json
import logging
import numpy as np
from sentence_transformers import SentenceTransformer, util
from tabulate import tabulate

# Ajustar path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from src.mining.extractor import SemanticExtractor

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("DEEP-DEBUG")

# CONFIGURACIÓN
DOCX_PATH = "/Users/jesusandresmezacontreras/projects/astra/minutes/ACTA N° 013 DE ENERO 16 DE 2024 - DTSC Condiciones y atenciones en salud mental.docx"
JSON_PATH = "/Users/jesusandresmezacontreras/projects/astra/cache_test/QHjkSjtiAyc_transcript.json"
THRESHOLD = 0.45 
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

def run_debug():
    # 1. Carga
    with open(JSON_PATH, 'r') as f:
        transcripts = [t for t in json.load(f) if len(t['text'].strip()) > 30]
    
    extractor = SemanticExtractor(static_hashes=set())
    xml_fragments = extractor.extract_from_document(DOCX_PATH)
    xml_fragments = [x for x in xml_fragments if len(x['text']) > 20]

    # 2. IA
    model = SentenceTransformer(MODEL_NAME)
    t_texts = [t['text'] for t in transcripts]
    x_texts = [x['text'] for x in xml_fragments]
    
    t_vecs = model.encode(t_texts, convert_to_tensor=True)
    x_vecs = model.encode(x_texts, convert_to_tensor=True)
    sim_matrix = util.cos_sim(t_vecs, x_vecs).cpu().numpy()

    # 3. Identificar Huérfanos y sus "Casi-Matches"
    matched_t_indices = set()
    for t_idx in range(len(transcripts)):
        if np.max(sim_matrix[t_idx]) >= THRESHOLD:
            matched_t_indices.add(t_idx)

    debug_data = []
    for t_idx, t in enumerate(transcripts):
        if t_idx not in matched_t_indices:
            # Encontrar el mejor fragmento XML que casi hace match
            best_x_idx = int(np.argmax(sim_matrix[t_idx]))
            score = float(sim_matrix[t_idx][best_x_idx])
            
            # Categorización automática del huérfano
            reason = "DESCONOCIDO"
            if score < 0.25:
                reason = "🚫 NO EXISTE EN EL ACTA (Charla informal/Saludo)"
            elif 0.25 <= score < 0.35:
                reason = "📉 SIMILITUD MUY BAJA (Posible mención lateral)"
            elif 0.35 <= score < THRESHOLD:
                reason = "🟡 CASI ENTRA (Threshold muy estricto)"
            
            debug_data.append([
                f"{t['start']:.1f}s",
                t['text'][:150] + "...",
                x_texts[best_x_idx][:100] + "...",
                f"{score:.3f}",
                reason
            ])

    # 4. Imprimir Tabla
    headers = ["Tiempo", "Audio (Lo que se dijo)", "Match más cercano en Acta", "Score", "Diagnóstico"]
    print("\n" + "="*120)
    print(f"🔍 DIAGNÓSTICO DE HUÉRFANOS (Total: {len(debug_data)})")
    print("="*120)
    print(tabulate(debug_data, headers=headers, tablefmt="grid"))
    print("\n💡 Sugerencia: Si los de 'CASI ENTRA' se ven correctos, baja el THRESHOLD a 0.40.")

if __name__ == "__main__":
    run_debug()