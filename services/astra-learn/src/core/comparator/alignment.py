import logging
import boto3
import os
import shutil
from typing import Dict, Any, List
from .metadata import ForensicExtractor, TextSegment
from .metrics import MetricsEngine

logger = logging.getLogger(__name__)

class ComparatorEngine:
    def __init__(self, s3_client=None):
        self.s3 = s3_client or boto3.client('s3')
        self.extractor = ForensicExtractor()
        self.metrics = MetricsEngine()
        self.temp_dir = "/tmp/astra-learn/jobs"
        os.makedirs(self.temp_dir, exist_ok=True)

    def _download_artifact(self, s3_path: str, local_name: str) -> str:
        # s3://bucket/key -> bucket, key
        try:
            parts = s3_path.replace("s3://", "").split("/", 1)
            bucket, key = parts[0], parts[1]
            local_path = os.path.join(self.temp_dir, local_name)
            self.s3.download_file(bucket, key, local_path)
            return local_path
        except Exception as e:
            logger.error(f"Error descargando {s3_path}: {e}")
            raise

    def compare_documents(self, generated_ref: str, final_ref: str, tenant_id: str) -> Dict[str, Any]:
        """
        Ejecuta el pipeline de comparación E2E.
        """
        job_id = os.urandom(4).hex()
        logger.info(f"Iniciando trabajo de comparación {job_id} para Tenant: {tenant_id}")
        
        gen_path = self._download_artifact(generated_ref, f"{job_id}_gen.docx")
        fin_path = self._download_artifact(final_ref, f"{job_id}_fin.docx")

        try:
            # 1. Extracción Forense
            gen_segments = self.extractor.extract_segments(gen_path)
            fin_segments = self.extractor.extract_segments(fin_path)

            # Indexar segmentos generados por chunk_id para búsqueda O(1)
            gen_map = {s.chunk_id: s for s in gen_segments if s.chunk_id}
            
            deltas = []
            global_wer_accum = 0.0
            matched_chunks = 0
            used_gen_ids = set()

            # 2. Alineación y Cálculo (Lógica Real)
            for fin_seg in fin_segments:
                original_seg = None
                match_method = "NONE"
                
                # A. Alineación por ID (Fuerte)
                if fin_seg.chunk_id and fin_seg.chunk_id in gen_map:
                    original_seg = gen_map[fin_seg.chunk_id]
                    match_method = "ID_MATCH"
                    used_gen_ids.add(fin_seg.chunk_id)
                
                # B. Alineación Semántica (Fallback si Word destruyó el ID)
                # Solo buscamos si el segmento final es largo de forma que valga la pena
                elif len(fin_seg.text) > 20:
                    best_match = None
                    max_sim = 0.0
                    for g_id, g_seg in gen_map.items():
                        if g_id in used_gen_ids: continue
                        sim = self.metrics.calculate_semantic_similarity(g_seg.text, fin_seg.text)
                        if sim > 0.85 and sim > max_sim:
                            max_sim = sim
                            best_match = g_seg
                    
                    if best_match:
                        original_seg = best_match
                        match_method = "FUZZY_SEMANTIC"
                        used_gen_ids.add(best_match.chunk_id)

                if original_seg:
                    calc_wer = self.metrics.calculate_wer(original_seg.text, fin_seg.text)
                    calc_sim = self.metrics.calculate_semantic_similarity(original_seg.text, fin_seg.text)
                    change_class = self.metrics.classify_change(calc_wer, calc_sim)
                    
                    deltas.append({
                        "chunk_id": original_seg.chunk_id,
                        "original_text": original_seg.text,
                        "final_text": fin_seg.text,
                        "metrics": {
                            "wer": calc_wer,
                            "similarity": calc_sim,
                            "classification": change_class
                        },
                        "alignment_method": match_method
                    })
                    
                    global_wer_accum += calc_wer
                    matched_chunks += 1
                else:
                    # Texto nuevo insertado por humano
                    deltas.append({
                        "chunk_id": None,
                        "original_text": None,
                        "final_text": fin_seg.text,
                        "metrics": {"classification": "USER_INSERTION"},
                        "alignment_method": "NONE"
                    })

            # 3. Detectar Eliminaciones (Lo que estaba en el original y no llegó al final)
            for gen_id, gen_seg in gen_map.items():
                if gen_id not in used_gen_ids:
                    deltas.append({
                        "chunk_id": gen_id,
                        "original_text": gen_seg.text,
                        "final_text": None,
                        "metrics": {"classification": "USER_DELETION"},
                        "alignment_method": "RESIDUAL"
                    })

            avg_wer = global_wer_accum / matched_chunks if matched_chunks > 0 else 0

            return {
                "job_id": job_id,
                "tenant_id": tenant_id,
                "stats": {
                    "total_segments_final": len(fin_segments),
                    "matched_segments": matched_chunks,
                    "deleted_segments": len(gen_map) - matched_chunks,
                    "average_wer": avg_wer
                },
                "deltas": deltas
            }

        finally:
            # Limpieza segura
            if os.path.exists(gen_path): os.remove(gen_path)
            if os.path.exists(fin_path): os.remove(fin_path)
