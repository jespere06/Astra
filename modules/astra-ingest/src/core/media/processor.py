
import io
import uuid
import imagehash
from PIL import Image
from sqlalchemy.orm import Session
from typing import Optional, Tuple

from src.db.models import Asset, AssetType
from src.core.exceptions import AstraIngestError

class MediaProcessor:
    """
    Maneja el procesamiento de imágenes, cálculo de pHash y persistencia.
    """
    
    # Umbral de Distancia de Hamming para considerar duplicado (0-5 es seguro)
    DUPLICATE_THRESHOLD = 5 

    def __init__(self, db: Session):
        self.db = db

    def _compute_phash(self, image_data: bytes) -> str:
        """Calcula el hash perceptual de una imagen binaria."""
        try:
            # Abrir imagen desde memoria
            img = Image.open(io.BytesIO(image_data))
            
            # Normalizar para consistencia (opcional, imagehash ya lo hace internamente)
            # img = img.resize((64, 64), Image.LANCZOS).convert("L")
            
            # Calcular pHash (Hash de 64 bits = 16 caracteres hex)
            hash_obj = imagehash.phash(img)
            return str(hash_obj)
        except Exception as e:
            raise AstraIngestError(f"Error procesando imagen para pHash: {e}")

    def _hamming_distance(self, hash1_str: str, hash2_str: str) -> int:
        """Calcula distancia de Hamming entre dos strings hexadecimales."""
        if len(hash1_str) != len(hash2_str):
            return 100 # Penalización máxima si longitudes difieren
        
        # Convertir hex a int y hacer XOR, luego contar bits en 1
        h1 = int(hash1_str, 16)
        h2 = int(hash2_str, 16)
        return bin(h1 ^ h2).count('1')

    def find_duplicate(self, tenant_id: str, image_data: bytes) -> Tuple[bool, Optional[str], float]:
        """
        Busca si existe una imagen visualmente similar para el tenant.
        Retorna: (is_duplicate, asset_id, confidence)
        """
        target_phash = self._compute_phash(image_data)
        
        # Estrategia: Cargar hashes del tenant y comparar en memoria (Python).
        # Para <100k imágenes por tenant, esto es más rápido que una función compleja de DB sin extensiones.
        candidates = self.db.query(Asset).filter(
            Asset.tenant_id == tenant_id,
            Asset.asset_type == AssetType.IMAGE
        ).with_entities(Asset.id, Asset.p_hash).all()

        best_match_id = None
        min_distance = 100

        for asset_id, stored_phash in candidates:
            dist = self._hamming_distance(target_phash, stored_phash)
            if dist < min_distance:
                min_distance = dist
                best_match_id = str(asset_id)
                
                # Short-circuit: Si es idéntico, salir ya
                if dist == 0:
                    break
        
        is_duplicate = min_distance <= self.DUPLICATE_THRESHOLD
        
        # Confianza inversa a la distancia (0 dist = 1.0 conf)
        confidence = max(0.0, 1.0 - (min_distance / 64.0))

        return is_duplicate, best_match_id if is_duplicate else None, confidence

    def register_new_asset(self, tenant_id: str, image_data: bytes, filename: str) -> Asset:
        """
        Guarda un nuevo asset en Storage (simulado) y DB.
        """
        phash = self._compute_phash(image_data)
        asset_id = uuid.uuid4()
        
        # Simulación de subida a S3/MinIO
        # En producción, aquí iría boto3.upload_fileobj
        storage_key = f"s3://astra-assets/{tenant_id}/{asset_id}/{filename}"
        
        new_asset = Asset(
            id=asset_id,
            tenant_id=tenant_id,
            asset_type=AssetType.IMAGE,
            p_hash=phash,
            storage_url=storage_key,
            original_filename=filename
        )
        
        self.db.add(new_asset)
        self.db.commit()
        self.db.refresh(new_asset)
        
        return new_asset