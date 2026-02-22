import pytest
from unittest.mock import MagicMock
from src.core.mapping.auto_mapper import HeuristicMapper, BlockOccurrence, ZONE_HEADER, ZONE_BODY, ZONE_FOOTER

class TestHeuristicMapper:

    @pytest.fixture
    def mapper(self):
        return HeuristicMapper(db=MagicMock())

    def test_header_classification(self, mapper):
        """DoD: Posición media 0.05 debe ser HEADER."""
        # Simulamos 10 ocurrencias siempre al principio del documento
        occurrences = [
            BlockOccurrence("d1", 5, 100),  # 0.05
            BlockOccurrence("d2", 4, 100),  # 0.04
            BlockOccurrence("d3", 6, 100),  # 0.06
            BlockOccurrence("d4", 5, 100),
            BlockOccurrence("d5", 5, 100)
        ]
        
        stats = mapper.calculate_stats(occurrences)
        zone, conf = mapper.infer_zone(stats)
        
        assert zone == ZONE_HEADER
        assert conf > 0.8  # Confianza alta

    def test_footer_classification(self, mapper):
        """DoD: Posición media 0.95 debe ser FOOTER."""
        # Simulamos ocurrencias al final
        occurrences = [
            BlockOccurrence("d1", 95, 100), # 0.95
            BlockOccurrence("d2", 98, 100)  # 0.98
        ]
        
        stats = mapper.calculate_stats(occurrences)
        zone, conf = mapper.infer_zone(stats)
        
        assert zone == ZONE_FOOTER

    def test_body_classification(self, mapper):
        """Posición media 0.5 debe ser BODY."""
        occurrences = [BlockOccurrence("d1", 50, 100)] # 0.5
        
        stats = mapper.calculate_stats(occurrences)
        zone, _ = mapper.infer_zone(stats)
        
        assert zone == ZONE_BODY

    def test_high_variance_uncertainty(self, mapper):
        """
        DoD: Alta desviación estándar debe ir a BODY pero con baja confianza.
        Simula un texto que a veces está al principio (0.1) y a veces al final (0.9).
        """
        occurrences = [
            BlockOccurrence("d1", 10, 100), # 0.1
            BlockOccurrence("d2", 90, 100)  # 0.9
        ]
        
        stats = mapper.calculate_stats(occurrences)
        assert stats["std"] > mapper.MAX_STD_DEV # Verificar que la desviación es alta
        
        zone, conf = mapper.infer_zone(stats)
        
        assert zone == ZONE_BODY # Default safe zone
        assert conf < 0.6        # Confianza penalizada