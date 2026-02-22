import re
import logging
from typing import Tuple, List, Optional
from lxml import etree
import spacy

logger = logging.getLogger(__name__)

class TemplateValidator:
    def __init__(self):
        # Intentar cargar modelo español de spacy para NER
        try:
            self.nlp = spacy.load("es_core_news_lg")
        except:
            logger.warning("No se encontró es_core_news_lg, intentando sm...")
            try:
                self.nlp = spacy.load("es_core_news_sm")
            except:
                logger.error("No se pudo cargar ningún modelo de spacy para NER.")
                self.nlp = None

    def validate(self, 
                 raw_pattern: str, 
                 cluster_size: int, 
                 xml_bytes: bytes,
                 tenant_id: str = "") -> Tuple[bool, str]:
        """
        Ejecuta los 5 KPIs de calidad ASTRA.
        Retorna (es_valido, motivo_rechazo).
        """
        
        # 1. Integridad Estructural XML
        try:
            root = etree.fromstring(xml_bytes)
            tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
            if tag not in ['p', 'tbl']:
                return False, f"Estructura XML inválida: root es {tag}, debe ser p o tbl"
            
            # Verificar propiedades de párrafo
            # ns = root.nsmap
            # w = f"{{{ns['w']}}}" if 'w' in ns else ""
            if tag == 'p' and not any('pPr' in c.tag for c in root):
                 # No es crítico pero deseable, lo dejamos pasar si tiene contenido
                 pass
        except Exception as e:
            return False, f"Error parseando XML: {str(e)}"

        # Limpiar texto para análisis (quitar marcadores de variable)
        clean_text = re.sub(r'\{VAR_\d+\}', '', raw_pattern).strip()
        words = clean_text.split()

        # 2. La Longitud Semántica Mínima (Token Floor)
        if len(words) < 5:
            return False, f"Demasiado corto ({len(words)} palabras), probablemente ruido"

        # 3. La Relación Estático/Variable (Boilerplate Ratio)
        static_chars = len(clean_text)
        total_chars = len(raw_pattern)
        ratio = static_chars / total_chars if total_chars > 0 else 0
        
        if ratio < 0.3:
            return False, f"Relación estático/variable muy baja ({ratio:.2f}), demasiado genérico"
        # Si ratio > 0.95, se considera Boilerplate (se acepta pero el llamador decide si lo marca)

        # 4. La Densidad de Cluster (Consensus Check)
        if cluster_size < 5:
            return False, f"Frecuencia insuficiente (Cluster size: {cluster_size})"

        # 5. El Índice de Anonimato (Privacy Score)
        if self.nlp:
            doc = self.nlp(clean_text)
            for ent in doc.ents:
                if ent.label_ == "PER":
                    # Si es una persona y no parece un cargo común (Secretario, etc.)
                    # Simplificación: Rechazar cualquier PER detectado en estático
                    return False, f"Privacidad: Se detectó nombre propio '{ent.text}' en texto estático"
                
                if ent.label_ == "LOC":
                    # Si el lugar no contiene el nombre del tenant/municipio (muy básico)
                    if tenant_id and tenant_id.lower() not in ent.text.lower():
                        logger.warning(f"Posible locación específica detectada: {ent.text}")
                        # No bloqueamos LOC por ahora para evitar falsos positivos agresivos
                        pass

        return True, "Calidad ASTRA Aprobada"

if __name__ == "__main__":
    # Test rápido
    validator = TemplateValidator()
    test_xml = b'<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:pPr/><w:r><w:t>Hola mundo</w:t></w:r></w:p>'
    
    # Caso: Muy corto
    print(validator.validate("Hola mundo", 10, test_xml))
    
    # Caso: Frecuencia baja
    print(validator.validate("Este es un texto largo para pasar el test", 2, test_xml))
    
    # Caso: Nombre propio (si NER funciona)
    print(validator.validate("El secretario Juan Perez saluda a la audiencia", 10, test_xml))
    
    # Caso: Válido
    print(validator.validate("Por medio del cual se modifica el artículo segundo del acuerdo", 10, test_xml))
