"""
Contrato central del Motor de Transcripción de ASTRA.

Define la interfaz abstracta `ITranscriber` y los modelos de datos
estandarizados que todo adaptador concreto DEBE devolver.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


# ────────────────────────────────────────────
# Data Models  (Shared contract)
# ────────────────────────────────────────────

@dataclass
class TranscriptSegment:
    """Un fragmento temporal de la transcripción."""
    start: float          # Inicio en segundos
    end: float            # Fin en segundos
    text: str             # Texto transcrito
    confidence: float     # Score de confianza normalizado [0..1]  (-inf log-prob → 0..1)
    speaker: Optional[str] = None   # Hablante (si hay diarización)

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class TranscriptResult:
    """Resultado completo y estandarizado de una transcripción."""
    text: str                                   # Texto completo concatenado
    segments: List[TranscriptSegment]           # Lista detallada de segmentos
    language: str = "es"                        # Idioma detectado
    language_probability: float = 1.0           # Confianza de detección
    duration_seconds: float = 0.0               # Duración total del audio
    provider: str = "unknown"                   # Nombre del motor utilizado
    metadata: Dict[str, Any] = field(default_factory=dict)  # Extra info


# ────────────────────────────────────────────
# Abstract Interface
# ────────────────────────────────────────────

class ITranscriber(ABC):
    """
    Interfaz abstracta que todo motor de transcripción debe implementar.

    Responsabilidades del adaptador concreto:
        1. Cargar el modelo de forma lazy (primera invocación).
        2. Normalizar el output a `TranscriptResult`.
        3. Liberar recursos explícitamente en `unload()`.
    """

    @abstractmethod
    def transcribe(
        self,
        audio_path: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> TranscriptResult:
        """
        Transcribe un archivo de audio completo.

        Args:
            audio_path:  Ruta local al archivo de audio (wav, mp3, ogg, etc.).
            config:      Configuración opcional para esta ejecución específica.
                         Puede sobrescribir defaults del adaptador (beam_size, vad, etc.).

        Returns:
            TranscriptResult con texto, segmentos y metadatos normalizados.
        """
        ...

    @abstractmethod
    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        config: Optional[Dict[str, Any]] = None,
    ) -> TranscriptResult:
        """
        Transcribe audio desde un buffer en memoria (bytes).
        
        Útil para streaming o cuando el audio ya está en RAM.
        """
        ...

    @abstractmethod
    def is_loaded(self) -> bool:
        """Retorna True si el modelo subyacente ya está cargado en memoria."""
        ...

    @abstractmethod
    def unload(self) -> None:
        """Libera la GPU/RAM del modelo. Permite escalar a cero."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Nombre canónico del motor (para logging y métricas)."""
        ...
