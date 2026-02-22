import numpy as np
import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from sqlalchemy.orm import Session
from src.db.models import ZoneMapping, MappingOrigin

logger = logging.getLogger(__name__)

# Constantes de Zona (Contrato con Orchestrator)
ZONE_HEADER = "ZONE_HEADER"
ZONE_BODY = "ZONE_BODY"
ZONE_FOOTER = "ZONE_FOOTER"
ZONE_UNCERTAIN = "ZONE_UNCERTAIN"  # Alias lógico, físicamente puede ir al Body con flag

@dataclass
class BlockOccurrence:
    """Representa una aparición de un template en un documento original."""
    doc_id: str
    block_index: int      # Índice del párrafo (ej. 5)
    total_blocks: int     # Total de párrafos en el doc (ej. 100)

    @property
    def relative_position(self) -> float:
        if self.total_blocks == 0: return 0.0
        return self.block_index / self.total_blocks

class HeuristicMapper:
    """
    Motor estadístico para inferir la zona de un template basado en su posición histórica.
    """
    
    # Umbrales configurables
    THRESHOLD_HEADER = 0.15  # El 15% superior del documento
    THRESHOLD_FOOTER = 0.85  # El 15% inferior del documento
    MAX_STD_DEV = 0.2        # Si la variación es mayor a esto, es "flotante/incierto"

    def __init__(self, db: Session):
        self.db = db

    def calculate_stats(self, occurrences: List[BlockOccurrence]) -> Dict[str, float]:
        """Calcula media y desviación estándar de las posiciones relativas."""
        positions = [occ.relative_position for occ in occurrences]
        
        if not positions:
            return {"mean": 0.5, "std": 1.0, "count": 0}

        return {
            "mean": float(np.mean(positions)),
            "std": float(np.std(positions)),
            "count": len(positions)
        }

    def infer_zone(self, stats: Dict[str, float]) -> Tuple[str, float]:
        """
        Aplica reglas heurísticas para determinar la zona y la confianza.
        Retorna: (zone_id, confidence)
        """
        mean = stats["mean"]
        std = stats["std"]
        count = stats["count"]

        # 1. Penalización por pocos datos
        confidence_penalty = 0.0
        if count < 5:
            confidence_penalty = 0.3

        # 2. Detección de inestabilidad (aparece en cualquier lado)
        if std > self.MAX_STD_DEV:
            # Es un bloque flotante, lo asignamos al Body pero con confianza baja
            return ZONE_BODY, max(0.1, 0.5 - confidence_penalty)

        # 3. Asignación posicional
        base_confidence = 0.95 - confidence_penalty
        
        if mean <= self.THRESHOLD_HEADER:
            return ZONE_HEADER, base_confidence
        
        if mean >= self.THRESHOLD_FOOTER:
            return ZONE_FOOTER, base_confidence
            
        return ZONE_BODY, base_confidence

    def process_mapping(self, tenant_id: str, template_id: str, occurrences: List[BlockOccurrence]):
        """
        Ejecuta el análisis y persiste/actualiza el mapeo en DB.
        Respeta el flag 'is_locked' si ya existe un mapeo manual.
        """
        # 1. Verificar existencia y bloqueo
        existing_mapping = self.db.query(ZoneMapping).filter_by(template_id=template_id).first()
        
        if existing_mapping and existing_mapping.is_locked:
            logger.info(f"Mapping para template {template_id} está bloqueado por humano. Saltando auto-update.")
            return existing_mapping

        # 2. Calcular estadísticas
        stats = self.calculate_stats(occurrences)
        
        # 3. Inferir zona
        zone_id, confidence = self.infer_zone(stats)
        
        # 4. Persistir (Upsert logic)
        if existing_mapping:
            existing_mapping.zone_id = zone_id
            existing_mapping.position_stats = stats
            existing_mapping.confidence_score = confidence
            existing_mapping.origin = MappingOrigin.AUTO
        else:
            new_mapping = ZoneMapping(
                tenant_id=tenant_id,
                template_id=template_id,
                zone_id=zone_id,
                position_stats=stats,
                confidence_score=confidence,
                origin=MappingOrigin.AUTO,
                is_locked=False
            )
            self.db.add(new_mapping)
        
        self.db.commit()
        logger.info(f"Auto-mapped template {template_id} to {zone_id} (conf: {confidence:.2f})")
        return existing_mapping or new_mapping
