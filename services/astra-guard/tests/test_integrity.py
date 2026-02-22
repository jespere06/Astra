import io
import zipfile
import pytest
from src.crypto.normalizer import OOXMLNormalizer
from src.crypto.merkle import MerkleEngine

def create_docx_mock(files: dict) -> io.BytesIO:
    """Crea un ZIP en memoria con el contenido dado."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    buf.seek(0)
    return buf

class TestIntegrityEngine:
    
    def test_ignore_metadata_changes(self):
        """
        DoD: Dos archivos con contenido idéntico pero metadata distinta
        deben generar el MISMO Root Hash.
        """
        # Archivo 1: Original
        doc1 = create_docx_mock({
            "word/document.xml": b"<xml>Contenido</xml>",
            "docProps/core.xml": b"<core>Creado hoy</core>", # Metadata
            "word/styles.xml": b"<style>Normal</style>"
        })
        
        # Archivo 2: Abierto y guardado (Metadata cambia)
        doc2 = create_docx_mock({
            "word/document.xml": b"<xml>Contenido</xml>",
            "docProps/core.xml": b"<core>Modificado manana</core>", # CAMBIO AQUÍ
            "word/styles.xml": b"<style>Normal</style>"
        })

        # Procesar Doc 1
        norm1 = OOXMLNormalizer(doc1)
        root1 = MerkleEngine().calculate_root(norm1.get_canonical_stream())["root_hash"]

        # Procesar Doc 2
        norm2 = OOXMLNormalizer(doc2)
        root2 = MerkleEngine().calculate_root(norm2.get_canonical_stream())["root_hash"]

        assert root1 == root2, "El hash cambió por metadatos volátiles. Fallo en normalización."

    def test_detect_content_changes(self):
        """
        DoD: Un cambio mínimo en el contenido debe cambiar el hash.
        """
        doc1 = create_docx_mock({"word/document.xml": b"Hola"})
        doc2 = create_docx_mock({"word/document.xml": b"Hole"}) # Cambio 1 letra

        norm1 = OOXMLNormalizer(doc1)
        root1 = MerkleEngine().calculate_root(norm1.get_canonical_stream())["root_hash"]

        norm2 = OOXMLNormalizer(doc2)
        root2 = MerkleEngine().calculate_root(norm2.get_canonical_stream())["root_hash"]

        assert root1 != root2, "El hash NO cambió a pesar de contenido distinto."
        
    def test_determinism(self):
        """
        Asegura que el orden de los archivos en el ZIP no afecte al hash.
        """
        files1 = {
            "a.xml": b"1",
            "b.xml": b"2"
        }
        files2 = {
            "b.xml": b"2",
            "a.xml": b"1"
        }
        
        doc1 = create_docx_mock(files1)
        doc2 = create_docx_mock(files2)
        
        root1 = MerkleEngine().calculate_root(OOXMLNormalizer(doc1).get_canonical_stream())["root_hash"]
        root2 = MerkleEngine().calculate_root(OOXMLNormalizer(doc2).get_canonical_stream())["root_hash"]
        
        assert root1 == root2, "El orden de archivos en el ZIP afectó al hash (Fallo de determinismo)."
