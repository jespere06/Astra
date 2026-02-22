import os
import zipfile
import shutil
import uuid
import logging
from lxml import etree
from src.config import settings
from src.infrastructure.s3_client import S3Client
from src.core.constants import OOXML_NAMESPACES, PATH_DOCUMENT
from src.core.table_engine import DynamicTableEngine
from src.core.xml_sanitizer import XmlSanitizer
from src.core.l10n import Localizer

logger = logging.getLogger(__name__)

class DocumentComposer:
    def __init__(self, session_id: str, tenant_id: str, timezone: str):
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.work_dir = os.path.join(settings.TEMP_DIR, session_id)
        self.s3 = S3Client()
        self.table_engine = DynamicTableEngine()
        self.localizer = Localizer(timezone)
        
        # Limpieza inicial
        if os.path.exists(self.work_dir):
            shutil.rmtree(self.work_dir)
        os.makedirs(self.work_dir)

    def load_skeleton(self, skeleton_id: str, version_id: str = None):
        """[Fase3-T01] Descarga y descomprime el Skeleton."""
        local_zip = os.path.join(self.work_dir, "skeleton.docx")
        
        # Descargar de S3 con Version ID
        self.s3.download_file(
            bucket=settings.S3_BUCKET_SKELETONS,
            key=f"{self.tenant_id}/{skeleton_id}.docx",
            download_path=local_zip,
            version_id=version_id
        )

        # Descomprimir
        with zipfile.ZipFile(local_zip, 'r') as zip_ref:
            zip_ref.extractall(self.work_dir)
        
        os.remove(local_zip) # Limpiar zip original

    def process_blocks(self, blocks: list):
        """Itera los bloques e inyecta contenido."""
        doc_path = os.path.join(self.work_dir, PATH_DOCUMENT)
        tree = etree.parse(doc_path)
        root = tree.getroot()
        
        # Namespace map para búsquedas
        ns = OOXML_NAMESPACES

        for block in blocks:
            if block['type'] == 'DYNAMIC_TABLE':
                # Buscar tabla por ID
                table_id = block.get('target_placeholder') # Debe coincidir con astra:tblId
                # XPath para encontrar la tabla con el atributo custom
                xpath = f".//w:tbl[@astra:tblId='{table_id}']"
                tables = root.xpath(xpath, namespaces=ns)
                
                if tables:
                    self.table_engine.process_table(tables[0], block['data'])
                else:
                    logger.warning(f"Tabla con ID {table_id} no encontrada en Skeleton.")

            elif block['type'] == 'TEMPLATE':
                 # Lógica simple de reemplazo de texto en placeholders
                 # (Implementación simplificada para este ejemplo)
                 pass
                 
        # Guardar cambios en XML
        tree.write(doc_path, encoding='UTF-8', xml_declaration=True, standalone=True)

    def finalize(self) -> str:
        """Re-empaqueta el DOCX y lo sube."""
        output_filename = f"{self.session_id}_final.docx"
        output_path = os.path.join(settings.TEMP_DIR, output_filename)
        
        # Zip del directorio de trabajo
        shutil.make_archive(output_path.replace('.docx', ''), 'zip', self.work_dir)
        shutil.move(output_path.replace('.docx', '.zip'), output_path)
        
        # Subir a S3
        s3_key = f"{self.tenant_id}/outputs/{output_filename}"
        self.s3.upload_file(output_path, settings.S3_BUCKET_OUTPUT, s3_key)
        
        # Limpieza
        shutil.rmtree(self.work_dir)
        os.remove(output_path)
        
        return s3_key
