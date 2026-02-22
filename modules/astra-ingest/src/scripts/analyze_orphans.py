import os
import sys
import json
import logging
import numpy as np
from sentence_transformers import SentenceTransformer, util
# Eliminamos TfidfVectorizer

# Ajustar path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.mining.extractor import SemanticExtractor

# Configurar Logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ORPHAN-ANALYSIS")

# ================= CONFIGURACIÓN =================
DOCX_PATH = "/Users/jesusandresmezacontreras/projects/astra/minutes/ACTA N° 013 DE ENERO 16 DE 2024 - DTSC Condiciones y atenciones en salud mental.docx"
JSON_PATH = "/Users/jesusandresmezacontreras/projects/astra/cache_test/QHjkSjtiAyc_transcript.json"

# Bajamos un poco el umbral porque estamos comparando resúmenes vs discursos
THRESHOLD = 0.45 
# Modelo multilingüe optimizado para similitud semántica (ignora diferencias de longitud)
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
# =================================================

def load_transcript():
    if not os.path.exists(JSON_PATH):
        logger.error(f"❌ No se encontró el JSON en {JSON_PATH}")
        sys.exit(1)
    with open(JSON_PATH, 'r') as f:
        return json.load(f)

def run_analysis():
    # 1. Cargar Transcripciones (Source)
    transcripts = load_transcript()
    # Filtro más estricto para ignorar "Sí", "Gracias", etc.
    transcripts = [t for t in transcripts if len(t['text'].strip()) > 30]
    logger.info(f"🎤 Cargados {len(transcripts)} segmentos de transcripción sustanciales.")

    # 2. Cargar XML (Target)
    if not os.path.exists(DOCX_PATH):
        logger.error(f"❌ No se encontró el DOCX en {DOCX_PATH}")
        sys.exit(1)

    logger.info("📄 Extrayendo fragmentos del DOCX...")
    extractor = SemanticExtractor(static_hashes=set())
    xml_fragments = extractor.extract_from_document(DOCX_PATH)
    # Filtro para ignorar fragmentos XML muy cortos (nombres sueltos de listas)
    xml_fragments = [x for x in xml_fragments if len(x['text']) > 20]
    logger.info(f"📄 Cargados {len(xml_fragments)} fragmentos XML sustanciales.")

    # 3. Vectorización Neuronal (AQUÍ ESTÁ LA MAGIA)
    logger.info(f"🧠 Cargando modelo neuronal {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    
    t_texts = [t['text'] for t in transcripts]
    x_texts = [x['text'] for x in xml_fragments]
    
    logger.info("🧮 Generando embeddings (esto puede tardar unos segundos)...")
    t_vecs = model.encode(t_texts, convert_to_tensor=True)
    x_vecs = model.encode(x_texts, convert_to_tensor=True)
    
    # Matriz de Similitud Coseno
    sim_matrix = util.cos_sim(t_vecs, x_vecs) # Retorna Tensor [len_t, len_x]

    # 4. Clasificación
    matched_transcript_indices = set()
    matched_xml_indices = set()
    pairs = []

    # Convertir a numpy para iterar fácil
    sim_matrix_np = sim_matrix.cpu().numpy()

    # Estrategia Greedy: Buscar el mejor match global, asignarlo, y repetir
    # Esto evita que un resumen genérico se robe todos los audios
    
    # Aplanamos la matriz para ordenar por score
    # (Esto es simplificado, en prod se usa algoritmo húngaro o max flow, pero esto sirve para test)
    # Iteramos filas (Transcripciones) para ver su mejor XML
    for t_idx in range(len(transcripts)):
        row = sim_matrix_np[t_idx]
        best_x_idx = int(np.argmax(row))
        best_score = float(row[best_x_idx])

        if best_score >= THRESHOLD:
            matched_transcript_indices.add(t_idx)
            matched_xml_indices.add(best_x_idx)
            pairs.append({
                "score": best_score,
                "xml": x_texts[best_x_idx],
                "transcript": t_texts[t_idx]
            })

    # 5. Reporte de Huérfanos
    
    # A. Huérfanos de Audio (Lo importante: ¿Se perdió el discurso?)
    orphan_transcripts = []
    for i, t in enumerate(transcripts):
        if i not in matched_transcript_indices:
            row = sim_matrix_np[i]
            best_attempt_idx = int(np.argmax(row))
            best_attempt_score = float(row[best_attempt_idx])
            orphan_transcripts.append({
                "time": f"{t['start']:.1f}s",
                "text": t['text'],
                "best_match_score": best_attempt_score,
                "best_match_text": x_texts[best_attempt_idx] if x_texts else "N/A"
            })

    # --- IMPRESIÓN ---

    print("\n" + "="*80)
    print(f"📊 ANÁLISIS SEMÁNTICO (Embeddings) | Umbral: {THRESHOLD}")
    print("="*80)
    print(f"✅ Pares Alineados:     {len(pairs)}")
    print(f"🟠 Huérfanos Audio:     {len(orphan_transcripts)}")
    
    print("\n" + "-"*80)
    print("✅ TOP 5 MEJORES MATCHES (Comprobación de realidad)")
    print("-" * 80)
    pairs.sort(key=lambda x: x['score'], reverse=True)
    for p in pairs[:5]:
        print(f"🟢 Score: {p['score']:.3f}")
        print(f"   Audio: {p['transcript'][:100]}...")
        print(f"   XML:   {p['xml'][:100]}...")
        print("")

    print("\n" + "-"*80)
    print("🟠 TOP 10 HUÉRFANOS DE AUDIO (¿Qué se está perdiendo?)")
    print("-" * 80)
    orphan_transcripts.sort(key=lambda x: x['best_match_score'], reverse=True)
    
    for ot in orphan_transcripts[:10]:
        print(f"[{ot['time']}] Score: {ot['best_match_score']:.3f}")
        print(f"   Audio: {ot['text'][:120]}...")
        print(f"   Target más cercano: {ot['best_match_text'][:120]}...")
        print("")

if __name__ == "__main__":
    run_analysis()