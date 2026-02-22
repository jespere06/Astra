import re
from xml.sax.saxutils import escape

class XmlSanitizer:
    """
    Garantiza que el texto inyectado no rompa el XML y previene inyecciones.
    """
    # Caracteres de control ASCII inválidos en XML 1.0 (excepto tab, CR, LF)
    _ILLEGAL_XML_CHARS_RE = re.compile(
        r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f\ud800-\udfff\ufdd0-\ufddf\ufffe\uffff]'
    )

    @classmethod
    def sanitize(cls, text: str) -> str:
        if not text:
            return ""
        
        # 1. Eliminar caracteres de control ilegales
        clean_text = cls._ILLEGAL_XML_CHARS_RE.sub('', text)
        
        # 2. Escapar caracteres reservados de XML (<, >, &, ", ')
        # lxml maneja esto al asignar .text, pero para atributos o inyecciones manuales es vital.
        return escape(clean_text)

    @classmethod
    def validate_namespace(cls, node_tag: str, allowed_namespaces: dict) -> bool:
        """Verifica que el tag pertenezca a un namespace conocido."""
        if not node_tag.startswith('{'):
            return False
        ns_url = node_tag[1:].split('}')[0]
        return ns_url in allowed_namespaces.values()
