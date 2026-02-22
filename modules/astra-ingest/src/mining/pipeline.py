import os
# APAGAR PARALELISMO DE RUST PARA EVITAR ERROR "Already borrowed" EN MAC
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import csv
import json
import time
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# Componentes internos
from src.mining.downloader import MediaDownloader, DownloadError
from src.mining.core_client import CoreTranscriptionClient
from src.mining.extractor import SemanticExtractor
from src.mining.aligner import SemanticAligner, AlignerConfig
from src.mining.dataset_builder import DatasetBuilder
from src.mining.analyzer import CorpusAnalyzer

logger = logging.getLogger(__name__)

class MiningOrchestrator:
    def __init__(self, output_dir: str, tenant_id: str = "default_miner"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tenant_id = tenant_id
        
        # Inicialización de servicios
        self.downloader = MediaDownloader()
        self.core_client = CoreTranscriptionClient()
        self.aligner = SemanticAligner(config=AlignerConfig(threshold=0.35))
        self.analyzer = CorpusAnalyzer()
        self.static_hashes = set() 

    def _process_single_row(self, idx: int, row: dict, total_rows: int, provider: str, dry_run: bool):
        video_url = (row.get("video_url") or row.get("url") or "").strip()
        docx_path = (row.get("docx_path") or row.get("path") or "").strip()

        if not video_url or not docx_path:
            return {"status": "failed", "pairs": [], "error": "Datos incompletos"}

        logger.info(f"▶️ [Hilo Iniciado] Procesando [{idx+1}/{total_rows}]: {video_url}")

        try:
            if not os.path.exists(docx_path):
                raise FileNotFoundError(f"Documento no encontrado: {docx_path}")

            if dry_run:
                return {"status": "success", "pairs": []}

            video_id = hashlib.md5(video_url.encode()).hexdigest()[:10]
            transcript_cache_path = self.output_dir / f"transcript_{video_id}.json"
            pairs_cache_path = self.output_dir / f"pairs_{video_id}.json"

            if pairs_cache_path.exists():
                logger.info(f"🟣 [{idx+1}] Usando PARES CACHEADOS (Saltando Alineación)")
                with open(pairs_cache_path, 'r', encoding='utf-8') as pf:
                    pairs = json.load(pf)
                return {"status": "success", "pairs": pairs, "url": video_url}

            segments = []
            if transcript_cache_path.exists():
                logger.info(f"🟢 [{idx+1}] Usando transcripción CACHEADA")
                with open(transcript_cache_path, 'r', encoding='utf-8') as cf:
                    segments = json.load(cf)
            else:
                s3_uri = self.downloader.download_and_upload(video_url, self.tenant_id)
                transcript_result = self.core_client.transcribe_url(
                    audio_url=s3_uri, 
                    tenant_id=self.tenant_id,
                    provider=provider
                )
                segments = transcript_result.get("segments", [])
                if not segments:
                    raise ValueError("La transcripción no retornó segmentos válidos.")
                
                with open(transcript_cache_path, 'w', encoding='utf-8') as cf:
                    json.dump(segments, cf, ensure_ascii=False, indent=2)

            extractor = SemanticExtractor(self.static_hashes)
            docx_fragments = extractor.extract_from_document(docx_path)

            pairs = self.aligner.align(segments, docx_fragments)
            
            # Guardar en caché para no volver a calcular nunca más
            with open(pairs_cache_path, 'w', encoding='utf-8') as pf:
                json.dump(pairs, pf, ensure_ascii=False, indent=2)
                
            logger.info(f"✅ [{idx+1}] FIN. Alineados {len(pairs)} pares de este video.")

            return {"status": "success", "pairs": pairs, "url": video_url}

        except Exception as e:
            logger.error(f"❌ Error en fila {idx+1} ({video_url}): {str(e)}")
            return {"status": "failed", "pairs": [], "error": str(e), "url": video_url, "row": idx+1}

    def process_batch(self, csv_path: str, provider: str = "deepgram", dry_run: bool = False, max_workers: int = 3):
        report = {
            "job_id": f"job_{int(time.time())}",
            "start_time": datetime.utcnow().isoformat(),
            "total_rows": 0,
            "success": 0,
            "failed": 0,
            "errors": []
        }

        all_aligned_pairs = []

        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Archivo CSV no encontrado: {csv_path}")

        logger.info(f"🚀 Iniciando Pipeline MULTIHILO (Workers: {max_workers})")

        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            report["total_rows"] = len(rows)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self._process_single_row, idx, row, len(rows), provider, dry_run): idx 
                    for idx, row in enumerate(rows)
                }

                for future in as_completed(futures):
                    res = future.result()
                    if res["status"] == "success":
                        report["success"] += 1
                        if res["pairs"]:
                            all_aligned_pairs.extend(res["pairs"])
                            
                            # ✨ MAGIA: GUARDADO INCREMENTAL ✨
                            # Guarda el train.jsonl en tiempo real después de cada video exitoso.
                            if not dry_run:
                                builder = DatasetBuilder()
                                builder.build(all_aligned_pairs, str(self.output_dir), train_ratio=0.9)
                                logger.info(f"💾 Dataset actualizado con éxito ({len(all_aligned_pairs)} pares totales)")
                    else:
                        report["failed"] += 1
                        report["errors"].append({
                            "row": res.get("row"), "url": res.get("url"), "error": res.get("error")
                        })

        report["end_time"] = datetime.utcnow().isoformat()
        report["aligned_pairs_count"] = len(all_aligned_pairs)
        report_path = self.output_dir / f"mining_report_{report['job_id']}.json"
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            
        return report