from abc import ABC, abstractmethod
from typing import Optional

class ASRProvider(ABC):
    """
    Clase base abstracta para proveedores de reconocimiento automático de voz (ASR).
    """

    @abstractmethod
    async def transcribe(self, audio_content: bytes, filename: str = "audio.wav", language: str = "es") -> str:
        """
        Transcribe el contenido de audio a texto.
        
        Args:
            audio_content (bytes): El archivo de audio en bytes.
            filename (str): Nombre ficticio del archivo (requerido por algunas APIs).
            language (str): Código ISO del idioma (default 'es').

        Returns:
            str: El texto transcrito.
        """
        pass
