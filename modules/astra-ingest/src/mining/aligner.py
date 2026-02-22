import logging
import numpy as np
import os
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from sklearn.metrics.pairwise import cosine_similarity
from numba import njit

from src.core.nlp.embedder import TextEmbedder
from src.mining.semantic_chunker import EnterpriseSemanticChunker

logger = logging.getLogger(__name__)

# ==========================================
# CONFIGURACIÓN
# ==========================================
class AlignerConfig(BaseModel):
    threshold: float = Field(0.35, description="Similitud mínima")
    gap_penalty_base: float = Field(0.0, description="Penalización por saltos (Desactivada)")
    merge_discount: float = Field(1.0, description="Descuento al fusionar (Desactivado)")

# ==========================================
# DEBUGGER INTERNO
# ==========================================
def dump_debug_matrix(S: np.ndarray, filename="debug_similarity_matrix.csv"):
    """Guarda la matriz cruda para inspección en Excel/Numbers"""
    try:
        # Guardamos solo una subsección si es muy grande para no llenar el disco
        rows, cols = S.shape
        limit_r, limit_c = min(rows, 100), min(cols, 100)
        
        # Guardar CSV
        np.savetxt(filename, S[:limit_r, :limit_c], delimiter=",", fmt='%.4f')
        logger.info(f"🐛 [DEBUG] Matriz de Similitud (parcial {limit_r}x{limit_c}) guardada en: {filename}")
        
        # Estadísticas
        logger.info(f"🐛 [DEBUG] Estadísticas Matriz S: Max={np.max(S):.4f}, Min={np.min(S):.4f}, Mean={np.mean(S):.4f}")
        
        # Histograma ASCII rápido
        counts, bins = np.histogram(S, bins=5, range=(0,1))
        logger.info(f"🐛 [DEBUG] Histograma de Similitud: {list(zip(np.round(bins, 2), counts))}")
        
    except Exception as e:
        logger.error(f"Error dumping debug matrix: {e}")

# ==========================================
# KERNEL NUMBA
# ==========================================
@njit
def compute_dp_matrix(S: np.ndarray, threshold: float, gap_pen: float, merge_disc: float):
    N, M = S.shape
    DP = np.zeros((N + 1, M + 1), dtype=np.float32)
    pointers = np.zeros((N + 1, M + 1), dtype=np.int32) 
    
    MATCH = 0; MERGE_AUDIO = 1; MERGE_XML = 2; SKIP_AUDIO = 3; SKIP_XML = 4

    # Inicialización laxa (sin penalización fuerte al inicio)
    for i in range(1, N + 1):
        DP[i, 0] = 0 # No penalizar saltar audios iniciales
        pointers[i, 0] = SKIP_AUDIO
    for j in range(1, M + 1):
        DP[0, j] = 0 # No penalizar saltar XMLs iniciales (raro, pero posible)
        pointers[0, j] = SKIP_XML

    # Relleno
    for i in range(1, N + 1):
        for j in range(1, M + 1):
            sim = S[i-1, j-1]
            
            # Boost local: Si supera el umbral, lo premiamos. Si no, lo penalizamos poco.
            score_gain = sim if sim >= threshold else -0.1

            s_match   = DP[i-1, j-1] + score_gain
            # Permitir agrupamiento sin costo
            s_merge_a = DP[i-1, j]   + (score_gain * merge_disc) 
            s_merge_x = DP[i, j-1]   + (score_gain * merge_disc) 
            
            # Saltos cuestan muy poco o nada
            s_skip_a  = DP[i-1, j]   - gap_pen
            s_skip_x  = DP[i, j-1]   - gap_pen

            best_s = s_match
            best_ptr = MATCH
            
            if s_merge_a > best_s: best_s = s_merge_a; best_ptr = MERGE_AUDIO
            if s_merge_x > best_s: best_s = s_merge_x; best_ptr = MERGE_XML
            if s_skip_a > best_s:  best_s = s_skip_a;  best_ptr = SKIP_AUDIO
            if s_skip_x > best_s:  best_s = s_skip_x;  best_ptr = SKIP_XML
            
            DP[i, j] = best_s
            pointers[i, j] = best_ptr

    return DP, pointers

# ==========================================
# ALINEADOR
# ==========================================
class SemanticAligner:
    def __init__(self, config: AlignerConfig = None):
        self.config = config or AlignerConfig()
        self.embedder = TextEmbedder()
        self.chunker = EnterpriseSemanticChunker(
            min_duration_sec=10.0, 
            soft_max_duration_sec=40.0
        )

    def align(self, transcript_segments: List, xml_nodes: List) -> List[Dict[str, Any]]:
        # 1. Validaciones de Entrada
        logger.info(f"🔍 [DEBUG] Input Raw: {len(transcript_segments)} segmentos, {len(xml_nodes)} nodos XML.")
        
        valid_xmls = [n for n in xml_nodes if n.get("text") and len(n.get("text", "").strip()) > 5]
        audio_chunks = self.chunker.chunk_transcript(transcript_segments)
        
        logger.info(f"🔍 [DEBUG] Pre-processed: {len(audio_chunks)} Audio Chunks, {len(valid_xmls)} XML Nodes.")

        if not valid_xmls or not audio_chunks: 
            return []

        # 2. Extracción de textos
        xml_texts = [n.get("text", "") for n in valid_xmls]
        audio_texts = [c.get("text", "") for c in audio_chunks]
        
        # Loguear muestras para ver si están vacías o sucias
        logger.info(f"🔍 [DEBUG] Muestra XML[0]: '{xml_texts[0][:50]}...'")
        logger.info(f"🔍 [DEBUG] Muestra Audio[0]: '{audio_texts[0][:50]}...'")

        # 3. Vectorización
        logger.info("🧠 Generando embeddings...")
        xml_emb = np.array(self.embedder.embed_batch(xml_texts))
        audio_emb = np.array(self.embedder.embed_batch(audio_texts))
        
        # 4. Cálculo de Matriz S
        logger.info(f"🧮 Calculando Similitud Coseno ({len(audio_chunks)}x{len(valid_xmls)})...")
        S = cosine_similarity(audio_emb, xml_emb).astype(np.float32)
        
        # ---> DEBUG DUMP <---
        dump_debug_matrix(S, "debug_S.csv")
        # --------------------

        # 5. Programación Dinámica
        DP, pointers = compute_dp_matrix(
            S=S,
            threshold=self.config.threshold,
            gap_pen=self.config.gap_penalty_base,
            merge_disc=self.config.merge_discount
        )

        # 6. Backtracking
        return self._backtrack_and_assemble(pointers, S, audio_chunks, valid_xmls)

    def _backtrack_and_assemble(self, pointers: np.ndarray, S: np.ndarray, audio_chunks: List, valid_xmls: List) -> List:
        N, M = S.shape
        i, j = N, M
        alignment_map = {} 
        
        matches_found = 0

        while i > 0 and j > 0:
            move = pointers[i, j]
            a_idx, x_idx = i - 1, j - 1 
            
            # Verificación de sanity check en el score
            current_score = S[a_idx, x_idx]

            if move == 0: # MATCH
                if current_score >= self.config.threshold:
                    alignment_map.setdefault(x_idx, []).append(a_idx)
                    matches_found += 1
                i -= 1; j -= 1
            elif move == 1: # MERGE_AUDIO
                if current_score >= self.config.threshold:
                    alignment_map.setdefault(x_idx, []).append(a_idx)
                    matches_found += 1
                i -= 1
            elif move == 2: # MERGE_XML
                if current_score >= self.config.threshold:
                    alignment_map.setdefault(x_idx, []).append(a_idx)
                    matches_found += 1
                j -= 1
            elif move == 3: # SKIP_AUDIO
                i -= 1
            elif move == 4: # SKIP_XML
                j -= 1
            else:
                break
        
        logger.info(f"🔍 [DEBUG] Backtracking encontró {matches_found} cruces crudos.")
        return self._build_payloads(alignment_map, audio_chunks, valid_xmls, S)

    def _build_payloads(self, alignment_map: Dict, audio_chunks: List, valid_xmls: List, S: np.ndarray) -> List:
        aligned_pairs = []
        for x_idx, a_indices in alignment_map.items():
            if not a_indices: continue
            
            # Ordenar índices cronológicamente
            a_indices = sorted(list(set(a_indices)))
            
            combined_texts = []
            # Lista plana de todos los índices de segmentos originales involucrados
            # (Si audio_chunks son agrupaciones, necesitamos desglosarlos si queremos precisión de segmento,
            # pero para el reporte basta con saber qué chunks usó el alineador)
            flat_audio_indices = []

            for idx in a_indices:
                chunk = audio_chunks[idx]
                # Si el chunk tiene segmentos internos, extraemos texto
                if "segments" in chunk:
                    for s in chunk["segments"]:
                        speaker = getattr(s, 'speaker', 'Unknown') if hasattr(s, 'speaker') else s.get('speaker', 'Unknown')
                        text = getattr(s, 'text', '') if hasattr(s, 'text') else s.get('text', '').strip()
                        combined_texts.append(f"[{speaker}]: {text}")
                else:
                    combined_texts.append(chunk.get("text", ""))
                
                # Asumimos que 'idx' en audio_chunks corresponde a índices secuenciales del transcript original
                # O simplemente pasamos el índice del chunk para que el reporte sepa que se usó.
                # Nota: El reporte usa índices sobre 'full_transcript'. 
                # Si 'chunker' agrupó, la correspondencia 1:1 se pierde.
                # Lo mejor es pasar los tiempos de inicio/fin para calcular cobertura.
                
                # Para el reporte de huérfanos específico de debug, necesitamos los índices originales.
                # Si el chunker guarda los índices originales, úsalos. Si no, usamos tiempos.
                if "segments" in chunk:
                    # Suponiendo que 'segments' tiene una referencia al índice original o inferimos por tiempo
                    pass

            xml_ref = valid_xmls[x_idx]
            scores = [S[a, x_idx] for a in a_indices]
            mean_score = float(np.mean(scores)) if scores else 0.0

            first_chunk = audio_chunks[a_indices[0]]
            last_chunk = audio_chunks[a_indices[-1]]

            aligned_pairs.append({
                "instruction": "Transforma esta transcripción coloquial en el formato formal del acta oficial.",
                "input": " ".join(combined_texts),
                "output": xml_ref.get("xml", "").strip(),
                "score": mean_score,
                "metadata": {
                    # --- CORRECCIÓN DE LLAVES PARA EL REPORTE ---
                    "start_time": first_chunk.get("start"), # Antes era audio_start
                    "end_time": last_chunk.get("end"),      # Antes era audio_end
                    
                    # --- DATOS PARA DEBUGGING ---
                    "xml_index": x_idx,
                    "audio_chunk_indices": a_indices, # Índices de los chunks usados
                    "source_node_id": xml_ref.get("id"),
                    "audio_chunks_merged": len(a_indices)
                }
            })

        return sorted(aligned_pairs, key=lambda x: x["metadata"]["start_time"])