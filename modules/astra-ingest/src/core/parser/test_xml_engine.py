import pytest
import zipfile
import io
import copy
from lxml import etree
from src.core.parser.xml_engine import DocxAtomizer
from src.core.constants import OOXML_NAMESPACES

# ... (Helper create_dummy_docx existente del T02a) ...
def create_dummy_docx(content_xml: str) -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zf:
        zf.writestr('word/document.xml', content_xml)
        zf.writestr('[Content_Types].xml', '<Types></Types>')
    buffer.seek(0)
    return buffer

class TestDocxAtomizer:
    # ... (Tests existentes T02a) ...
    pass

class TestDocxAtomizerSkeleton:
    """Tests específicos para la extracción de Skeleton (Fase1-T02b)."""

    def test_skeleton_sanitization(self):
        """Debe eliminar el texto de los nodos w:t pero mantener la estructura."""
        xml_content = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b'  <w:body>'
            b'    <w:p>'
            b'      <w:pPr><w:b/></w:pPr>' # Propiedad de párrafo
            b'      <w:r>'
            b'        <w:rPr><w:i/></w:rPr>' # Propiedad de run (cursiva)
            b'        <w:t>Texto Confidencial</w:t>' # TEXTO A BORRAR
            b'        <w:br/>' # Salto de línea (NO BORRAR)
            b'      </w:r>'
            b'    </w:p>'
            b'  </w:body>'
            b'</w:document>'
        )
        docx_file = create_dummy_docx(xml_content)

        with DocxAtomizer(docx_file) as atomizer:
            # Ejecutar extracción
            skeleton_root = atomizer.get_skeleton_tree()

            # 1. Verificar Inmutabilidad (El original debe tener texto)
            original_root = atomizer.document_tree.getroot()
            original_texts = original_root.xpath('//w:t', namespaces=OOXML_NAMESPACES)
            assert original_texts[0].text == "Texto Confidencial"

            # 2. Verificar Sanitización (El skeleton debe estar vacío)
            skeleton_texts = skeleton_root.xpath('//w:t', namespaces=OOXML_NAMESPACES)
            assert len(skeleton_texts) == 1
            assert skeleton_texts[0].text == ""

            # 3. Verificar Preservación Estructural
            # Debe existir el salto de línea <w:br/>
            br_nodes = skeleton_root.xpath('//w:br', namespaces=OOXML_NAMESPACES)
            assert len(br_nodes) == 1
            
            # Deben existir las propiedades <w:pPr> y <w:rPr>
            p_pr = skeleton_root.xpath('//w:pPr', namespaces=OOXML_NAMESPACES)
            assert len(p_pr) == 1
            
            r_pr = skeleton_root.xpath('//w:rPr', namespaces=OOXML_NAMESPACES)
            assert len(r_pr) == 1

    def test_skeleton_complex_structure(self):
        """Debe manejar tablas y estructuras anidadas sin romperlas."""
        xml_content = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b'  <w:body>'
            b'    <w:tbl>' # Tabla
            b'      <w:tr>' # Fila
            b'        <w:tc>' # Celda
            b'          <w:p><w:r><w:t>Dato 1</w:t></w:r></w:p>'
            b'        </w:tc>'
            b'        <w:tc>' # Celda
            b'          <w:p><w:r><w:t>Dato 2</w:t></w:r></w:p>'
            b'        </w:tc>'
            b'      </w:tr>'
            b'    </w:tbl>'
            b'    <w:p><w:r><w:drawing/></w:r></w:p>' # Imagen/Dibujo
            b'  </w:body>'
            b'</w:document>'
        )
        docx_file = create_dummy_docx(xml_content)

        with DocxAtomizer(docx_file) as atomizer:
            skeleton_root = atomizer.get_skeleton_tree()

            # Verificar que la tabla existe
            rows = skeleton_root.xpath('//w:tr', namespaces=OOXML_NAMESPACES)
            assert len(rows) == 1
            
            # Verificar celdas
            cells = skeleton_root.xpath('//w:tc', namespaces=OOXML_NAMESPACES)
            assert len(cells) == 2

            # Verificar que el texto se fue
            texts = skeleton_root.xpath('//w:t', namespaces=OOXML_NAMESPACES)
            for t in texts:
                assert t.text == ""

            # Verificar que el nodo de dibujo (w:drawing) persiste
            drawings = skeleton_root.xpath('//w:drawing', namespaces=OOXML_NAMESPACES)
            assert len(drawings) == 1

class TestDocxExtraction:
    """Tests específicos para la extracción de contenido (Fase1-T02b)."""

    def test_extract_content_simple(self):
        """Debe extraer texto de párrafos y mapear IDs con metadatos."""
        xml_content = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b'  <w:body>'
            b'    <w:p w:rsidR="ID_1">'
            b'      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            b'      <w:r><w:t>Hola</w:t></w:r>'
            b'    </w:p>'
            b'    <w:tbl w:rsidR="TBL_1">'
            b'      <w:tr><w:tc><w:p><w:r><w:t>Dato</w:t></w:r></w:p></w:tc></w:tr>'
            b'    </w:tbl>'
            b'  </w:body>'
            b'</w:document>'
        )
        docx_file = create_dummy_docx(xml_content)

        with DocxAtomizer(docx_file) as atomizer:
            content = atomizer.extract_content()

            assert len(content) == 2
            assert content[0]["id"] == "ID_1"
            assert content[0]["metadata"]["style"] == "Heading1"
            assert content[1]["type"] == "table"
            assert content[1]["id"] == "TBL_1"

    def test_skeleton_anchors(self):
        """Debe inyectar astra:id para anclaje determinista."""
        xml_content = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b'  <w:body>'
            b'    <w:p w:rsidR="P1"><w:r><w:t>T1</w:t></w:r></w:p>'
            b'  </w:body>'
            b'</w:document>'
        )
        docx_file = create_dummy_docx(xml_content)
        ASTRA_NS = "https://astra.ai/ooxml"

        with DocxAtomizer(docx_file) as atomizer:
            skeleton_tree = atomizer.get_skeleton_tree()
            p = skeleton_tree.xpath('//w:p', namespaces=OOXML_NAMESPACES)[0]
            
            # Verificar inyección de ancla
            assert p.get(f"{{{ASTRA_NS}}}id") == "P1"
            # Verificar sanitización de texto
            assert p.xpath('.//w:t', namespaces=OOXML_NAMESPACES)[0].text == ""
    def test_skeleton_dynamic_table(self):
        """Debe identificar una tabla dinámica, podarla e inyectar la fila molde."""
        xml_content = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b'  <w:body>'
            b'    <w:tbl w:rsidR="TBL1">'
            b'      <w:tr>' # Header
            b'        <w:tc><w:p><w:r><w:t>Nombre</w:t></w:r></w:p></w:tc>'
            b'      </w:tr>'
            b'      <w:tr>' # Body (Template Candidate)
            b'        <w:tc><w:p><w:r><w:t>Juan Perez</w:t></w:r></w:p></w:tc>'
            b'      </w:tr>'
            b'      <w:tr>' # Body (Extra data)
            b'        <w:tc><w:p><w:r><w:t>Maria Lopez</w:t></w:r></w:p></w:tc>'
            b'      </w:tr>'
            b'    </w:tbl>'
            b'  </w:body>'
            b'</w:document>'
        )
        docx_file = create_dummy_docx(xml_content)
        ASTRA_NS = "https://astra.ai/ooxml"

        with DocxAtomizer(docx_file) as atomizer:
            skeleton_tree = atomizer.get_skeleton_tree()
            
            # 1. Verificar que la tabla en el skeleton tiene exactamente 2 filas (Header + Template)
            rows = skeleton_tree.xpath('//w:tr', namespaces=OOXML_NAMESPACES)
            assert len(rows) == 2
            
            # 2. Verificar que la segunda fila tiene el marcador de template
            template_row = rows[1]
            assert template_row.get(f"{{{ASTRA_NS}}}rowType") == "template"
            
            # 3. Verificar que el texto de la template row está vacío (sanitizado)
            t_node = template_row.xpath('.//w:t', namespaces=OOXML_NAMESPACES)[0]
            assert (t_node.text or "") == ""

            # 4. Verificar que el ID de la tabla fue inyectado
            tbl_node = skeleton_tree.xpath('//w:tbl', namespaces=OOXML_NAMESPACES)[0]
            astra_tbl_id = tbl_node.get(f"{{{ASTRA_NS}}}tblId")
            assert astra_tbl_id is not None
            
            # 5. Verificar que el blob XML fue capturado en el atomizer
            assert astra_tbl_id in atomizer.dynamic_tables
            assert b'Juan Perez' not in atomizer.dynamic_tables[astra_tbl_id]
