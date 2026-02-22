import pytest
from src.core.parser.style_models import StyleDefinition
from src.core.parser.style_mapper import StyleMapper, ASTRA_HEADING_1, ASTRA_HEADING_2, ASTRA_BODY, ASTRA_LIST

class TestStyleMapper:
    @pytest.fixture
    def mapper(self):
        return StyleMapper()

    def test_exact_name_match(self, mapper):
        """Regla 1: Coincidencia por nombre."""
        styles = [
            StyleDefinition(style_id="1", name="Título 1", type="paragraph"),
            StyleDefinition(style_id="2", name="heading 2", type="paragraph")
        ]
        result = mapper.map_styles(styles)
        assert result["1"] == ASTRA_HEADING_1
        assert result["2"] == ASTRA_HEADING_2

    def test_outline_level_inference(self, mapper):
        """Regla 2 y 3: Inferencia por nivel de esquema."""
        styles = [
            StyleDefinition(style_id="x", name="Mi Estilo Raro", type="paragraph", outline_level=0),
            StyleDefinition(style_id="y", name="Subtitulo", type="paragraph", outline_level=1)
        ]
        result = mapper.map_styles(styles)
        assert result["x"] == ASTRA_HEADING_1
        assert result["y"] == ASTRA_HEADING_2

    def test_visual_format_inference(self, mapper):
        """Regla 4: Inferencia por tamaño y negrita."""
        styles = [
            # 14pt (28 medios puntos) + Bold -> Heading 1
            StyleDefinition(style_id="big", name="Grande", type="paragraph", font_size=28, is_bold=True),
            # 12pt + Bold -> Body (no es suficientemente grande para ser H1 por defecto en esta regla)
            StyleDefinition(style_id="small", name="Pequeño", type="paragraph", font_size=24, is_bold=True)
        ]
        result = mapper.map_styles(styles)
        assert result["big"] == ASTRA_HEADING_1
        assert result["small"] == ASTRA_BODY

    def test_list_detection(self, mapper):
        """Regla 5: Detección de listas."""
        styles = [StyleDefinition(style_id="l1", name="Párrafo de lista", type="paragraph")]
        result = mapper.map_styles(styles)
        assert result["l1"] == ASTRA_LIST

    def test_fallback(self, mapper):
        """Regla 6: Default a Body."""
        styles = [StyleDefinition(style_id="norm", name="Normal", type="paragraph")]
        result = mapper.map_styles(styles)
        assert result["norm"] == ASTRA_BODY

    def test_ignore_character_styles(self, mapper):
        """Debe ignorar estilos que no sean de párrafo."""
        styles = [StyleDefinition(style_id="c1", name="NegritaChar", type="character")]
        result = mapper.map_styles(styles)
        assert "c1" not in result
