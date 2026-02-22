import zipfile
import logging
from typing import List, Dict, Optional
from lxml import etree
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TextSegment:
    chunk_id: Optional[str]
    text: str
    order_index: int
    styles: Dict[str, str]

class ForensicExtractor:
    """
    Analiza un archivo DOCX (OOXML) buscando rastros de auditoría (chunk_ids)
    inyectados por ASTRA-BUILDER, sobreviviendo a ediciones en Word.
    """
    
    # Namespaces estándar y custom de ASTRA
    NS = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'astra': 'https://astra.ai/ooxml'
    }

    def extract_segments(self, docx_path: str) -> List[TextSegment]:
        try:
            with zipfile.ZipFile(docx_path, 'r') as zf:
                xml_content = zf.read('word/document.xml')
                
            root = etree.fromstring(xml_content)
            segments = []
            
            # Iterar sobre párrafos
            for idx, p_node in enumerate(root.xpath('//w:p', namespaces=self.NS)):
                # 1. Intentar recuperar ID explícito (Inyectado por Builder)
                # El Builder inyecta astra:chunkId="{UUID}" en w:p
                chunk_id = p_node.get(f"{{{self.NS['astra']}}}chunkId")
                
                # 2. Si no hay ID explícito, buscar en los runs (w:r) por si el ID se movió
                if not chunk_id:
                    # Buscar en atributos de la propiedad del párrafo (w:pPr)
                    ppr = p_node.find('w:pPr', namespaces=self.NS)
                    if ppr is not None:
                        chunk_id = ppr.get(f"{{{self.NS['astra']}}}chunkId")

                # 3. Extraer texto limpio concatenando todos los runs
                texts = p_node.xpath('.//w:t/text()', namespaces=self.NS)
                full_text = "".join(texts).strip()

                # 4. Extraer estilos básicos (Bold, Italic, Style Name)
                styles = {}
                p_style = p_node.xpath('.//w:pStyle/@w:val', namespaces=self.NS)
                if p_style:
                    styles['paragraph_style'] = p_style[0]

                if full_text: # Ignorar párrafos vacíos
                    segments.append(TextSegment(
                        chunk_id=chunk_id,
                        text=full_text,
                        order_index=idx,
                        styles=styles
                    ))
            
            logger.info(f"Extraídos {len(segments)} segmentos del documento final.")
            return segments

        except Exception as e:
            logger.error(f"Error forense extrayendo metadata: {e}")
            raise ValueError(f"Documento corrupto o ilegible: {str(e)}")
