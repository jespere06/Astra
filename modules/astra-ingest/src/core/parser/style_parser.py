from lxml import etree
from typing import List
from src.core.constants import OOXML_NAMESPACES
from src.core.parser.style_models import StyleDefinition

class StyleParser:
    def __init__(self):
        self.ns = OOXML_NAMESPACES

    def parse_styles_xml(self, xml_tree: etree._ElementTree) -> List[StyleDefinition]:
        """
        Extrae definiciones de estilos desde un árbol XML de styles.xml.
        """
        styles = []
        root = xml_tree.getroot()
        
        # Iterar sobre todos los nodos <w:style>
        for style_node in root.xpath('//w:style', namespaces=self.ns):
            style_type = style_node.get(f"{{{self.ns['w']}}}type")
            
            # Solo nos interesan estilos de párrafo y caracter para el MVP
            if style_type not in ['paragraph', 'character']:
                continue

            style_id = style_node.get(f"{{{self.ns['w']}}}styleId")
            is_default = style_node.get(f"{{{self.ns['w']}}}default") == '1'
            
            # 1. Extraer Nombre
            name_node = style_node.find('w:name', namespaces=self.ns)
            name = name_node.get(f"{{{self.ns['w']}}}val") if name_node is not None else style_id

            # 2. Extraer Propiedades de Párrafo (Outline Level)
            outline_lvl = None
            p_pr = style_node.find('w:pPr', namespaces=self.ns)
            if p_pr is not None:
                outline_node = p_pr.find('w:outlineLvl', namespaces=self.ns)
                if outline_node is not None:
                    try:
                        outline_lvl = int(outline_node.get(f"{{{self.ns['w']}}}val"))
                    except (ValueError, TypeError):
                        pass

            # 3. Extraer Propiedades de Run (Formato: Negrita, Tamaño)
            font_size = None
            is_bold = False
            is_italic = False
            
            r_pr = style_node.find('w:rPr', namespaces=self.ns)
            if r_pr is not None:
                # Negrita
                if r_pr.find('w:b', namespaces=self.ns) is not None:
                    is_bold = True
                
                # Cursiva
                if r_pr.find('w:i', namespaces=self.ns) is not None:
                    is_italic = True
                
                # Tamaño (Word usa medios puntos, ej: 24 = 12pt)
                sz_node = r_pr.find('w:sz', namespaces=self.ns)
                if sz_node is not None:
                    try:
                        font_size = int(sz_node.get(f"{{{self.ns['w']}}}val"))
                    except (ValueError, TypeError):
                        pass

            styles.append(StyleDefinition(
                style_id=style_id,
                name=name,
                type=style_type,
                is_default=is_default,
                outline_level=outline_lvl,
                font_size=font_size,
                is_bold=is_bold,
                is_italic=is_italic
            ))

        return styles