import zipfile
import io
import logging
from typing import Iterator, BinaryIO
from .constants import VOLATILE_PREFIXES

logger = logging.getLogger(__name__)

class OOXMLNormalizer:
    """
    Motor de extracción determinista para archivos OpenXML (docx, xlsx, pptx).
    Convierte el archivo físico en un stream canónico ignorando metadatos volátiles.
    """

    def __init__(self, stream: BinaryIO):
        self._stream = stream

    def _is_volatile(self, filename: str) -> bool:
        """Determina si un archivo interno debe ser ignorado."""
        for prefix in VOLATILE_PREFIXES:
            if filename.startswith(prefix):
                return True
        return False

    def get_canonical_stream(self) -> Iterator[bytes]:
        """
        Genera un flujo de bytes ordenado y limpio.
        
        Lógica:
        1. Abre el ZIP.
        2. Filtra archivos volátiles (docProps, etc).
        3. Ordena alfabéticamente los nombres de archivo (Determinismo OS).
        4. Lee el contenido de cada archivo en orden.
        5. Emite chunks de bytes.
        """
        try:
            # Validar que sea un ZIP
            # Si el stream no soporta seek, zipfile dará error. UploadFile.file suele soportarlo.
            if not zipfile.is_zipfile(self._stream):
                raise ValueError("El archivo proporcionado no es un contenedor ZIP válido (OOXML).")

            with zipfile.ZipFile(self._stream, 'r') as zf:
                # 1. Obtener lista de archivos y filtrar
                all_files = zf.namelist()
                semantic_files = [f for f in all_files if not self._is_volatile(f)]
                
                # 2. Ordenar alfabéticamente (Crucial para determinismo)
                # Word puede guardar 'document.xml' antes o después de 'styles.xml'.
                # Nosotros forzamos un orden estricto.
                semantic_files.sort()
                
                logger.info(f"Normalizando {len(semantic_files)} archivos internos para hash semántico.")

                # 3. Streaming de contenido
                for filename in semantic_files:
                    # Opcional: Inyectar el nombre del archivo en el stream para evitar
                    # ataques de colisión donde el contenido se mueve de un archivo a otro.
                    # yield filename.encode('utf-8') 
                    
                    with zf.open(filename) as f:
                        while True:
                            # Leer en pequeños buffers para no saturar RAM
                            chunk = f.read(64 * 1024) # 64KB chunks de lectura interna
                            if not chunk:
                                break
                            yield chunk

        except Exception as e:
            logger.error(f"Error durante la normalización OOXML: {e}")
            raise e
