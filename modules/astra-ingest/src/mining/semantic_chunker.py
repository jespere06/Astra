import numpy as np
from typing import List, Dict, Any
from src.core.nlp.embedder import TextEmbedder
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger(__name__)

class EnterpriseSemanticChunker:
    def __init__(
        self, 
        base_threshold: float = 0.60, 
        min_duration_sec: float = 15.0,
        soft_max_duration_sec: float = 60.0,
        hard_max_duration_sec: float = 90.0,
        silence_penalty: float = 0.15,
        speaker_change_penalty: float = 0.10, 
        ema_alpha: float = 0.4,
        overlap_segments: int = 1
    ):
        self.embedder = TextEmbedder()
        self.base_threshold = base_threshold
        self.min_duration = min_duration_sec
        self.soft_max = soft_max_duration_sec
        self.hard_max = hard_max_duration_sec
        self.silence_penalty = silence_penalty
        self.speaker_change_penalty = speaker_change_penalty
        self.ema_alpha = ema_alpha
        self.overlap = overlap_segments

    def chunk_transcript(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not segments:
            return []

        # 1. Vectorización Batch
        sentences = [s.get('text', '').strip() for s in segments]
        
        # --- CORRECCIÓN AQUÍ: Convertir la lista a NumPy Array ---
        embeddings_list = self.embedder.embed_batch(sentences)
        embeddings = np.array(embeddings_list) 
        # ---------------------------------------------------------
        
        chunks = []
        
        # Inicializar estado con el primer segmento
        current_indices = [0] 
        current_segments = [segments[0]]
        current_text = segments[0].get('text', '')
        chunk_start = segments[0].get('start', 0.0)
        chunk_end = segments[0].get('end', 0.0)
        
        # Centroide Inicial
        current_centroid = embeddings[0].reshape(1, -1)

        # Iteramos desde el segundo segmento
        i = 1
        while i < len(segments):
            next_seg = segments[i]
            next_emb = embeddings[i].reshape(1, -1)
            
            # Calculamos similitud contra el "Tema Reciente" (Centroide EMA)
            raw_similarity = cosine_similarity(current_centroid, next_emb)[0][0]
            adjusted_sim = raw_similarity

            # --- Multi-modalidad (Tiempo + Hablantes) ---
            
            # A. Penalización por Silencio
            silence_gap = next_seg.get('start', 0.0) - chunk_end
            if silence_gap > 2.0:
                adjusted_sim -= self.silence_penalty
                
            # B. Penalización por Cambio de Orador
            last_speaker = current_segments[-1].get('speaker')
            next_speaker = next_seg.get('speaker')
            
            if last_speaker and next_speaker and last_speaker != next_speaker:
                adjusted_sim -= self.speaker_change_penalty

            # --- Zonas de Corte Inteligentes ---
            current_duration = chunk_end - chunk_start
            
            is_in_warning_zone = current_duration >= self.soft_max
            is_guillotine_cut = current_duration >= self.hard_max
            is_safe_to_cut = current_duration >= self.min_duration

            # CONDICIÓN DE CORTE
            should_cut = False
            
            if is_safe_to_cut and adjusted_sim < self.base_threshold:
                should_cut = True
            elif is_in_warning_zone and adjusted_sim < (self.base_threshold + 0.1):
                should_cut = True
            elif is_guillotine_cut:
                should_cut = True

            if should_cut:
                # CERRAR CHUNK ACTUAL
                chunks.append({
                    "text": current_text.strip(),
                    "segments": current_segments.copy(),
                    "start": chunk_start,
                    "end": chunk_end,
                    "duration": current_duration,
                    "avg_similarity": float(adjusted_sim)
                })
                
                # --- Overlap ---
                overlap_count = min(self.overlap, len(current_segments))
                
                if overlap_count > 0:
                    overlap_segs = current_segments[-overlap_count:]
                    overlap_idxs = current_indices[-overlap_count:]
                else:
                    overlap_segs = []
                    overlap_idxs = []

                # INICIAR NUEVO CHUNK (Con overlap)
                current_segments = overlap_segs + [next_seg]
                current_indices = overlap_idxs + [i]
                
                current_text = " ".join([s.get('text', '').strip() for s in current_segments])
                chunk_start = current_segments[0].get('start', next_seg.get('start', 0.0))
                chunk_end = next_seg.get('end', 0.0)
                
                # Resetear el Centroide (Promedio del overlap + nuevo)
                relevant_embeddings = embeddings[current_indices] # Indexación NumPy
                current_centroid = np.mean(relevant_embeddings, axis=0).reshape(1, -1)

            else:
                # FUSIONAR
                current_segments.append(next_seg)
                current_indices.append(i)
                current_text += " " + next_seg.get('text', '').strip()
                chunk_end = next_seg.get('end', 0.0)
                
                # Actualizar EMA del centroide
                current_centroid = (self.ema_alpha * next_emb) + ((1 - self.ema_alpha) * current_centroid)

            i += 1

        # Agregar el último chunk pendiente
        if current_segments:
            chunks.append({
                "text": current_text.strip(),
                "segments": current_segments,
                "start": chunk_start,
                "end": chunk_end,
                "duration": chunk_end - chunk_start
            })

        logger.info(f"🧠 Chunking Empresarial: {len(segments)} oraciones procesadas en {len(chunks)} bloques cognitivos.")
        return chunks