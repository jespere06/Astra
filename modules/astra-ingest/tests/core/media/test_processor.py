import pytest
import io
from unittest.mock import MagicMock
from PIL import Image
from src.core.media.processor import MediaProcessor
from src.db.models import Asset, AssetType

class TestMediaProcessor:

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def processor(self, mock_db):
        return MediaProcessor(mock_db)

    def create_dummy_image_bytes(self, color="red", size=(100, 100)):
        """Crea una imagen en memoria para pruebas."""
        img = Image.new("RGB", size, color=color)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_phash_robustness(self, processor):
        """
        DoD: Imagen original vs Imagen reducida 50% -> is_duplicate = True.
        Verifica que el pHash sea resistente a cambios de tamaño.
        """
        # 1. Crear imagen original (Grande)
        img_original = Image.new("L", (500, 500), color=128) # Gris medio
        buf_orig = io.BytesIO()
        img_original.save(buf_orig, format="JPEG", quality=100)
        bytes_orig = buf_orig.getvalue()

        # 2. Crear imagen modificada (Pequeña y comprimida)
        img_small = img_original.resize((250, 250)) # Reducida un 50%
        buf_small = io.BytesIO()
        img_small.save(buf_small, format="JPEG", quality=50) # Baja calidad
        bytes_small = buf_small.getvalue()

        # 3. Calcular Hashes
        hash_orig = processor._compute_phash(bytes_orig)
        hash_small = processor._compute_phash(bytes_small)

        # 4. Verificar distancia
        distance = processor._hamming_distance(hash_orig, hash_small)
        
        # pHash es muy robusto, la distancia debería ser 0 o muy cercana a 0
        assert distance <= 5, f"La distancia de Hamming fue {distance}, se esperaba <= 5"

    def test_find_duplicate_logic(self, processor, mock_db):
        """Verifica la lógica de búsqueda en DB."""
        
        # Hash simulado de una imagen roja
        target_bytes = self.create_dummy_image_bytes(color="red")
        target_hash = processor._compute_phash(target_bytes)
        
        # Simular respuesta de DB:
        # Caso A: Un asset idéntico (distancia 0)
        # Caso B: Un asset muy distinto (distancia alta)
        mock_asset_match = (1, target_hash) # ID 1, Hash idéntico
        mock_asset_diff = (2, "0000ffff0000ffff") # ID 2, Hash invertido
        
        # Mockear la query
        mock_db.query.return_value.filter.return_value.with_entities.return_value.all.return_value = [
            mock_asset_diff, 
            mock_asset_match
        ]

        is_dup, asset_id, conf = processor.find_duplicate("tenant_1", target_bytes)

        assert is_dup is True
        assert asset_id == "1"
        assert conf == 1.0

    def test_no_duplicate_found(self, processor, mock_db):
        """Verifica que retorne False si no hay coincidencias cercanas."""
        target_bytes = self.create_dummy_image_bytes(color="blue")
        
        # DB vacía o con hashes lejanos
        mock_db.query.return_value.filter.return_value.with_entities.return_value.all.return_value = []

        is_dup, asset_id, conf = processor.find_duplicate("tenant_1", target_bytes)

        assert is_dup is False
        assert asset_id is None
