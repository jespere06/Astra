import json
import random
import logging
from typing import List, Dict, Any, Tuple
from pathlib import Path
from collections import defaultdict

# Intentar importar NoiseInjector si existe, sino usar None (retrocompatibilidad)
try:
    from .noise_engine import NoiseInjector
except ImportError:
    NoiseInjector = None

logger = logging.getLogger(__name__)

class DatasetBuilder:
    """
    Transforma pares alineados en datasets JSONL formato Alpaca para Instruction Tuning.
    Implementa prevención de fuga de datos (Data Leakage) agrupando por documento origen.
    """

    # Banco de System Prompts para variabilidad y robustez
    SYSTEM_INSTRUCTIONS = [
        "Transforma la siguiente intervención coloquial en un fragmento de acta oficial en formato OpenXML (DOCX).",
        "Actúa como un secretario de concejo y formaliza la transcripción en un bloque XML válido.",
        "Genera el código XML del acta correspondiente a lo dicho en el audio, manteniendo el estilo formal.",
        "Convierte el discurso hablado en texto jurídico estructurado para un acta municipal.",
        "Redacta el párrafo del acta basándote en la transcripción, corrigiendo muletillas y aplicando etiquetas XML."
    ]

    def __init__(self, noise_injector: Any = None):
        self.noise_injector = noise_injector

    def build(
        self,
        aligned_pairs: List[Dict[str, Any]],
        output_dir: str,
        train_ratio: float = 0.9,
        min_score: float = 0.0,
        augment_factor: int = 0,
        seed: int = 42
    ) -> Dict[str, int]:
        """
        Genera train.jsonl y val.jsonl asegurando que no haya fuga de datos entre documentos.

        Args:
            aligned_pairs: Lista de dicts {input, output, score, metadata}.
            output_dir: Ruta donde guardar los archivos.
            train_ratio: Porcentaje para entrenamiento (0.0 - 1.0).
            min_score: Score mínimo de alineación para incluir el par.
            augment_factor: Factor de aumento de datos con ruido.
            seed: Semilla para reproducibilidad del split.

        Returns:
            Dict con estadísticas {'train': N, 'val': N}.
        """
        random.seed(seed)
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        # 1. Filtrado Inicial por Calidad
        valid_pairs = [
            p for p in aligned_pairs 
            if p.get("score", 1.0) >= min_score 
            and p.get("input", "").strip() 
            and p.get("output", "").strip()
        ]

        if not valid_pairs:
            logger.warning("No hay pares válidos para generar el dataset.")
            return {"train": 0, "val": 0}

        # 2. Agrupamiento por Documento (Anti-Leakage Strategy)
        # Usamos 'source_doc_id' o 'doc_id' o generamos un grupo 'unknown'
        grouped_docs = defaultdict(list)
        for pair in valid_pairs:
            # Intentar obtener ID del documento desde metadata
            meta = pair.get("metadata", {})
            # Soporte para varias convenciones de nombres en metadata
            doc_id = meta.get("source_doc_id") or meta.get("doc_id") or meta.get("filename") or "unknown_doc"
            grouped_docs[doc_id].append(pair)

        doc_ids = list(grouped_docs.keys())
        random.shuffle(doc_ids)

        # 3. Split Determinista a Nivel de Documento
        
        # --- PARCHE PARA DEBUG/PRUEBAS CON UN SOLO DOC ---
        if len(doc_ids) == 1:
            # Si solo hay un documento, no podemos dividir por documento.
            # Ponemos todo en Train para que el fine-tuning funcione, 
            # o hacemos un split aleatorio simple ignorando la fuga de datos.
            logger.warning("⚠️ Solo se detectó 1 documento único. Forzando split aleatorio simple (Mode Dev).")
            
            random.shuffle(valid_pairs)
            split_idx = int(len(valid_pairs) * train_ratio)
            
            train_pairs = valid_pairs[:split_idx]
            val_pairs = valid_pairs[split_idx:]
            
            # Dummy lists for reporting
            train_docs = doc_ids
            val_docs = []
            
        else:
            # --- LÓGICA DE PRODUCCIÓN (Anti-Leakage) ---
            split_idx = int(len(doc_ids) * train_ratio)
            
            # Caso borde: Si hay pocos documentos, asegurar al menos 1 en val
            if split_idx == len(doc_ids) and train_ratio < 1.0 and len(doc_ids) > 1:
                split_idx = len(doc_ids) - 1

            train_docs = doc_ids[:split_idx]
            val_docs = doc_ids[split_idx:]

            # Aplanar listas
            train_pairs = []
            for doc_id in train_docs:
                train_pairs.extend(grouped_docs[doc_id])

            val_pairs = []
            for doc_id in val_docs:
                val_pairs.extend(grouped_docs[doc_id])

        # 4. Aumento de Datos (Solo en Train)
        if augment_factor > 0 and self.noise_injector:
            augmented_train = []
            for pair in train_pairs:
                augmented_train.append(pair) # Mantener original
                for _ in range(augment_factor):
                    # Copia profunda necesaria si modificamos
                    noisy_pair = pair.copy()
                    noisy_pair["input"] = self.noise_injector.corrupt(pair["input"])
                    # Importante: No cambiamos el output (XML), solo el input ruidoso
                    augmented_train.append(noisy_pair)
            train_pairs = augmented_train
            random.shuffle(train_pairs)

        # 5. Escritura física (Formato Alpaca)
        self._write_jsonl(train_pairs, out_path / "train.jsonl")
        self._write_jsonl(val_pairs, out_path / "val.jsonl")

        logger.info(
            f"Dataset Generado: {len(train_pairs)} train (Docs: {len(train_docs)}), "
            f"{len(val_pairs)} val (Docs: {len(val_docs)})"
        )

        return {
            "train": len(train_pairs),
            "val": len(val_pairs),
            "train_docs": len(train_docs),
            "val_docs": len(val_docs)
        }

    def _write_jsonl(self, pairs: List[Dict], filepath: Path):
        """Escribe la lista de pares en formato JSONL Alpaca estricto."""
        with open(filepath, 'w', encoding='utf-8') as f:
            for p in pairs:
                # Selección aleatoria del System Prompt
                instruction = random.choice(self.SYSTEM_INSTRUCTIONS)
                
                # Estructura Alpaca
                row = {
                    "instruction": instruction,
                    "input": p["input"],
                    "output": p["output"],
                    # Preservar metadatos útiles para debugging pero fuera del schema core de entrenamiento si se desea
                    # Algunas herramientas de training ignoran llaves extra, otras fallan.
                    # Unsloth suele ignorar extras. Lo dejamos por trazabilidad.
                    "metadata": p.get("metadata", {})
                }
                
                # Serialización segura (sin escapeo ASCII para soportar tildes/ñ)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")