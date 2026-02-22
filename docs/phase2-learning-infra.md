# Documentación Técnica: Infraestructura de Aprendizaje (Fase 2)

## 1. Despacho Serverless [Fase2-T05]

**Objetivo:** Permitir el entrenamiento elástico de modelos en la nube utilizando RunPod Serverless, evitando la necesidad de GPUs locales o clusters K8s permanentes.

### Componente: `RunPodClient`

Ubicación: `services/astra-learn/src/infrastructure/clients/runpod_client.py`

#### Características Técnicas:

- **Asincronía**: Implementado sobre `httpx.AsyncClient` para no bloquear el scheduler de entrenamiento.
- **Protocolo RunPod v2**: Utiliza los endpoints `/run` (async job submission) y `/status` (polling).
- **Manejo de Errores**: Enmascara errores de red y HTTP bajo la excepción de dominio `RunPodError`.
- **Resiliencia**: Implementa un mecanismo de reintentos con backoff exponencial para errores transitorios (500, 502, 503, etc.).
- **Seguridad**: Autenticación vía Bearer Token inyectado desde variables de entorno.

### Configuración requerida (.env):

```bash
RUNPOD_API_KEY=your_api_key_here
RUNPOD_ENDPOINT_ID=your_endpoint_id_here
```

### Flujo de Uso:

```python
client = RunPodClient()
job_id = await client.submit_job({"dataset_url": "s3://...", "epochs": 3})
status = await client.get_status(job_id)
if status["status"] == "COMPLETED":
    print(status["output"])
```

### Suite de Pruebas:

Ubicación: `services/astra-learn/tests/infrastructure/test_runpod_client.py`.
Utiliza `respx` para simular la API de RunPod, garantizando que los tests sean rápidos, deterministas y no requieran conexión real.

---

## 2. Worker de Entrenamiento GPU [Fase2-T06]

Se ha dockerizado el entorno de entrenamiento para su ejecución en RunPod.

### Dockerfile & Entorno:

Ubicación: `services/astra-learn/worker/Dockerfile`.

- **Base**: `unslothai/unsloth` (optimizado para Fine-Tuning con 2x velocidad y -70% VRAM).
- **Dependencias**: `runpod`, `requests`, `boto3`.

### Handler de Ejecución:

Ubicación: `services/astra-learn/runpod_training_handler.py`.

- **Orquestación Local**: Se encarga de descargar los datasets desde S3, invocar el script `train.py`, comprimir los adaptadores resultantes y subirlos de vuelta al bucket de salida.
- **Protocolo de Comunicación**: Diseñado para el modo Serverless de RunPod, devolviendo estados y errores de forma estructurada.

### Verificación local:

```bash
docker build -t astra/trainer:v1 -f services/astra-learn/worker/Dockerfile .
docker run --rm astra/trainer:v1 python -c "import unsloth; print('Worker Ready')"
```

---

## 3. Orquestación Híbrida [Fase2-T07]

El `JobScheduler` ha sido actualizado para actuar como un bus de despacho inteligente entre la infraestructura On-Premise y la Nube.

### Estrategias de Ejecución:

- **K8S (Kubernetes Local)**: Utilizado por defecto. Monta volúmenes de datos directamente en el Pod de entrenamiento. Ideal para datos altamente sensibles o cuando hay GPUs locales disponibles.
- **RUNPOD (Cloud Serverless)**: Utilizado para "Cloud Bursting". Convierte los datasets locales en URLs presignadas de S3 (con TTL de 1 hora) para que el worker externo pueda consumirlos sin acceso al cluster privado.

### Configuración del Backend Selector:

Se controla mediante la variable `TRAINING_BACKEND` en el servicio `astra-learn`.

### Generación Dinámica de Artefactos:

Cuando se selecciona RunPod, el scheduler genera automáticamente:

1.  **Input URL**: Pre-signed GET para el archivo `.jsonl`.
2.  **Output URL**: Pre-signed PUT para que el worker suba el `adapter.zip` final.
3.  **Payload de Hiperparámetros**: Inyección de configuración del modelo base y límites de secuencia.
