import pytest
import time
from src.nlp.cleaner import TextSanitizer

class TestTextSanitizer:
    @pytest.fixture
    def sanitizer(self):
        return TextSanitizer()

    def test_basic_cleaning(self, sanitizer):
        raw = "   hola   mundo  "
        assert sanitizer.clean(raw) == "Hola mundo"

    def test_fillers_removal(self, sanitizer):
        """DoD: Eliminación de muletillas"""
        raw = "eh... bueno pues, vamos a iniciar mmm la sesión"
        # "..." se reduce a "." por dedup_punct, "eh" y "mmm" se van, "bueno pues" se va
        expected = ". , vamos a iniciar la sesión" 
        # Nota: La puntuación suelta suele quedar, el modelo de Puntuación (COR-02b) la arreglará después.
        # El sanitizer se enfoca en palabras.
        cleaned = sanitizer.clean(raw)
        
        # Verificamos que las palabras clave hayan desaparecido
        assert "eh" not in cleaned
        assert "mmm" not in cleaned
        assert "bueno pues" not in cleaned
        assert "iniciar" in cleaned

    def test_contractions_expansion(self, sanitizer):
        """DoD: Expansión de contracciones"""
        raw = "esto es pa todos los del concejo"
        assert sanitizer.clean(raw) == "Esto es para todos los del concejo"

    def test_case_preservation_in_contraction(self, sanitizer):
        raw = "PA lante"
        assert sanitizer.clean(raw) == "PARA lante"
        
        raw = "Pa lante"
        assert sanitizer.clean(raw) == "Para lante"

    def test_punctuation_deduplication(self, sanitizer):
        raw = "Hola mundo... todo bien??"
        assert sanitizer.clean(raw) == "Hola mundo. todo bien?"

    def test_proper_name_protection(self, sanitizer):
        """Riesgo: No borrar partes de nombres propios"""
        # "Ana" contiene "na" (nada), "Emanuel" contiene "el" (no está en fillers pero es test de boundary)
        # Probemos con una muletilla que sea subcadena.
        # "Mente" contiene "te" (si "te" fuera muletilla).
        # Probemos "Este" (muletilla) vs "Esteban" (Nombre).
        
        raw = "Este documento es de Esteban"
        # "Este" al inicio es muletilla (según constants), "Esteban" debe quedar intacto.
        clean = sanitizer.clean(raw)
        
        assert "Esteban" in clean
        # La lógica actual borra "Este" si está en fillers.
        # Si el contexto ASR pone "Este..." como muletilla, se borra.

    def test_performance(self, sanitizer):
        """DoD: < 50ms para 500 palabras"""
        long_text = "hola pa todos eh " * 100 # ~400-500 palabras
        start = time.time()
        sanitizer.clean(long_text)
        end = time.time()
        duration_ms = (end - start) * 1000
        
        print(f"\nPerformance: {duration_ms:.2f}ms")
        assert duration_ms < 50

    def test_unicode_normalization(self, sanitizer):
        # Texto con tilde combinada (dos caracteres) vs precompuesta
        nfd_text = "camio\u0301n" # 'o' + '´'
        nfc_text = "camión"      # 'ó'
        
        assert sanitizer.clean(nfd_text) == "Camión"
        assert sanitizer.clean(nfd_text) == sanitizer.clean(nfc_text)

    def test_empty_input(self, sanitizer):
        assert sanitizer.clean(None) == ""
        assert sanitizer.clean("") == ""
