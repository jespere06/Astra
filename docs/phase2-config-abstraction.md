# Documentación Técnica: Abstracción de Configuración y Factory (Fase 2)

## 1. Abstracción de Entorno [Fase2-T08]

**Objetivo:** Permitir que ASTRA funcione en modo Híbrido (Cloud) o Aislado (On-Premise) sin cambios en el código, facilitando despliegues en clientes como la Fiscalía.

### Componentes en `shared-kernel`:

#### `AstraGlobalSettings`

Ubicación: `libs/shared-kernel/src/config/settings.py`

- Utiliza **Pydantic v2** para cargar variables de entorno.
- **Validación Cruzada**: Impide configuraciones incoherentes (ej. usar OpenAI en modo On-Premise).
- **Perfiles**: `CLOUD` (Default) y `ONPREM`.

#### `DependencyFactory`

Ubicación: `libs/shared-kernel/src/config/factory.py`

- Utiliza el **Patrón Registry** para desacoplar implementaciones concretas.
- **Storage**: Resuelve automáticamente entre `S3StorageAdapter` y `FileSystemStorageAdapter`.
- **Transcripción**: Permite el registro dinámico de proveedores desde los microservicios, evitando dependencias circulares.

#### `FileSystemStorageAdapter`

Ubicación: `libs/shared-kernel/src/storage/fs_adapter.py`

- Implementa la interfaz `IStorageProvider`.
- Permite operaciones de almacenamiento persistente utilizando el disco local (volúmenes montados), esencial para entornos sin S3.

### Cómo usar en un Microservicio:

```python
from shared_kernel.config.factory import dependency_factory

# Obtener almacenamiento (S3 o FS según config)
storage = dependency_factory.get_storage()

# Registrar un transcriptor personalizado (ej. en astra-core)
dependency_factory.register_transcriber("deepgram", DeepgramTranscriber)

# Obtener transcriptor configurado
transcriber = dependency_factory.get_transcriber()
```

### Suite de Pruebas:

Ubicación: `libs/shared-kernel/tests/config/test_factory.py`.
Verifica la resolución de dependencias, el registro dinámico y las restricciones de seguridad del perfil `ONPREM`.
