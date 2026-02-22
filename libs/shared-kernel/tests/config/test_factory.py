import os
import pytest
from unittest.mock import MagicMock
from src.config.factory import DependencyFactory
from src.config.settings import AstraGlobalSettings
from src.config.enums import TranscriptionProvider, StorageBackend, DeploymentProfile
from src.storage.fs_adapter import FileSystemStorageAdapter
from src.storage.s3_adapter import S3StorageAdapter

# Mocks de Clases de Servicio (simulando astra-core)
class MockWhisperTranscriber:
    def __init__(self, config=None):
        self.name = "Whisper"

class MockDeepgramTranscriber:
    def __init__(self, config=None):
        self.name = "Deepgram"

class TestDependencyFactory:

    def setup_method(self):
        # Limpiar registro antes de cada test
        DependencyFactory._transcriber_registry = {}

    def test_storage_resolution_s3(self):
        # Configurar entorno para S3
        settings = AstraGlobalSettings(STORAGE_TYPE="s3")
        factory = DependencyFactory(settings)
        
        storage = factory.get_storage()
        assert isinstance(storage, S3StorageAdapter)

    def test_storage_resolution_filesystem(self):
        # Configurar entorno para Filesystem
        settings = AstraGlobalSettings(STORAGE_TYPE="filesystem", STORAGE_LOCAL_ROOT="/tmp/astra")
        factory = DependencyFactory(settings)
        
        storage = factory.get_storage()
        assert isinstance(storage, FileSystemStorageAdapter)
        assert storage.root_path == "/tmp/astra"

    def test_transcriber_registration_and_retrieval(self):
        # 1. Registrar proveedores
        DependencyFactory.register_transcriber(TranscriptionProvider.WHISPER_LOCAL, MockWhisperTranscriber)
        DependencyFactory.register_transcriber(TranscriptionProvider.DEEPGRAM, MockDeepgramTranscriber)

        # 2. Configurar para usar Whisper
        settings = AstraGlobalSettings(TRANSCRIPTION_PROVIDER="whisper_local")
        factory = DependencyFactory(settings)

        # 3. Obtener instancia
        transcriber = factory.get_transcriber()
        assert isinstance(transcriber, MockWhisperTranscriber)
        assert transcriber.name == "Whisper"

        # 4. Cambiar configuración a Deepgram (simulado cambiando settings del factory)
        factory.settings = AstraGlobalSettings(
            TRANSCRIPTION_PROVIDER="deepgram", 
            DEEPGRAM_API_KEY="dummy_key"
        )
        transcriber_dg = factory.get_transcriber()
        assert isinstance(transcriber_dg, MockDeepgramTranscriber)

    def test_validation_on_premise_restrictions(self):
        """Verifica que no se pueda configurar Deepgram en modo ONPREM"""
        with pytest.raises(ValueError) as excinfo:
            AstraGlobalSettings(
                ASTRA_PROFILE=DeploymentProfile.ONPREM,
                TRANSCRIPTION_PROVIDER=TranscriptionProvider.DEEPGRAM
            )
        assert "No se puede usar deepgram en modo ONPREM" in str(excinfo.value)

    def test_missing_provider_registration(self):
        settings = AstraGlobalSettings(TRANSCRIPTION_PROVIDER="whisper_local")
        factory = DependencyFactory(settings)
        
        # No registramos nada
        with pytest.raises(ValueError) as excinfo:
            factory.get_transcriber()
        
        assert "no ha sido registrado" in str(excinfo.value)

    def test_deepgram_missing_key(self):
        """Verifica que falle si falta la API Key de Deepgram en modo Cloud"""
        with pytest.raises(ValueError) as excinfo:
            AstraGlobalSettings(
                ASTRA_PROFILE=DeploymentProfile.CLOUD,
                TRANSCRIPTION_PROVIDER=TranscriptionProvider.DEEPGRAM
                # Sin DEEPGRAM_API_KEY
            )
        assert "DEEPGRAM_API_KEY es requerida" in str(excinfo.value)
