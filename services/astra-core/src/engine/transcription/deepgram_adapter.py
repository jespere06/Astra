"""
Adaptador de Deepgram (Nova-3) para la interfaz unificada ITranscriber.

Permite transcripción Cloud de alto rendimiento sin consumo de GPU local.
Soporta URLs (S3 presigned) y Buffers.

Requiere:
    - DEEPGRAM_API_KEY en variables de entorno o config.
    - pip install deepgram-sdk==5.x.x
"""

import io
import logging
import os
import json 
from typing import Dict, Optional, Any, List, Union

import httpx 
try:
    from deepgram import DeepgramClient
except ImportError as e:
    print(f"⚠️ Error importando Deepgram: {e}")
    DeepgramClient = None

from src.engine.transcription.interface import (
    ITranscriber,
    TranscriptResult,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "model": "nova-3",
    "smart_format": True,
    "language": "es",
    "punctuate": True,
    "diarize": True, # <--- ACTIVADO
}

class DeepgramTranscriber(ITranscriber):
    """
    Adaptador para el motor Deepgram Nova-3 (SDK v5).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = {**_DEFAULTS, **(config or {})}
        self._client: Optional[DeepgramClient] = None
        self._api_key = self._config.get("api_key") or os.getenv("DEEPGRAM_API_KEY")

    def _ensure_loaded(self):
        """Valida dependencias y credenciales al momento de uso."""
        if self._client is not None:
            return

        if DeepgramClient is None:
            raise RuntimeError(
                "La librería 'deepgram-sdk' no está instalada o falló su importación. "
                "Instale con: pip install deepgram-sdk"
            )

        if not self._api_key:
            raise ValueError("DEEPGRAM_API_KEY no está configurada en el entorno ni en la config.")

        try:
            # Configurar Timeout Extendido (15 minutos / 900 segundos) estilo SDK v5/v6
            self._client = DeepgramClient(
                api_key=self._api_key, 
                timeout=900.0
            )
            logger.info("✅ Cliente Deepgram inicializado (v5/v6) con Timeout extendido (15min).")
        except Exception as e:
            logger.error(f"Error inicializando cliente Deepgram: {e}")
            raise
    # ── ITranscriber Implementation ──────────────────────────

    def transcribe(
        self,
        audio_path: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> TranscriptResult:
        """
        Transcribe desde una URL o un archivo local.
        """
        self._ensure_loaded()
        merged_config = {**self._config, **(config or {})}
        options = self._build_options(merged_config)

        try:
            # Detección de URL vs Archivo Local
            if audio_path.startswith("http://") or audio_path.startswith("https://"):
                logger.info(f"☁️ Enviando URL a Deepgram: {audio_path[:60]}...")
                
                # SINTAXIS v5 CORRECTA: 'url' directo + opciones desempaquetadas
                response = self._client.listen.v1.media.transcribe_url(
                    url=audio_path,
                    **options
                )
            else:
                if not os.path.exists(audio_path):
                    raise FileNotFoundError(f"Archivo no encontrado: {audio_path}")
                
                logger.info(f"📄 Enviando archivo local a Deepgram: {audio_path}")
                with open(audio_path, "rb") as audio_file:
                    buffer_data = audio_file.read()
                
                # SINTAXIS v5 CORRECTA: 'request' recibe los bytes crudos
                response = self._client.listen.v1.media.transcribe_file(
                    request=buffer_data,
                    **options
                )

            return self._map_response(response, merged_config)

        except Exception as e:
            logger.error(f"❌ Error en transcripción Deepgram: {e}")
            raise

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        config: Optional[Dict[str, Any]] = None,
    ) -> TranscriptResult:
        """
        Transcribe desde un buffer de memoria.
        """
        self._ensure_loaded()
        merged_config = {**self._config, **(config or {})}
        options = self._build_options(merged_config)

        try:
            logger.info(f"💾 Enviando buffer ({len(audio_bytes)} bytes) a Deepgram...")
            
            # SINTAXIS v5 CORRECTA: 'request' recibe los bytes crudos
            response = self._client.listen.v1.media.transcribe_file(
                request=audio_bytes,
                **options
            )
            return self._map_response(response, merged_config)

        except Exception as e:
            logger.error(f"❌ Error en transcripción de bytes Deepgram: {e}")
            raise

    def is_loaded(self) -> bool:
        return self._client is not None

    def unload(self) -> None:
        """Deepgram es stateless (REST API), solo limpiamos el cliente."""
        self._client = None

    @property
    def provider_name(self) -> str:
        return "deepgram/nova-3"

    # ── Helpers ──────────────────────────────────────────────

    def _build_options(self, config: Dict) -> Dict[str, Any]:
        """Convierte el diccionario de config a kwargs para el SDK v5."""
        # En v5 pasamos un diccionario simple o kwargs, no PrerecordedOptions
        return {
            "model": config.get("model", "nova-3"),
            "smart_format": config.get("smart_format", True),
            "language": config.get("language", "es"),
            "punctuate": config.get("punctuate", True),
            "diarize": config.get("diarize", False),
        }

    def _map_response(self, response: Any, config: Dict) -> TranscriptResult:
        """
        Transforma la respuesta (Objeto Pydantic SDK v5+) a TranscriptResult de ASTRA.
        """
        try:
            # 1. Acceso a properties (SDK v5/v6)
            results = getattr(response, "results", None)
            if not results:
                return TranscriptResult(text="", segments=[], provider=self.provider_name)

            channels = getattr(results, "channels",[])
            if not channels or len(channels) == 0:
                return TranscriptResult(text="", segments=[], provider=self.provider_name)

            first_channel = channels[0] # <--- CORRECCIÓN: Faltaba el
            
            alternatives = getattr(first_channel, "alternatives",[])
            if not alternatives or len(alternatives) == 0:
                return TranscriptResult(text="", segments=[], provider=self.provider_name)

            alternative = alternatives[0] # <--- CORRECCIÓN: Faltaba el
            
            # Extraemos propiedades
            words = getattr(alternative, "words",[])
            full_text = getattr(alternative, "transcript", "")
            confidence = getattr(alternative, "confidence", 0.0)

            metadata = getattr(response, "metadata", None)
            duration = getattr(metadata, "duration", 0.0) if metadata else 0.0

            segments: List =[]
            formatted_full_text = ""

            # 2. LÓGICA DE AGRUPAMIENTO POR HABLANTE
            # --- VERSIÓN ENTERPRISE DEL BUCLE DE AGRUPAMIENTO ---
            if words:
                # 1. Extraer configuraciones con valores por defecto seguros para Embeddings
                # Lo ideal es que estos vengan de config.get("chunking", {})...
                max_words = config.get("max_words_per_segment", 150) # ~200 tokens (ideal para embeddings)
                soft_time_limit = config.get("soft_time_limit_sec", 12.0) # Cuándo empezar a buscar un punto
                hard_time_limit = config.get("hard_time_limit_sec", 35.0) # Cuándo cortar por emergencia
                pause_threshold = config.get("pause_threshold_sec", 1.5)  # Segundos de silencio para asumir nueva idea

                current_speaker = None
                current_text_buffer =[]
                current_start = 0.0
                current_end = 0.0
                conf_sum = 0.0
                prev_word_end = 0.0 # Para calcular silencios
                
                for w in words:
                    w_speaker = getattr(w, "speaker", 0) or 0
                    w_text = getattr(w, "punctuated_word", None) or getattr(w, "word", "")
                    w_start = float(getattr(w, "start", 0.0))
                    w_end = float(getattr(w, "end", 0.0))
                    w_conf = float(getattr(w, "confidence", 0.0))
                    
                    if current_speaker is None:
                        current_speaker = w_speaker
                        current_start = w_start
                        prev_word_end = w_start
                    
                    # --- LÓGICA DE CORTE ENTERPRISE ---
                    duration = w_end - current_start
                    word_count = len(current_text_buffer)
                    silence_duration = w_start - prev_word_end
                    
                    is_strong_punct = any(w_text.endswith(p) for p in ('.', '?', '!'))
                    is_speaker_change = (w_speaker != current_speaker)
                    
                    # Evaluamos razones para cortar
                    cut_reason = None
                    if is_speaker_change:
                        cut_reason = "speaker_change"
                    elif word_count >= max_words:
                        cut_reason = "max_words_reached"
                    elif duration >= hard_time_limit:
                        cut_reason = "hard_time_limit"
                    elif duration >= soft_time_limit and is_strong_punct:
                        cut_reason = "semantic_sentence_end"
                    elif silence_duration >= pause_threshold and word_count > 5:
                        cut_reason = "long_pause_detected"

                    # Si hay una razón para cortar y tenemos texto acumulado
                    if cut_reason and current_text_buffer:
                        # Opcional: Loguear por qué se cortó (útil para afinar parámetros)
                        # logger.debug(f"Corte realizado por: {cut_reason} (Duración: {duration:.1f}s, Palabras: {word_count})")
                        
                        seg_text = " ".join(current_text_buffer)
                        avg_conf = conf_sum / word_count

                        minutes, seconds = divmod(int(current_start), 60)
                        timestamp = f"{minutes:02d}:{seconds:02d}"
                        speaker_label = f"Speaker {current_speaker}"

                        segments.append(TranscriptSegment(
                            start=current_start,
                            end=current_end,
                            text=seg_text,
                            confidence=avg_conf,
                            speaker=speaker_label
                        ))

                        formatted_full_text += f" ({timestamp}): {seg_text}\n"
                        
                        # Reset para el siguiente segmento
                        current_speaker = w_speaker
                        current_start = w_start
                        current_text_buffer =[]
                        conf_sum = 0.0
                    
                    # Añadir palabra actual al buffer
                    current_text_buffer.append(w_text)
                    current_end = w_end
                    conf_sum += w_conf
                    prev_word_end = w_end
                    
                # Guardar el último segmento remanente (Draining the buffer)
                if current_text_buffer:
                    seg_text = " ".join(current_text_buffer)
                    avg_conf = conf_sum / len(current_text_buffer)
                    minutes, seconds = divmod(int(current_start), 60)
                    timestamp = f"{minutes:02d}:{seconds:02d}"
                    speaker_label = f"Speaker {current_speaker}"
                    
                    segments.append(TranscriptSegment(
                        start=current_start,
                        end=current_end,
                        text=seg_text,
                        confidence=avg_conf,
                        speaker=speaker_label
                    ))
                    formatted_full_text += f" ({timestamp}): {seg_text}\n"

                final_text = formatted_full_text.strip()

            return TranscriptResult(
                text=final_text,
                segments=segments,
                language=config.get("language", "es"),
                language_probability=1.0, 
                duration_seconds=duration,
                provider=self.provider_name,
                metadata={"api": "deepgram"}
            )

        except Exception as e:
            logger.error(f"Error mapeando respuesta Deepgram: {e}")
            import traceback
            traceback.print_exc()
            return TranscriptResult(text="", segments=[], provider=self.provider_name)