"""
Definición de constantes y espacios de nombres (Namespaces) para OOXML.
Referencia: ECMA-376 Standard.
"""

# Mapeo de prefijos a URIs oficiales de OOXML
OOXML_NAMESPACES = {
    # WordprocessingML Main
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    # Office Document Relationships
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    # DrawingML - Wordprocessing Drawing
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    # DrawingML - Main
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    # DrawingML - Picture
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    # Content Types
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    # Microsoft VML (Legacy) - A veces necesario para imágenes antiguas
    "v": "urn:schemas-microsoft-com:vml",
    # Word 2010 extensions (común en documentos modernos)
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    # Simple Types
    "xs": "http://www.w3.org/2001/XMLSchema",
    # Astra Custom Identifiers
    "astra": "https://astra.ai/ooxml"
}

# Rutas estándar dentro del ZIP (Sujeto a cambios si se lee [Content_Types].xml dinámicamente)
PATH_WORD_DOCUMENT = "word/document.xml"
PATH_STYLES = "word/styles.xml"
PATH_RELATIONSHIPS = "word/_rels/document.xml.rels"