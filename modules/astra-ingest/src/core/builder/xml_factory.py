from lxml import etree
import copy
from src.core.constants import OOXML_NAMESPACES
from src.core.nlp.alignment_engine import TemplateModel

class XmlFactory:
    """
    Generador de fragmentos XML OOXML compatibles con Word.
    Encapsula variables dinámicas en etiquetas <w:sdt> (Structured Document Tags).
    """

    def __init__(self):
        self.ns = OOXML_NAMESPACES
        self.w = f"{{{self.ns['w']}}}"

    def generate_ooxml_template(self, model: TemplateModel, reference_node: etree._Element) -> bytes:
        """
        Genera el XML de la sub-plantilla heredando estilos del nodo de referencia.
        
        Args:
            model: El modelo lógico (tokens estáticos/variables).
            reference_node: El elemento <w:p> original para copiar propiedades (pPr, rPr).
        """
        # 1. Crear nodo párrafo base <w:p>
        p = etree.Element(f"{self.w}p", nsmap=self.ns)
        
        # 2. Copiar propiedades de párrafo (<w:pPr>) si existen
        p_pr = reference_node.find(f"{self.w}pPr")
        if p_pr is not None:
            p.append(copy.deepcopy(p_pr))

        # 3. Extraer propiedades de run base (<w:rPr>) para heredar fuente/tamaño
        # Buscamos el primer run que tenga propiedades para usarlo como base
        base_r_pr = None
        first_run = reference_node.find(f"{self.w}r")
        if first_run is not None:
            base_r_pr = first_run.find(f"{self.w}rPr")

        # 4. Construir el contenido con Fusión de Runs (Run Merger)
        static_buffer = []

        def flush_static():
            if static_buffer:
                # Crear un solo Run para todo el texto acumulado
                run = etree.SubElement(p, f"{self.w}r")
                if base_r_pr is not None:
                    run.append(copy.deepcopy(base_r_pr))
                
                t = etree.SubElement(run, f"{self.w}t")
                t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                t.text = "".join(static_buffer)
                static_buffer.clear()

        for token in model.tokens:
            if token.is_variable:
                flush_static()  # Primero soltamos lo que tengamos acumulado
                
                # Crear Content Control (<w:sdt>)
                sdt = etree.SubElement(p, f"{self.w}sdt")
                sdt_pr = etree.SubElement(sdt, f"{self.w}sdtPr")
                alias = etree.SubElement(sdt_pr, f"{self.w}alias")
                alias.set(f"{self.w}val", token.variable_name)
                tag = etree.SubElement(sdt_pr, f"{self.w}tag")
                tag.set(f"{self.w}val", token.variable_name)
                
                sdt_content = etree.SubElement(sdt, f"{self.w}sdtContent")
                run = etree.SubElement(sdt_content, f"{self.w}r")
                if base_r_pr is not None:
                    run.append(copy.deepcopy(base_r_pr))
                    
                t = etree.SubElement(run, f"{self.w}t")
                t.text = f"{{{{ {token.variable_name} }}}}"
            else:
                # Acumulamos el texto estático con su espacio
                static_buffer.append(token.text + " ")

        # Flush final para cualquier texto restante
        flush_static()

        return etree.tostring(p, encoding='utf-8', xml_declaration=False)