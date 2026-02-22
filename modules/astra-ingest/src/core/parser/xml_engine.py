import zipfile
import copy
from pathlib import Path
from typing import Union, BinaryIO, Optional
from lxml import etree
from .table_analyzer import TableAnalyzer
from .table_standardizer import TableStandardizer
from .table.models import RowClassification

from src.core.constants import OOXML_NAMESPACES, PATH_WORD_DOCUMENT
from src.core.exceptions import DocxFormatError, OOXMLError, AstraIngestError

class DocxAtomizer:
    """
    Encargado de abrir, validar, parsear y GUARDAR archivos .docx.
    """

    def __init__(self, source: Union[str, Path, BinaryIO]):
        self._source = source
        self._zip_file: Optional[zipfile.ZipFile] = None
        self._document_tree: Optional[etree._ElementTree] = None
        self.dynamic_tables: dict[str, bytes] = {} # astra_id -> xml_template_row
        
        # Configuración de Seguridad del Parser XML
        self._parser = etree.XMLParser(
            resolve_entities=False,
            no_network=True,
            huge_tree=False,
            recover=False
        )

        self._open_zip()

    def _open_zip(self):
        """Abre el contenedor ZIP validando que sea un archivo accesible."""
        try:
            self._zip_file = zipfile.ZipFile(self._source, 'r')
        except zipfile.BadZipFile as e:
            raise DocxFormatError(f"El archivo no es un contenedor ZIP válido: {e}")
        except FileNotFoundError:
            raise DocxFormatError(f"No se encontró el archivo: {self._source}")
    
    def _load_xml(self, filename: str) -> etree._ElementTree:
        """Extrae y parsea un archivo XML interno del ZIP."""
        if filename not in self._zip_file.namelist():
            raise OOXMLError(f"El archivo requerido '{filename}' no existe en el paquete DOCX.")

        try:
            with self._zip_file.open(filename) as f:
                xml_bytes = f.read()
            # Parsear creando un ElementTree completo
            return etree.ElementTree(etree.fromstring(xml_bytes, parser=self._parser))
            
        except etree.XMLSyntaxError as e:
            raise OOXMLError(f"Error de sintaxis XML en '{filename}': {e}")
        except Exception as e:
            raise AstraIngestError(f"Error inesperado procesando '{filename}': {e}")

    @property
    def document_tree(self) -> etree._ElementTree:
        """Retorna el árbol DOM parseado de 'word/document.xml'."""
        if self._document_tree is None:
            self._document_tree = self._load_xml(PATH_WORD_DOCUMENT)
        return self._document_tree

    @property
    def namespaces(self) -> dict:
        return OOXML_NAMESPACES

    def _get_node_style(self, node: etree._Element) -> Optional[str]:
        """Extrae el nombre del estilo aplicado a un párrafo o run."""
        w_ns = self.namespaces['w']
        # Buscar en w:pPr/w:pStyle o w:rPr/w:rStyle
        style_node = node.xpath('.//w:pStyle | .//w:rStyle', namespaces=self.namespaces)
        if style_node:
            return style_node[0].get(f'{{{w_ns}}}val')
        return None

    def _get_node_metadata(self, node: etree._Element) -> dict:
        """Extrae metadatos de formato (negrita, cursiva, etc.)."""
        metadata = {}
        style = self._get_node_style(node)
        if style:
            metadata["style"] = style
        
        # Bold/Italic check in rPr
        if node.tag.endswith('}r'):
            if node.xpath('.//w:b', namespaces=self.namespaces): metadata["bold"] = True
            if node.xpath('.//w:i', namespaces=self.namespaces): metadata["italic"] = True
        
        return metadata

    def extract_content(self) -> list[dict]:
        """
        Extrae el contenido textual mapeado a IDs estructurales y metadatos.
        Implementación Recursiva de Alta Fidelidad.
        """
        results = []
        w_ns = self.namespaces['w']
        
        # Buscamos todos los párrafos y tablas en el cuerpo
        # El orden de aparición es crucial para la reconstrucción
        body = self.document_tree.xpath('//w:body', namespaces=self.namespaces)[0]
        
        for i, node in enumerate(body.xpath('./w:p | ./w:tbl', namespaces=self.namespaces)):
            node_id = node.get(f'{{{w_ns}}}rsidR') or f"node_{i}"
            
            if node.tag.endswith('}p'):
                text = "".join(node.xpath('.//w:t/text()', namespaces=self.namespaces))
                if text.strip():
                    results.append({
                        "id": node_id,
                        "text": text,
                        "type": "paragraph",
                        "metadata": self._get_node_metadata(node)
                    })
            elif node.tag.endswith('}tbl'):
                # Extracción básica de tablas (puede expandirse a celdas individuales)
                table_text = " ".join(node.xpath('.//w:t/text()', namespaces=self.namespaces))
                if table_text.strip():
                    results.append({
                        "id": node_id,
                        "text": table_text,
                        "type": "table",
                        "metadata": {"rows": len(node.xpath('.//w:tr', namespaces=self.namespaces))}
                    })
                
        return results

    def extract_raw_xml_blocks(self) -> list[dict]:
        """
        Extrae bloques de párrafos en formato XML crudo (incluyendo estilos)
        para el dataset de entrenamiento semántico. (Fase 5-T01)
        """
        results = []
        w_ns = self.namespaces['w']
        body = self.document_tree.xpath('//w:body', namespaces=self.namespaces)[0]

        for i, node in enumerate(body.xpath('./w:p', namespaces=self.namespaces)):
            # ID determinista o existente
            node_id = node.get(f'{{{w_ns}}}rsidR') or f"p_{i}"
            
            # Texto plano para alineación
            text = "".join(node.xpath('.//w:t/text()', namespaces=self.namespaces))
            
            # XML Crudo (bytes -> str)
            # method='xml' asegura que no se pierdan namespaces
            xml_bytes = etree.tostring(node, encoding='UTF-8', method='xml')
            xml_str = xml_bytes.decode('utf-8')

            if text.strip():  # Solo extraer si tiene contenido visible
                results.append({
                    "id": node_id,
                    "xml": xml_str,
                    "text": text
                })
        
        return results

    def get_skeleton_tree(self) -> etree._ElementTree:
        """
        Genera un Skeleton inyectando 'astra:id' para anclaje determinista.
        También detecta y estandariza tablas dinámicas.
        """
        skeleton_tree = copy.deepcopy(self.document_tree)
        root = skeleton_tree.getroot()
        
        # Registrar namespace personalizado para anclas
        ASTRA_NS = "https://astra.ai/ooxml"
        
        w_ns = self.namespaces['w']
        w_t_tag = f"{{{w_ns}}}t"

        analyzer = TableAnalyzer()
        standardizer = TableStandardizer()
        self.dynamic_tables = {} # Resetear para cada run

        # 1. Limpiar texto e inyectar anclas
        body = root.xpath('//w:body', namespaces=self.namespaces)[0]
        
        # Procesar nodos descendientes de body (p y tbl)
        # Usamos list para evitar problemas al modificar el árbol si fuera necesario
        for i, node in enumerate(body.xpath('./w:p | ./w:tbl', namespaces=self.namespaces)):
            # Inyectar ID de ancla
            node_id = node.get(f'{{{w_ns}}}rsidR') or f"node_{i}"
            node.set(f"{{{ASTRA_NS}}}id", node_id)
            
            if node.tag.endswith('}p'):
                # Limpiar contenido de texto
                for t in node.iter(w_t_tag):
                    t.text = ""
            
            elif node.tag.endswith('}tbl'):
                # Análisis de Tabla Dinámica
                result = analyzer.analyze_table(node)
                if result.is_dynamic_candidate:
                    # Guardar el blob XML para el Builder
                    self.dynamic_tables[result.astra_id] = result.xml_template_row
                    
                    # Ejecutar estandarización (poda de filas de datos)
                    # Si no hay clasificación explícita aún, creamos una heurística básica:
                    # TODO: Mover esto al Detector de Patrones en Fase 1-T11.1c
                    if not result.row_classification:
                        row_count = len(node.xpath('./w:tr', namespaces=self.namespaces))
                        result.row_classification = RowClassification(
                            header_indices=[0] if row_count > 0 else [],
                            body_indices=list(range(1, row_count)) if row_count > 1 else []
                        )
                    
                    standardizer.standardize_table(
                        node, 
                        result.row_classification, 
                        result.xml_template_row
                    )
                else:
                    # Si no es dinámica, simplemente limpiamos el texto de todas sus celdas
                    for t in node.iter(w_t_tag):
                        t.text = ""
            
        return skeleton_tree

    def save(self, output_path: Union[str, Path], custom_tree: Optional[etree._ElementTree] = None):
        """
        Reconstruye el archivo .docx guardando los cambios.
        
        Estrategia 'Copy-Replace': Copia bit a bit todos los archivos del ZIP original
        excepto 'word/document.xml', el cual es serializado desde la memoria.

        Args:
            output_path: Ruta donde se guardará el nuevo archivo .docx.
            custom_tree: (Opcional) Si se provee, serializa este árbol en lugar del 
                         self.document_tree interno. Útil para guardar Skeletons.
        """
        target_tree = custom_tree if custom_tree is not None else self.document_tree
        
        try:
            # Pre-serializar el XML para asegurar que es válido antes de abrir el ZIP de destino
            # standalone=True genera 'standalone="yes"', crítico para Word.
            xml_bytes = etree.tostring(
                target_tree,
                encoding='UTF-8',
                xml_declaration=True,
                standalone=True
            )
        except Exception as e:
            raise AstraIngestError(f"Error serializando el XML del documento: {e}")

        try:
            with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as target_zip:
                # Iterar sobre los archivos originales
                for item in self._zip_file.infolist():
                    if item.filename == PATH_WORD_DOCUMENT:
                        # Inyectar nuestro XML modificado
                        target_zip.writestr(item, xml_bytes)
                    else:
                        # Copiar el resto bit a bit
                        target_zip.writestr(item, self._zip_file.read(item.filename))
        except Exception as e:
            raise AstraIngestError(f"Error escribiendo el archivo DOCX de salida: {e}")

    def to_string(self, tree: etree._ElementTree) -> bytes:
        """Serializa un árbol etree a bytes OOXML."""
        return etree.tostring(
            tree,
            encoding='UTF-8',
            xml_declaration=True,
            standalone=True
        )

    def close(self):
        if self._zip_file:
            self._zip_file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()