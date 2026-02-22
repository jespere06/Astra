import io
import logging
from PIL import Image
from src.config import settings

logger = logging.getLogger(__name__)

class ImageNormalizer:
    @staticmethod
    def process(image_bytes: bytes) -> bytes:
        """
        Normaliza una imagen:
        1. Convierte a RGB (Manejo de Transparencia/CMYK).
        2. Redimensiona si excede el ancho máximo (mantiene aspect ratio).
        3. Comprime a JPEG optimizado.
        """
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                # Conversión segura a RGB (necesario para guardar como JPEG)
                if img.mode in ('RGBA', 'P', 'CMYK'):
                     # Convert P to RGBA first to handle transparency properly if palette based, then RGB
                    if img.mode == 'P':
                         img = img.convert('RGBA')
                    img = img.convert('RGB')

                # Redimensionamiento (Downscaling)
                width, height = img.size
                if width > settings.MAX_IMAGE_WIDTH:
                    # Calcular nueva altura manteniendo ratio
                    new_height = int(height * (settings.MAX_IMAGE_WIDTH / width))
                    # LANCZOS es el mejor filtro para downsampling
                    img = img.resize((settings.MAX_IMAGE_WIDTH, new_height), Image.Resampling.LANCZOS)
                    logger.debug(f"Imagen redimensionada: {width}x{height} -> {settings.MAX_IMAGE_WIDTH}x{new_height}")

                # Compresión y Exportación
                output_buffer = io.BytesIO()
                img.save(
                    output_buffer, 
                    format='JPEG', 
                    quality=settings.IMAGE_QUALITY, 
                    optimize=True
                )
                
                return output_buffer.getvalue()

        except Exception as e:
            logger.error(f"Error normalizando imagen: {e}")
            # Política de Resiliencia: Si falla la optimización, 
            # devolvemos el original para no bloquear el flujo.
            return image_bytes
