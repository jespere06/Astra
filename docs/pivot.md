# Directiva Técnica Maestra (DTM): ASTRA Batch Pivot

**Objetivo:** Transicionar la arquitectura de **ASTRA** hacia un modelo de **Procesamiento por Lotes de Alto Rendimiento (High-Throughput Batch)**, priorizando la eficiencia de costos mediante el uso de infraestructura híbrida (VPS Contabo + GPU Serverless On-Demand).

**Inputs:**

- Archivos de audio de larga duración (3h - 8h) provenientes de S3.
- Infraestructura base desplegada en Contabo VPS 20 (Orchestrator, DB, Qdrant).
- Modelos de IA: Whisper Large-v3 Turbo y NVIDIA Parakeet-TDT.

**Outputs Esperados:**

- Módulo `ASTRA-ORCHESTRATOR` refactorizado para soportar flujos asíncronos de larga duración (Job Queues).
- Nuevo servicio `ASTRA-WORKER` (Serverless Container) capaz de procesar audio masivo en <15 min.
- Capa de abstracción `TranscriptionEngine` que soporte múltiples backends (Whisper/Parakeet).
- Despliegue de infraestructura en RunPod/Modal para workers efímeros.

**Archivos a Tocar:**

- `services/astra-orchestrator`: Lógica de encolamiento y webhooks.
- `services/astra-core`: Refactorización hacia `astra-worker` (nuevo repo/módulo).
- `infra/`: Terraform/Pulumi para RunPod Templates.

**Contratos Clave:**

- **Job Payload:** `{ session_id, audio_url, model_config: { provider: "parakeet" } }`
- **Worker Callback:** `POST /webhook/job/{id} { status, transcript_url, metrics }`

**DoD:** Un archivo de 7 horas se procesa end-to-end en <10 minutos costando <$0.05 USD. El sistema escala a cero cuando no hay jobs.

**Estimación:** 2 Semanas (Sprint Táctico).
**Riesgos:** Latencia de arranque en frío (Cold Start) de workers serverless y manejo de archivos grandes en red.

---

# Documento de Arquitectura: ASTRA Batch Pivot

## Contexto

El negocio ha validado que el caso de uso principal implica la carga de archivos de audio de larga duración (sesiones completas de ~7 horas) al final del día, eliminando la necesidad de procesamiento en tiempo real estricto. Esto permite optimizar costos radicalmente moviendo la inferencia pesada a instancias GPU efímeras (Serverless) y manteniendo el control plane en un VPS económico.

## Plan de Batalla

La arquitectura migra de un modelo "Always-on Service" a un modelo "Controller-Worker".

1.  **Controller (Contabo):** Gestiona la API, estado, bases de datos y la cola de trabajos.
2.  **Worker (RunPod/Modal):** Contenedores que nacen, procesan y mueren.

## Análisis de Impacto

- **Latencia:** Aumenta el tiempo de inicio (Cold Start ~10-30s), irrelevante para jobs batch.
- **Complejidad:** Se introduce gestión de colas asíncronas y webhooks.
- **Costos:** Reducción estimada del 90% en costos de cómputo de IA.

---

## Roadmap Secuencial

### [Fase1-T01] Abstracción del Motor de Transcripción (Unified Interface)

- **Título:** Implementación del `TranscriptionEngine` Agnóstico
- **Descripción:** Refactorizar el núcleo de transcripción para soportar múltiples backends bajo una interfaz común. Esto permite cambiar entre Whisper Turbo, Parakeet o APIs externas mediante configuración.
- **Dónde:** `services/astra-core/src/engine/transcription/`
- **Owner sugerido:** Senior Python Dev
- **Prioridad:** P0
- **Estimación:** 8 horas
- **Dependencias:** Ninguna
- **Entregables:** Interfaz `ITranscriber` y adaptadores `WhisperAdapter`, `ParakeetAdapter`.
- **Criterios de Éxito (DoD):** Tests unitarios pasando para ambos motores con el mismo input de audio.
- **Tests requeridos:** Unit tests con mocks de modelos. Integration test con audios cortos.
- **Riesgos (Bajo):** Incompatibilidad de dependencias (CUDA versiones) entre librerías. Mitigación: Docker images separadas si es necesario.

**Dev Prompt:**
Diseña e implementa una interfaz abstracta `ITranscriber` en Python que defina el método `transcribe(audio_path: str, config: Dict) -> TranscriptResult`.
Implementa dos clases concretas:

1. `WhisperTranscriber`: Usando `faster-whisper` con soporte para `large-v3-turbo`.
2. `ParakeetTranscriber`: Usando `NVIDIA NeMo` para `parakeet-tdt-0.6b`.
   Asegura que el output `TranscriptResult` estandarice los segmentos, timestamps y confianza, independientemente del motor usado. Maneja la carga de modelos (Lazy Loading) para no saturar memoria en import.

---

### [Fase1-T02] Diseño del Contenedor del Worker (GPU Optimized)

- **Título:** Dockerización de ASTRA-WORKER para RunPod
- **Descripción:** Crear una imagen Docker optimizada para ejecución en Serverless GPU. Debe incluir los drivers CUDA, las librerías de `faster-whisper` y `NeMo`, y un servidor ligero (ej. FastAPI o script worker) que acepte un payload de trabajo, procese y suba el resultado.
- **Dónde:** `services/astra-worker/Dockerfile`, `services/astra-worker/src/`
- **Owner sugerido:** DevOps / ML Engineer
- **Prioridad:** P0
- **Estimación:** 12 horas
- **Dependencias:** [Fase1-T01]
- **Entregables:** Imagen Docker publicada en ECR/DockerHub compatible con RunPod.
- **Criterios de Éxito (DoD):** El contenedor arranca en <10s y procesa un audio de prueba usando GPU.
- **Tests requeridos:** Build y Run en entorno local con GPU o instancia de prueba.
- **Riesgos (Medio):** Tamaño de la imagen (>10GB) afectando tiempos de cold start. Mitigación: Multi-stage builds, cache de modelos en volumen de red.

**Dev Prompt:**
Crea un `Dockerfile` optimizado para `ASTRA-WORKER`. Base image: `nvidia/cuda:12.1.0-runtime-ubuntu22.04`.
Instala Python 3.10, `faster-whisper`, `nemo_toolkit[asr]`.
Implementa un script `main.py` que:

1. Lea variables de entorno para configuración.
2. Descargue el audio de una URL S3 presignada.
3. Ejecute la transcripción usando la abstracción creada en T01.
4. Suba el JSON resultante a S3.
5. Notifique a un Webhook de finalización.
   Optimiza el tamaño de la imagen eliminando cachés de pip y apt.

---

### [Fase1-T03] Orquestador de Jobs Asíncronos (Queue Management)

- **Título:** Sistema de Encolamiento de Trabajos en Orchestrator
- **Descripción:** Modificar `ASTRA-ORCHESTRATOR` para manejar flujos asíncronos. Implementar una cola (Redis/BullMQ o tabla Postgres) para gestionar los estados de los trabajos (`QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`). Implementar la lógica para disparar workers en RunPod vía API.
- **Dónde:** `services/astra-orchestrator/src/jobs/`
- **Owner sugerido:** Backend Lead
- **Prioridad:** P0
- **Estimación:** 16 horas
- **Dependencias:** Ninguna
- **Entregables:** Endpoints de creación y monitoreo de Jobs. Integración con API de RunPod.
- **Criterios de Éxito (DoD):** Un request POST crea un job, dispara un worker remoto y actualiza el estado.
- **Tests requeridos:** Integration tests mockeando la API de RunPod.
- **Riesgos (Bajo):** Fallos en la API del proveedor serverless. Mitigación: Retries y Dead Letter Queue.

**Dev Prompt:**
Implementa el módulo de gestión de Jobs en `ASTRA-ORCHESTRATOR`.

1. Crea modelo `Job` en DB: `id`, `status`, `input_url`, `output_url`, `created_at`, `finished_at`.
2. Implementa `JobManager` que:
   - Recibe petición de transcripción.
   - Sube audio a S3 temporal.
   - Llama a la API de RunPod (Serverless Endpoint) pasando la URL del audio y el Webhook de callback.
   - Actualiza estado a `PROCESSING`.
3. Implementa endpoint `POST /webhooks/runpod` para recibir la notificación de éxito/fallo y actualizar el Job.

---

### [Fase1-T04] Adaptador de Almacenamiento S3 (Cloudflare R2)

- **Título:** Migración de Capa de Almacenamiento a Compatible S3
- **Descripción:** Configurar y validar la librería de almacenamiento para usar Cloudflare R2 como backend. Asegurar que la generación de URLs presignadas funcione correctamente para que los workers externos puedan descargar los audios.
- **Dónde:** `libs/shared-kernel/storage/`, `infra/`
- **Owner sugerido:** DevOps
- **Prioridad:** P1
- **Estimación:** 4 horas
- **Dependencias:** Ninguna
- **Entregables:** Configuración probada con R2.
- **Criterios de Éxito (DoD):** Subida y descarga exitosa de archivos >1GB desde entorno externo.
- **Tests requeridos:** Test de conectividad y permisos de buckets.
- **Riesgos (Bajo):** Diferencias sutiles en API S3 de Cloudflare. Mitigación: Usar librería estándar `boto3`.

**Dev Prompt:**
Configura el cliente `boto3` en el proyecto para conectar con Cloudflare R2.
Define las variables de entorno necesarias (`R2_ACCOUNT_ID`, `R2_ACCESS_KEY`, `R2_SECRET_KEY`).
Crea una clase utilitaria `StorageService` que abstraiga:

- `upload_file(path, bucket, key)`
- `generate_presigned_url(bucket, key, expiration)`
  Verifica que las URLs generadas sean accesibles públicamente (o con token) desde fuera de la red local (para los workers).

---

### [Fase1-T05] Configuración de VPS Contabo (Production Environment)

- **Título:** Provisionamiento y Hardening de VPS Contabo
- **Descripción:** Configurar el servidor Cloud VPS 20. Instalación de Docker, Docker Compose, configuración de Firewall (UFW), Fail2Ban, y despliegue de los servicios base (Postgres, Redis, Qdrant).
- **Dónde:** Infraestructura (Servidor Remoto)
- **Owner sugerido:** SysAdmin / DevOps
- **Prioridad:** P0
- **Estimación:** 6 horas
- **Dependencias:** Compra del servidor.
- **Entregables:** Servidor accesible vía SSH seguro, servicios base corriendo.
- **Criterios de Éxito (DoD):** Todos los contenedores de infraestructura en estado `Running`. Puertos de DB cerrados al exterior.
- **Tests requeridos:** N/A
- **Riesgos (Medio):** Seguridad del servidor expuesto. Mitigación: SSH Key-only auth, firewall estricto.

**Dev Prompt:**
Ejecuta el setup inicial del VPS Contabo (Ubuntu 22.04 LTS):

1. Actualizar sistema y crear usuario deploy con privilegios sudo.
2. Deshabilitar login root por SSH y password auth.
3. Instalar Docker y Docker Compose plugin.
4. Configurar UFW: permitir solo 22 (SSH), 80/443 (HTTP/S).
5. Desplegar `docker-compose.yml` con:
   - PostgreSQL (Alpine)
   - Redis (Alpine)
   - Qdrant (Configurado con `mmap` para ahorro de RAM).
   - Nginx Proxy Manager (o Traefik) para gestión de SSL.

---

### [Fase1-T06] Pipeline de Ingesta Masiva (Cold Start Data)

- **Título:** Script de Procesamiento Batch para Documentos Históricos
- **Descripción:** Crear un script que tome los 50 documentos DOCX históricos, extraiga el texto, genere embeddings y pueble la base de datos Qdrant y el diccionario de entidades. Este proceso se ejecutará en el VPS para inicializar la "memoria" del sistema.
- **Dónde:** `services/astra-ingest/scripts/`
- **Owner sugerido:** Backend Dev
- **Prioridad:** P1
- **Estimación:** 8 horas
- **Dependencias:** [Fase1-T05] (Servicios corriendo)
- **Entregables:** Script `bootstrap_tenant.py` y base de datos poblada.
- **Criterios de Éxito (DoD):** Qdrant contiene vectores de las 50 actas. Diccionario de entidades contiene nombres de concejales y barrios.
- **Tests requeridos:** Ejecución local con un subconjunto de docs.
- **Riesgos (Bajo):** Formatos de DOCX muy inconsistentes.

**Dev Prompt:**
Desarrolla el script `bootstrap_tenant.py` en `astra-ingest`.
Funcionalidad:

1. Recorre una carpeta de archivos `.docx`.
2. Usa `DocxAtomizer` (existente) para extraer texto y estructura.
3. Usa `TextEmbedder` (existente) para generar vectores.
4. Extrae entidades (Nombres, Cargos) usando reglas heurísticas simples (ej. texto en mayúscula sostenida cerca de "Concejal").
5. Guarda vectores en Qdrant y entidades en Postgres (`tenant_config`).
   El script debe ser idempotente (si se corre dos veces, no duplica data).

---

### [Fase1-T07] API de Streaming para Transcripción (Fallback)

- **Título:** Mantener Endpoints de Streaming (Legacy Support)
- **Descripción:** Asegurar que la arquitectura actual de `ASTRA-CORE` que soporta streaming (WebSockets/HTTP Chunked) se mantenga funcional pero marcada como "Legacy/Real-time". Esto permite atender casos de uso futuros de transcripción en vivo sin reescribir todo, aunque por defecto se use el Batch Worker.
- **Dónde:** `services/astra-core/src/api/`
- **Owner sugerido:** Backend Dev
- **Prioridad:** P2
- **Estimación:** 4 horas
- **Dependencias:** Ninguna
- **Entregables:** API Dual (Batch por defecto, Stream opcional).
- **Criterios de Éxito (DoD):** El sistema puede recibir un stream de audio si se configura el flag `mode=realtime`.
- **Tests requeridos:** Test manual de endpoint de streaming.

**Dev Prompt:**
Refactoriza el controlador de `ASTRA-CORE` para soportar dos modos de operación:

1. **Modo Batch (Default):** Recibe un ID de Job, descarga audio de S3, procesa completo, sube resultado.
2. **Modo Stream (Legacy):** Mantiene la lógica actual de recibir chunks de audio y procesar incrementalmente.
   Asegura que el `TranscriptionEngine` (T01) sea compatible con ambos modos (procesar archivo completo vs procesar buffer en memoria).

---

### Checklist de Handoff a Desarrollo

1.  [ ] Repositorio configurado con la nueva estructura de `astra-worker`.
2.  [ ] Credenciales de Cloudflare R2 y RunPod obtenidas y configuradas en `.env`.
3.  [ ] Acceso SSH al VPS de Contabo verificado.
4.  [ ] Definición clara de la interfaz `ITranscriber`.
5.  [ ] Set de datos de prueba (1 audio largo, 50 docs históricos) disponible en S3/Local.
