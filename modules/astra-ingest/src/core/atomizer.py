import zipfile
import io
from lxml import etree

class OOXMLDissector:
    # Namespaces estándar de OOXML
    NAMESPACES = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    }

    def __init__(self, file_content: bytes):
        self.file_content = file_content
        self.zip_ref = zipfile.ZipFile(io.BytesIO(file_content))

    def extract_skeleton(self):
        """
        Parsea document.xml, limpia el contenido variable y retorna el XML string.
        """
        xml_content = self.zip_ref.read('word/document.xml')
        root = etree.fromstring(xml_content)

        # Iterar sobre nodos de texto (<w:t>) y reemplazarlos por tokens
        # Nota: En una implementación real, esto sería más sofisticado para detectar
        # variables vs texto estático. Aquí vaciamos para crear el esqueleto puro.
        count = 0
        for node in root.xpath('//w:t', namespaces=self.NAMESPACES):
            # Preservar espacio si es necesario, pero vaciar contenido
            # o poner un placeholder genérico
            node.text = f"{{BLK_{count}}}" 
            count += 1

        return etree.tostring(root, encoding='unicode', pretty_print=True)

    def extract_media_map(self):
        """
        Retorna un diccionario {nombre_archivo: bytes} de la carpeta media.
        """
        media_files = {}
        for file_info in self.zip_ref.infolist():
            if file_info.filename.startswith('word/media/'):
                media_files[file_info.filename] = self.zip_ref.read(file_info.filename)
        return media_files
