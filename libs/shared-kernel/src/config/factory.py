import logging
from typing import Dict, Type, Any, Optional
from .settings import global_settings, AstraGlobalSettings
from .enums import TranscriptionProvider, StorageBackend
from ..storage.interface import IStorageProvider
from ..storage.s3_adapter import S3StorageAdapter
from ..storage.fs_adapter import FileSystemStorageAdapter

logger = logging.getLogger(__name__)

class DependencyFactory:
    """
    Factory centralizado para la inyección de dependencias de infraestructura.
    Permite desacoplar la lógica de negocio de las implementaciones concretas
    basándose en la configuración del entorno (CLOUD/ONPREM).
    """
    
    _transcriber_registry: Dict[str, Type] = {}
    _storage_registry: Dict[str, Type] = {
        StorageBackend.S3: S3StorageAdapter,
        StorageBackend.FILESYSTEM: FileSystemStorageAdapter
    }
    
    def __init__(self, settings: AstraGlobalSettings = global_settings):
        self.settings = settings

    @classmethod
    def register_transcriber(cls, provider_key: str, implementation_class: Type):
        """
        Permite a los microservicios registrar sus implementaciones de ITranscriber.
        Esto evita dependencias circulares entre shared-kernel y los servicios.
        """
        cls._transcriber_registry[provider_key] = implementation_class
        logger.info(f"Registrado proveedor de transcripción: {provider_key} -> {implementation_class.__name__}")

    def get_transcriber(self, **kwargs) -> Any:
        """
        Retorna la instancia del transcriptor configurado en TRANSCRIPTION_PROVIDER.
        """
        provider_key = self.settings.TRANSCRIPTION_PROVIDER
        
        # Verificar si está registrado
        if provider_key not in self._transcriber_registry:
            # Intento de fallback o error descriptivo
            registered_keys = list(self._transcriber_registry.keys())
            raise ValueError(
                f"El proveedor de transcripción '{provider_key}' no ha sido registrado en el Factory. "
                f"Asegúrese de importar y registrar la clase al inicio de la aplicación. "
                f"Disponibles: {registered_keys}"
            )
        
        implementation_class = self._transcriber_registry[provider_key]
        
        logger.info(f"Factory: Instanciando Transcriber '{provider_key}' ({implementation_class.__name__})")
        # Asumimos que los transcriptores aceptan config en el constructor o kwargs
        return implementation_class(config=kwargs)

    def get_storage(self) -> IStorageProvider:
        """
        Retorna la instancia del almacenamiento configurado en STORAGE_TYPE.
        """
        backend_key = self.settings.STORAGE_TYPE
        
        if backend_key not in self._storage_registry:
            raise ValueError(f"Backend de almacenamiento no soportado: {backend_key}")
            
        implementation_class = self._storage_registry[backend_key]
        
        logger.info(f"Factory: Instanciando Storage '{backend_key}' ({implementation_class.__name__})")
        
        if backend_key == StorageBackend.FILESYSTEM:
            return implementation_class(root_path=self.settings.STORAGE_LOCAL_ROOT)
        else:
            # S3 Adapter usa sus propias settings internas o env vars
            return implementation_class()

# Instancia global por conveniencia
dependency_factory = DependencyFactory()
