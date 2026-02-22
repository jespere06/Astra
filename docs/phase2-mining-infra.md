# Documentación Técnica: Infraestructura de Minería (Fase 2)

## 1. Directiva Técnica Maestra (DTM) - [Fase2-T01]

**Objetivo:** Habilitar el entorno de ejecución de `astra-ingest` para soportar la descarga y transcodificación de audio desde fuentes externas (YouTube).

**Requisitos:**

- Repositorio: `modules/astra-ingest/Dockerfile`.
- Herramientas: `yt-dlp` (vía pip, latest) y `ffmpeg` (via apt-get, stable).

**DoD (Definition of Done):**

1. La imagen se construye sin errores.
2. `yt-dlp` instalado vía `pip` para evitar bloqueos de API.
3. `ffmpeg` instalado como dependencia de sistema.
4. El contenedor corre como usuario `appuser` (no-root).

---

## 2. Análisis de Arquitectura

### Meta

Dotar al microservicio **ASTRA-INGEST** de las capacidades necesarias para interactuar con plataformas externas y normalizar contenido auditivo.

### Suposiciones

- Imagen base `python:3.10-slim` para balancear tamaño y compatibilidad.
- Conectividad a internet permitida para dominios de video.
- Inmutabilidad de la imagen (actualizaciones vía rebuild).

### Impactos

- **Build Time:** Incremento por instalación de `ffmpeg`.
- **Storage:** Uso de disco efímero durante descargas.
- **Seguridad:** Usuario no privilegiado para ejecución de subprocesos.

---

## 3. Implementación [Fase2-T01]

Se ha actualizado el `Dockerfile` de `modules/astra-ingest` integrando las herramientas CLI requeridas.

### Verificación manual sugerida:

```bash
docker build -t astra-ingest:mining .
docker run --rm astra-ingest:mining yt-dlp --version
docker run --rm astra-ingest:mining ffmpeg -version
```

---

## 4. Implementación [Fase2-T02]

Se ha desarrollado el servicio `MediaDownloader` en `src/mining/downloader.py`.

### Capacidades:

- **Descarga Inteligente**: Invocación de `yt-dlp` en modo audio-only.
- **Normalización On-the-fly**: Configuración de `ffmpeg` para forzar formato WAV PCM, 16kHz, Mono (requisito para modelos acústicos).
- **Persistencia en S3**: Almacenamiento automático en el bucket `astra-raw` bajo la estructura `/mining/{tenant_id}/{uuid}.wav`.
- **Gestión de Temporales**: Limpieza agresiva de archivos en `/tmp` tras procesamiento exitoso o fallido.

### Tests:

Ubicación: `tests/mining/test_downloader.py`. Soporta ejecución con Mocks para CI y pruebas reales para integración local.

---

## 5. Orquestación E2E [Fase2-T04]

Se ha implementado el `MiningOrchestrator` para cerrar el ciclo de vida del dato.

### Flujo Integrado:

1.  **Ingesta CSV**: Lee video URLs y mappings de DOCX.
2.  **MediaDownloader**: Ejecuta la descarga y normalización (WAV).
3.  **CoreClient**: Solicita la transcripción a `astra-core` indicando el proveedor (ej. `deepgram`).
4.  **SemanticExtractor**: Procesa el acta DOCX local para extraer fragmentos.
5.  **Alignment & Build**: Cruza la transcripción con el acta para generar el `train.jsonl`.

### CLI:

Script: `src/scripts/run_mining.py`. Permite disparar el pipeline completo con control de tenants y modo dry-run.
