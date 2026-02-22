import os
import sys
import json
import logging
import time
from datetime import datetime
from pathlib import Path

# Ajustar path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.mining.extractor import SemanticExtractor
from src.mining.aligner import SemanticAligner, AlignerConfig
from src.config import settings

# --- CONFIGURACIÓN DEL TEST ---
BASE_DIR = "/Users/jesusandresmezacontreras/projects/astra"
DOCX_PATH = os.path.join(BASE_DIR, "minutes/ACTA N° 013 DE ENERO 16 DE 2024 - DTSC Condiciones y atenciones en salud mental.docx")
TRANSCRIPT_PATH = os.path.join(BASE_DIR, "cache_test/QHjkSjtiAyc_transcript.json")
REPORT_OUTPUT_DIR = os.path.join(BASE_DIR, "_reports")
# Umbral ajustado para la estrategia inversa
THRESHOLD = 0.35 

os.makedirs(REPORT_OUTPUT_DIR, exist_ok=True)

def generate_report():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(REPORT_OUTPUT_DIR, f"alignment_report_{timestamp}.txt")
    
    print(f"🚀 Iniciando análisis completo (Estrategia Inversa)...")
    start_time = time.time()

    # 1. Cargar Datos
    print("📂 Cargando transcripción...")
    with open(TRANSCRIPT_PATH, 'r') as f:
        full_transcript = json.load(f)
    
    print("📄 Extrayendo XML del DOCX...")
    extractor = SemanticExtractor(static_hashes=set())
    xml_fragments = extractor.extract_from_document(DOCX_PATH)
    # Filtro de longitud mínima para XML
    xml_fragments = [x for x in xml_fragments if len(x['text']) > 15]

    # 2. Ejecutar Alineación
    print("🧠 Ejecutando Alineación Audio-Driven...")
    config = AlignerConfig(threshold=THRESHOLD)
    aligner = SemanticAligner(config=config)
    pairs = aligner.align(full_transcript, xml_fragments)
    
    duration = time.time() - start_time
    
    # 3. Calcular Huérfanos
    used_xml_indices = set()
    used_audio_indices = set()
    
    for p in pairs:
        meta = p['metadata']
        
        # Recorrer todos los XMLs agrupados
        if 'xml_indices' in meta:
            for x_idx in meta['xml_indices']:
                used_xml_indices.add(x_idx)
        else:
            used_xml_indices.add(meta.get('xml_index'))
            
        # Recorrer todos los Audios agrupados
        # CORRECCIÓN: La clave real en aligner.py es 'audio_chunk_indices'
        if 'audio_chunk_indices' in meta:
            for idx in meta['audio_chunk_indices']:
                used_audio_indices.add(idx)
        elif 'audio_indices' in meta: # Fallback por si acaso
            for idx in meta['audio_indices']:
                used_audio_indices.add(idx)
        elif 'audio_start_idx' in meta: 
            for i in range(meta['audio_start_idx'], meta['audio_end_idx']):
                used_audio_indices.add(i)
            
    # Identificar Huérfanos XML
    orphan_xml = []
    for idx, node in enumerate(xml_fragments):
        if idx not in used_xml_indices:
            orphan_xml.append({"idx": idx, "text": node["text"]})
            
    # Identificar Huérfanos Audio
    orphan_audio = []
    for idx, seg in enumerate(full_transcript):
        if idx not in used_audio_indices:
            orphan_audio.append({"idx": idx, "time": seg.get('start', 0), "text": seg.get('text', '')})

    # 4. Escribir Reporte
    print(f"📝 Escribiendo reporte en: {report_file}")
    
    with open(report_file, "w", encoding="utf-8") as f:
        # HEADER
        f.write("================================================================================\n")
        f.write(f"📊 REPORTE DE CALIDAD DE ALINEACIÓN ASTRA (INVERSA)\n")
        f.write(f"Fecha: {datetime.now().isoformat()}\n")
        f.write("================================================================================\n\n")
        
        # METADATOS
        f.write("1. METADATOS DE EJECUCIÓN\n")
        f.write(f"   - Duración: {duration:.2f} s\n")
        f.write(f"   - Total XML: {len(xml_fragments)}\n")
        f.write(f"   - Total Audio: {len(full_transcript)}\n")
        f.write(f"   - Umbral: {THRESHOLD}\n\n")
        
        # RESUMEN
        coverage_xml = (len(used_xml_indices) / len(xml_fragments)) * 100 if xml_fragments else 0
        coverage_audio = (len(used_audio_indices) / len(full_transcript)) * 100 if full_transcript else 0
        
        f.write("2. RESUMEN DE COBERTURA\n")
        f.write(f"   - ✅ Pares Encontrados: {len(pairs)}\n")
        f.write(f"   - 📈 Cobertura XML: {coverage_xml:.1f}%\n")
        f.write(f"   - 📈 Cobertura Audio: {coverage_audio:.1f}%\n\n")
        
        # DETALLE DE PARES
        f.write("3. MUESTRA DE PARES (Top 50)\n")
        f.write("================================================================================\n")
        
        # Mostrar solo los primeros 20 pares
        limit_pairs = pairs[:50]
        for i, p in enumerate(limit_pairs):
            audio_secs = p['metadata'].get('end_time', 0) - p['metadata'].get('start_time', 0)
            f.write(f"\n🔹 PAREJA #{i+1} [Score: {p['score']:.4f}]\n")
            f.write(f"   INPUT (Audio ~{audio_secs:.1f} segs):\n")
            f.write(f"   {p['input'][:300]}...\n")
            f.write(f"   OUTPUT (XML Target):\n")
            
            # Limpiar XML para lectura humana
            from lxml import etree
            try:
                root = etree.fromstring(p['output'])
                text_content = "".join(root.xpath(".//text()")).strip()
                f.write(f"   {text_content[:300]}...\n")
            except:
                f.write(f"   (XML raw)\n")
            f.write("-" * 80 + "\n")
            
        if len(pairs) > 50:
            f.write(f"\n... y {len(pairs) - 50} pares más (ocultos por brevedad).\n")

        # HUÉRFANOS XML
        f.write("\n================================================================================\n")
        f.write(f"4. HUÉRFANOS DE XML ({len(orphan_xml)} bloques sin audio asociado)\n")
        f.write("   * Bloques de texto que no encontraron correspondencia en el audio.\n")
        f.write("================================================================================\n")
        for ox in orphan_xml[:300]: # Limitamos a 300 para no inundar el log
            f.write(f"   [Idx {ox['idx']}] {ox['text'][:150]}...\n")
        if len(orphan_xml) > 300:
             f.write(f"   ... y {len(orphan_xml) - 300} más.\n")
            
        # HUÉRFANOS AUDIO
        f.write("\n================================================================================\n")
        f.write(f"5. HUÉRFANOS DE AUDIO ({len(orphan_audio)} segmentos no usados)\n")
        f.write("   * Segmentos de audio que no se asignaron a ningún párrafo del acta.\n")
        f.write("================================================================================\n")
        
        # Agrupar huérfanos consecutivos para visualización limpia
        if orphan_audio:
            current_group = [orphan_audio[0]]
            for i in range(1, len(orphan_audio)):
                prev = orphan_audio[i-1]
                curr = orphan_audio[i]
                # Si son consecutivos en índice, agrupar
                if curr['idx'] == prev['idx'] + 1:
                    current_group.append(curr)
                else:
                    _write_audio_group(f, current_group)
                    current_group = [curr]
            _write_audio_group(f, current_group)

    print(f"✅ Reporte finalizado. Abrir: {report_file}")

def _write_audio_group(f, group):
    if not group: return
    start_t = group[0]['time']
    # Estimación de fin si no tenemos el dato exacto del siguiente
    end_t = group[-1]['time'] + 5.0 
    text = " ".join([g['text'] for g in group])
    f.write(f"   [{start_t:.1f}s -> ~{end_t:.1f}s] ({len(group)} segs): {text[:200]}...\n")

if __name__ == "__main__":
    generate_report()