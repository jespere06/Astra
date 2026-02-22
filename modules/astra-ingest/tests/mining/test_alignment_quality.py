import os
import sys
import json
import logging
import argparse
from pathlib import Path

# Ajustar path para importar módulos internos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.mining.downloader import MediaDownloader
from src.mining.core_client import CoreTranscriptionClient
from src.mining.extractor import SemanticExtractor
from src.mining.aligner import SemanticAligner, AlignerConfig
from src.core.parser.xml_engine import DocxAtomizer
from src.config import settings

# Configurar Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ALIGN-TEST")

# ================= CONFIGURACIÓN =================
CACHE_DIR = "./cache_test"
TENANT_ID = "test_tenant"

# Datos de entrada (Tu caso de prueba)
VIDEO_URL = "https://www.youtube.com/watch?v=QHjkSjtiAyc"
# Nota: Asegúrate de que el nombre del archivo coincida exactamente con el que tienes en disco
DOCX_FILENAME = "ACTA N° 013 DE ENERO 16 DE 2024 - DTSC Condiciones y atenciones en salud mental.docx"
# =================================================

def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

def get_cached_transcript(video_id):
    path = os.path.join(CACHE_DIR, f"{video_id}_transcript.json")
    if os.path.exists(path):
        logger.info(f"🟢 Cache HIT: Transcripción encontrada en {path}")
        with open(path, 'r') as f:
            return json.load(f)
    return None

def save_transcript_cache(video_id, data):
    path = os.path.join(CACHE_DIR, f"{video_id}_transcript.json")
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    logger.info(f"💾 Transcripción cacheada en {path}")

def get_video_id(url):
    """Extrae ID de YouTube simple"""
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    return "video_unknown"

def run_test():
    ensure_cache_dir()
    
    # 1. Obtener Rutas
    # Asumimos que el DOCX está en la carpeta 'minutes' en la raíz del proyecto
    # Ajusta esta ruta si tu archivo está en otro lado
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    docx_path = os.path.join(base_path, "minutes", DOCX_FILENAME)

    if not os.path.exists(docx_path):
        logger.error(f"❌ No se encontró el archivo DOCX en: {docx_path}")
        logger.info("Por favor verifica que el archivo .docx exista en la carpeta 'minutes'.")
        return

    video_id = get_video_id(VIDEO_URL)
    
    # 2. Transcripción (Con Caché)
    segments = get_cached_transcript(video_id)
    
    if not segments:
        logger.info("🔵 Cache MISS: Iniciando descarga y transcripción...")
        
        # A. Descargar y Normalizar
        downloader = MediaDownloader()
        # Esto sube a MinIO/S3 local y retorna la URI
        s3_uri = downloader.download_and_upload(VIDEO_URL, TENANT_ID)
        logger.info(f"Audio subido a: {s3_uri}")

        # B. Transcribir con Deepgram (vía Core Client)
        # Nota: Asegúrate de que astra-core esté corriendo en el puerto 8002
        # o que CoreTranscriptionClient tenga la URL correcta.
        client = CoreTranscriptionClient()
        
        # Si astra-core no está corriendo, este paso fallará. 
        # Si tienes la DEEPGRAM_KEY local, podrías usar el SDK directo aquí como fallback,
        # pero probemos la arquitectura real primero.
        try:
            transcript_result = client.transcribe_url(s3_uri, TENANT_ID, provider="deepgram")
            segments = transcript_result.get("segments", [])
            save_transcript_cache(video_id, segments)
        except Exception as e:
            logger.error(f"❌ Error transcribiendo: {e}")
            logger.info("Asegúrate de que 'astra-core' esté corriendo (npm run dev:core) y tenga DEEPGRAM_API_KEY")
            return

    logger.info(f"✅ Transcripción cargada: {len(segments)} segmentos.")

    # 3. Extracción de XML del DOCX
    logger.info("Parsing DOCX para extraer fragmentos XML...")
    # Usamos un conjunto vacío de hashes estáticos para extraer TODO por ahora y ver qué sale
    extractor = SemanticExtractor(static_hashes=set()) 
    xml_fragments = extractor.extract_from_document(docx_path)
    
    logger.info(f"✅ DOCX procesado: {len(xml_fragments)} fragmentos XML extraídos.")

    # 4. Alineación (El núcleo de la prueba)
    logger.info("🧠 Ejecutando Alineación Semántica (TF-IDF + Cosine)...")
    
    config = AlignerConfig(threshold=0.5)
    aligner = SemanticAligner(config=config)
    
    pairs = aligner.align(segments, xml_fragments)
    
    # 5. Generación de Reporte Visual
    print("\n" + "="*80)
    print(f"📊 REPORTE DE CALIDAD DE ALINEACIÓN")
    print(f"Video: {VIDEO_URL}")
    print(f"Doc: {DOCX_FILENAME}")
    print(f"Pares Encontrados: {len(pairs)}")
    print("="*80 + "\n")

    # Guardar JSONL de salida
    output_jsonl = os.path.join(CACHE_DIR, "dataset_preview.jsonl")
    
    with open(output_jsonl, 'w') as f:
        # Ordenar por score para ver los mejores y peores
        sorted_pairs = sorted(pairs, key=lambda x: x['score'], reverse=True)
        
        for i, pair in enumerate(sorted_pairs):
            # Guardar en archivo
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")
            
            # Imprimir muestra en consola (Top 5, Middle 2, Bottom 2)
            if i < 5 or (len(pairs)//2 <= i < len(pairs)//2 + 2) or i >= len(pairs) - 2:
                score = pair['score']
                icon = "🟢" if score > 0.8 else ("🟡" if score > 0.6 else "🔴")
                
                print(f"{icon} [Score: {score:.4f}]")
                print(f"🎤 INPUT (Transcripción):")
                print(f"   {pair['input'][:200]}...") # Truncar para legibilidad
                print(f"📄 OUTPUT (XML Target):")
                # Limpiar un poco el XML para visualizar el texto contenido
                from lxml import etree
                try:
                    root = etree.fromstring(pair['output'])
                    text_content = "".join(root.xpath(".//text()"))
                    print(f"   XML RAW: {pair['output'][:100]}...")
                    print(f"   TEXTO:   {text_content[:200]}...")
                except:
                    print(f"   {pair['output'][:200]}...")
                print("-" * 50)

    print(f"\n💾 Dataset completo guardado en: {output_jsonl}")
    print("👉 Revisa los casos con 🟡 y 🔴 para ajustar el 'threshold' en SemanticAligner.")

if __name__ == "__main__":
    run_test()