import pytest
import os
import zipfile
import subprocess
import shutil
from pathlib import Path
from lxml import etree
from src.core.parser.xml_engine import DocxAtomizer
from src.core.constants import OOXML_NAMESPACES

# Directorio temporal para artefactos de prueba
TEST_OUTPUT_DIR = Path("tests/e2e/output")

@pytest.fixture(scope="module", autouse=True)
def setup_teardown():
    """Crea y limpia el directorio de outputs."""
    os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)
    yield
    # Comentar la siguiente línea si se desea inspeccionar los archivos generados post-test
    shutil.rmtree(TEST_OUTPUT_DIR)

def create_valid_docx(path: Path):
    """Crea un DOCX mínimo válido físicamente en disco."""
    content_xml = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b'  <w:body>'
        b'    <w:p><w:r><w:t>Hola Mundo</w:t></w:r></w:p>'
        b'  </w:body>'
        b'</w:document>'
    )
    rels_xml = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'</Relationships>'
    )
    content_types_xml = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        b'  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        b'  <Default Extension="xml" ContentType="application/xml"/>'
        b'  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        b'</Types>'
    )

    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('word/document.xml', content_xml)
        zf.writestr('_rels/.rels', rels_xml)
        zf.writestr('[Content_Types].xml', content_types_xml)

class TestDocxIntegrity:

    def test_round_trip_integrity(self):
        """
        Prueba de ciclo completo:
        1. Crear DOCX
        2. Leer con Atomizer
        3. Generar Skeleton (modificar)
        4. Guardar como nuevo DOCX
        5. Verificar que es un ZIP válido y XML legible
        """
        input_path = TEST_OUTPUT_DIR / "source.docx"
        output_path = TEST_OUTPUT_DIR / "generated_skeleton.docx"
        create_valid_docx(input_path)

        # Paso 2 y 3: Leer y extraer Skeleton
        with DocxAtomizer(input_path) as atomizer:
            skeleton_tree = atomizer.get_skeleton_tree()
            
            # Paso 4: Guardar el Skeleton
            atomizer.save(output_path, custom_tree=skeleton_tree)

        # Paso 5: Verificaciones
        assert output_path.exists()
        assert zipfile.is_zipfile(output_path)

        # Verificar contenido interno del archivo generado
        with zipfile.ZipFile(output_path, 'r') as zf:
            # a. Integridad estructural ZIP
            assert 'word/document.xml' in zf.namelist()
            assert '[Content_Types].xml' in zf.namelist()
            
            # b. Integridad XML (debe ser parseable)
            xml_content = zf.read('word/document.xml')
            root = etree.fromstring(xml_content)
            
            # c. Verificar que los cambios se aplicaron (Skeleton vacío)
            texts = root.xpath('//w:t', namespaces=OOXML_NAMESPACES)
            for t in texts:
                assert t.text == "" or t.text is None
            
            # d. Verificar declaración XML (Standalone)
            # lxml tostring incluye la declaración, verificamos bytes crudos
            assert b'standalone="yes"' in xml_content or b"standalone='yes'" in xml_content

    @pytest.mark.skipif(shutil.which("libreoffice") is None, reason="LibreOffice no instalado")
    def test_libreoffice_smoke_test(self):
        """
        Intenta convertir el DOCX generado a PDF usando LibreOffice headless.
        Si LibreOffice falla, el DOCX probablemente está corrupto estructuralmente.
        """
        input_path = TEST_OUTPUT_DIR / "smoke_source.docx"
        output_docx = TEST_OUTPUT_DIR / "smoke_output.docx"
        create_valid_docx(input_path)

        # Generar archivo
        with DocxAtomizer(input_path) as atomizer:
            atomizer.save(output_docx)

        # Ejecutar conversión
        # libreoffice --headless --convert-to pdf --outdir <dir> <file>
        result = subprocess.run(
            [
                "libreoffice", "--headless", "--convert-to", "pdf",
                "--outdir", str(TEST_OUTPUT_DIR), str(output_docx)
            ],
            capture_output=True,
            text=True
        )

        # Si el exit code es 0, LibreOffice pudo abrir y procesar el archivo
        if result.returncode != 0:
            pytest.fail(f"LibreOffice rechazó el archivo generado: {result.stderr}")
        
        expected_pdf = TEST_OUTPUT_DIR / "smoke_output.pdf"
        assert expected_pdf.exists()