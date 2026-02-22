import os
import shutil
import logging
import boto3
from typing import Dict, Optional
from botocore.exceptions import ClientError
from src.config import get_settings

# Intentamos importar componentes de inferencia
# Si no están disponibles (modo mock/dev), evitamos el crash
try:
    from src.inference.model_loader import ModelLoader
    from src.inference.llm_engine import LLMEngine
    HAS_INFERENCE = True
except ImportError:
    HAS_INFERENCE = False

import asyncio
import gc
import torch

logger = logging.getLogger(__name__)

class IntelligenceReloader:
    """
    Gestiona el ciclo de vida de los activos de inteligencia (Adaptadores LoRA y Diccionarios).
    Implementa Hot-Swap seguro con bloqueo de escritura.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IntelligenceReloader, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.settings = get_settings()
        self.s3 = boto3.client(
            's3',
            endpoint_url=self.settings.S3_ENDPOINT_URL,
            aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY
        )
        
        # Lock de concurrencia para el swap
        self._swap_lock = asyncio.Lock()
        
        # Caché en memoria para diccionarios (Tenant -> Dict)
        self._entity_dictionaries: Dict[str, Dict[str, str]] = {}
        
        # Registro de versiones activas
        self._active_versions: Dict[str, str] = {}
        
        # Asegurar directorio de caché
        os.makedirs(self.settings.MODEL_CACHE_DIR, exist_ok=True)

    def update_dictionary(self, tenant_id: str, new_dictionary: Dict[str, str]):
        """
        Actualización atómica del diccionario de entidades en memoria.
        """
        logger.info(f"🔄 Hot-Reload: Actualizando diccionario para tenant {tenant_id}")
        self._entity_dictionaries[tenant_id] = new_dictionary

    def get_dictionary(self, tenant_id: str) -> Dict[str, str]:
        return self._entity_dictionaries.get(tenant_id, {})

    async def swap_adapter(self, tenant_id: str, s3_uri: str, version: str) -> bool:
        """
        Descarga un adaptador LoRA desde S3 y actualiza la referencia en memoria (VRAM).
        """
        if not HAS_INFERENCE:
            logger.warning("Inferencia no disponible. Saltando swap de adaptador.")
            return False

        logger.info(f"⬇️ Hot-Reload: Iniciando descarga de adaptador {version} para {tenant_id}")
        
        try:
            # 1. Preparar rutas
            bucket, key = self._parse_s3_uri(s3_uri)
            # Asumiendo que el key apunta a un .zip o carpeta
            # Para este ejemplo, suponemos que es una carpeta sync (descarga recursiva simulada)
            # En prod, descargaríamos un .zip y descomprimiríamos.
            
            target_dir = os.path.join(self.settings.MODEL_CACHE_DIR, tenant_id, version)
            
            # Ejecutar descarga I/O en thread separado para no bloquear el loop
            await asyncio.to_thread(self._download_artifact_safe, bucket, key, target_dir)
            
            # 2. Atomic Swap (Critical Section)
            logger.info(f"🔒 Adquiriendo lock para swap de modelo ({tenant_id})...")
            async with self._swap_lock:
                loader = ModelLoader()
                base_model = loader.get_model()
                
                if base_model is None:
                    logger.error("No hay modelo base cargado. Imposible aplicar adaptador.")
                    return False

                adapter_name = f"{tenant_id}_{version}"
                
                # Cargar el nuevo adaptador en VRAM
                logger.info(f"🧠 Cargando pesos PEFT: {adapter_name}")
                base_model.load_adapter(target_dir, adapter_name=adapter_name)
                
                # Activar el nuevo adaptador
                base_model.set_adapter(adapter_name)
                
                # Limpiar el adaptador viejo si existía
                old_version = self._active_versions.get(tenant_id)
                if old_version:
                    old_adapter_name = f"{tenant_id}_{old_version}"
                    if old_adapter_name != adapter_name:
                        logger.info(f"🧹 Eliminando adaptador obsoleto de VRAM: {old_adapter_name}")
                        # En PEFT, delete_adapter a veces requiere desactivarlo primero
                        if hasattr(base_model, "delete_adapter"):
                            base_model.delete_adapter(old_adapter_name)
                
                # Actualizar registro
                self._active_versions[tenant_id] = version
                
                # Forzar GC para evitar fragmentación
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            # 3. Limpieza de disco (Background)
            if old_version:
                await asyncio.to_thread(self._cleanup_old_versions, tenant_id, version)
            
            logger.info(f"🚀 Hot-Swap completado exitosamente. Tenant {tenant_id} usa {version}")
            return True

        except Exception as e:
            logger.error(f"❌ Fallo crítico en Hot-Reload: {e}", exc_info=True)
            return False

    def _download_artifact_safe(self, bucket: str, key: str, target_dir: str):
        """Descarga simulada/real del artefacto (Zip/Folder)."""
        # Si ya existe, asumimos integridad (o podríamos verificar hash)
        if os.path.exists(target_dir):
            return

        temp_dir = f"{target_dir}_tmp"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir)

        # Aquí iría la lógica recursiva de S3 o descarga de ZIP
        # Simulamos descarga de config.json y adapter_model.bin
        try:
            # self.s3.download_file(...)
            # Mock de creación de archivos para que PEFT cargue algo válido
            with open(os.path.join(temp_dir, "adapter_config.json"), "w") as f:
                f.write('{"lora_alpha": 16, "r": 16, "peft_type": "LORA", "task_type": "CAUSAL_LM", "target_modules": ["q_proj", "v_proj"]}')
            
            # Simulamos el binario (vacío o dummy para el mock)
            # En real, descargaríamos el archivo
            with open(os.path.join(temp_dir, "adapter_model.bin"), "wb") as f:
                f.write(b"mock_weights")

            # Move atómico
            shutil.move(temp_dir, target_dir)
        except Exception as e:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise e

    def _parse_s3_uri(self, uri: str):
        parts = uri.replace("s3://", "").split("/", 1)
        return parts[0], parts[1]

    def _cleanup_old_versions(self, tenant_id: str, keep_version: str):
        base_dir = os.path.join(self.settings.MODEL_CACHE_DIR, tenant_id)
        if not os.path.exists(base_dir):
            return
            
        for version_dir in os.listdir(base_dir):
            if version_dir != keep_version:
                full_path = os.path.join(base_dir, version_dir)
                try:
                    shutil.rmtree(full_path)
                    logger.debug(f"🧹 GC Disco: Eliminada versión antigua {version_dir}")
                except Exception as e:
                    logger.warning(f"Error limpiando caché antigua: {e}")