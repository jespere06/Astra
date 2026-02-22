# Roadmap Técnico: Fase 3 — Automatización del Bucle de Inteligencia (The Intelligence Loop)

## 1. Meta / Objetivo de la Fase

Capitalizar la corrección algorítmica de la alineación para construir el **Pipeline de Entrenamiento Continuo (CT/CI)**. El objetivo es automatizar el flujo: _Minería de Datos (Ingest) → Curaduría de Dataset → Fine-Tuning Remoto (RunPod) → Evaluación Automática → Despliegue en Caliente (Core)_. Transformaremos los datos alineados correctamente en adaptadores LoRA que mejoren la precisión del sistema sesión tras sesión.

## 2. Suposiciones Iniciales

1.  **Fixes Aplicados:** Se asume que los parches lógicos en `aligner.py`, `extractor.py` y `deepgram_adapter.py` (segmentación) ya están aplicados en `main` y estabilizados.
2.  **Infraestructura Híbrida:** `ASTRA-CORE` corre localmente (o en VPS) pero el entrenamiento pesado se delega a **RunPod Serverless** (GPU A100/L40S).
3.  **Modelo Base:** Se estandariza el uso de **Llama-3-8B-Instruct** (Unsloth cuantizado a 4-bit) como base para el Fine-Tuning.
4.  **Persistencia:** MinIO/S3 está operativo para almacenar datasets intermedios (`.jsonl`) y artefactos de modelos (`adapter.zip`).

## 3. Análisis de Impacto

- **ASTRA-INGEST:** Se vuelve crítico para la calidad del modelo. Un fallo en el alineador ahora envenena el modelo (Garbage In, Garbage Out).
- **ASTRA-LEARN:** Pasa de ser un concepto a un orquestador activo de trabajos remotos.
- **ASTRA-CORE:** Debe implementar mecanismos de _Hot-Swap_ para recargar adaptadores LoRA sin tiempo de inactividad.
- **Costos:** Se introduce un costo variable por minuto de entrenamiento en RunPod (controlado por time-limits).

---

## 4. Roadmap Secuencial (Core)

### [Fase3-T01] Hardening de Motores de Minería (Ingest Refactor) {completado}

- **Título:** Integración y Parametrización de la Lógica de Alineación (V2)
- **Descripción:** Refactorizar los cambios rápidos ("hotfixes") aplicados en `aligner.py` y `extractor.py` para convertirlos en una implementación robusta y configurable. Exponer los parámetros críticos (`max_lookahead`, `word_count_threshold`, `length_penalty_factor`) en `src/config.py` o variables de entorno para ajuste fino sin redespliegue. Implementar Tests de Regresión para asegurar que no reaparezcan los "bloques gigantes".
- **Dónde:** `modules/astra-ingest/src/mining/aligner.py`, `extractor.py`, `config.py`.
- **Owner sugerido:** Backend Lead (Python).
- **Prioridad:** **P0**
- **Estimación:** 6 horas.
- **Dependencias:** Ninguna (Fixes previos).
- **Entregables:** Código refactorizado, archivo de configuración actualizado, Tests de Regresión (Pytest).
- **Criterios de Éxito (DoD):** El test `test_improved_alignment.py` pasa consistentemente con un Score > 0.85 y cobertura de audio > 50% en el documento de prueba.
- **Tests requeridos:** Unit Tests con casos de borde (texto muy corto, audio muy largo).
- **Riesgos:** Regresión en documentos con estilos de redacción muy diferentes.

### [Fase3-T02] Generador de Datasets "Instruction-Tuning" (Alpaca Formatter) {completado}

- **Título:** Pipeline de Transformación JSONL para Unsloth/Llama-3
- **Descripción:** Crear el componente `DatasetFormatter` en `ASTRA-INGEST` (o `LEARN`). Su función es tomar los pares alineados (Input Audio Text -> Output XML) y transformarlos al formato estándar de instrucción de Llama-3 (Alpaca/ShareGPT). Debe incluir "System Prompts" variados para robustez. Debe dividir determinísticamente en `train` y `validation` sets.
- **Dónde:** `modules/astra-ingest/src/mining/dataset_builder.py`
- **Owner sugerido:** ML Engineer.
- **Prioridad:** **P0**
- **Estimación:** 8 horas.
- **Dependencias:** [Fase3-T01].
- **Entregables:** Archivos `train.jsonl` y `val.jsonl` en S3.
- **Criterios de Éxito (DoD):** Dataset válido generado que puede ser cargado por la librería `datasets` de HuggingFace sin errores.
- **Tests requeridos:** Validación de esquema JSON y integridad de UTF-8.
- **Riesgos:** Fuga de datos (Data Leakage) entre train/val si no se separa por documento/sesión.

### [Fase3-T03] Worker de Entrenamiento Remoto (RunPod Handler) {completado}

- **Título:** Implementación del Handler de Entrenamiento Unsloth en RunPod
- **Descripción:** Desarrollar el script `runpod_training_handler.py` dentro de la imagen Docker de `astra-trainer`. Este script debe: 1. Descargar el dataset desde la URL firmada. 2. Iniciar el entrenamiento `SFTTrainer` (Unsloth). 3. Monitorear Loss. 4. Empaquetar los adaptadores LoRA resultantes (`adapter_model.bin`, `adapter_config.json`). 5. Subirlos a la URL firmada de salida.
- **Dónde:** `services/astra-learn/runpod_training_handler.py`, `services/astra-learn/src/training/train.py`.
- **Owner sugerido:** MLOps Engineer.
- **Prioridad:** **P0**
- **Estimación:** 16 horas.
- **Dependencias:** Dockerfile de `astra-trainer` (definido en fases previas).
- **Entregables:** Imagen Docker funcional en Container Registry, Handler probado.
- **Criterios de Éxito (DoD):** Ejecución end-to-end en RunPod produce un archivo `.zip` en S3 con los pesos del modelo.
- **Tests requeridos:** Ejecución local con GPU simulada o dataset diminuto.
- **Riesgos:** OOM (Out of Memory) en GPU. Mitigar con `gradient_accumulation_steps` y `max_seq_length`.

### [Fase3-T04] Orquestador de Jobs de Entrenamiento (Job Manager) {completado}

- **Título:** Gestión de Estado de Entrenamientos en Redis
- **Descripción:** Actualizar `ASTRA-ORCHESTRATOR` (o `LEARN`) para gestionar el ciclo de vida del Job de entrenamiento. Endpoints para: `submit_training`, `check_status`, `cancel`. Debe mantener el estado (`QUEUED`, `TRAINING`, `COMPLETED`, `FAILED`) en Redis y manejar los Webhooks de retorno de RunPod.
- **Dónde:** `services/astra-orchestrator/src/controllers/training.py`, `src/jobs/manager.py`.
- **Owner sugerido:** Backend Dev.
- **Prioridad:** **P1**
- **Estimación:** 12 horas.
- **Dependencias:** [Fase3-T03].
- **Entregables:** API funcional para iniciar y monitorear entrenamientos.
- **Criterios de Éxito (DoD):** El dashboard muestra la barra de progreso del entrenamiento y actualiza el estado al finalizar.
- **Tests requeridos:** Integration Tests mockeando la API de RunPod.
- **Riesgos:** Pérdida de notificaciones webhook (implementar polling de respaldo).

### [Fase3-T05] Evaluador Automático de Modelos (The Judge) {completado}

- **Título:** Pipeline de Evaluación "Shadow" (A/B Testing Sintético)
- **Descripción:** Antes de promocionar un modelo a producción, el sistema debe validarlo. Implementar un script que corra inferencia sobre el set de validación (`val.jsonl`) usando el nuevo adaptador y calcule métricas: **WER** (Word Error Rate) y **Similitud Semántica**. Si el nuevo modelo es peor que el anterior (regresión), se marca como `REJECTED`.
- **Dónde:** `services/astra-learn/src/evaluation/evaluator.py`.
- **Owner sugerido:** Data Scientist.
- **Prioridad:** **P1**
- **Estimación:** 10 horas.
- **Dependencias:** [Fase3-T03].
- **Entregables:** Reporte de métricas JSON en S3 junto al modelo.
- **Criterios de Éxito (DoD):** Bloqueo automático de modelos que alucinan o generan XML inválido.
- **Tests requeridos:** Unit tests con métricas dummy.

### [Fase3-T06] Mecanismo de Hot-Reload en Core (Intelligence Reloader) {completado}

- **Título:** Sistema de Actualización de Adaptadores en Caliente
- **Descripción:** Modificar `ASTRA-CORE` para escuchar eventos de Redis (`MODEL_PROMOTED`). Al recibir el evento, descargar el nuevo adaptador LoRA en background, cargarlo en memoria RAM (usando `peft`) y hacer el switch atómico de punteros para que las siguientes peticiones usen el nuevo modelo.
- **Dónde:** `services/astra-core/src/inference/model_manager.py`, `src/main.py`.
- **Owner sugerido:** Senior Backend / ML Engineer.
- **Prioridad:** **P1**
- **Estimación:** 14 horas.
- **Dependencias:** [Fase3-T05].
- **Entregables:** Capacidad de cambiar la "inteligencia" del sistema sin reiniciar el contenedor Docker.
- **Criterios de Éxito (DoD):** Inferencia A usa modelo V1, evento ocurre, Inferencia B usa modelo V2. Sin downtime.
- **Tests requeridos:** Test de carga durante el switch.
- **Riesgos:** Pico de uso de RAM durante la carga del segundo modelo (antes de descargar el primero).

---

## 5. Directivas de Calidad

1.  **Data Sanitization:** El `DatasetFormatter` (T02) debe tener un paso estricto de Regex/NER para eliminar o enmascarar nombres propios (PII) antes de subir el dataset a la nube de entrenamiento.
2.  **Model Versioning:** Todo modelo entrenado debe tener un ID único (UUID o Timestamp) y trazabilidad completa al dataset que lo generó (Data Lineage).
3.  **Fail-Safe Inference:** Si el nuevo adaptador falla al cargar en `ASTRA-CORE`, el sistema debe hacer rollback automático al adaptador anterior (Safe Fallback) y alertar.
4.  **Resource Limits:** Los Jobs de RunPod deben tener `timeout` estricto (ej. 1 hora) para evitar facturación infinita si el proceso se cuelga.

## 6. Matriz de Riesgos y Mitigaciones

| Riesgo                        | Probabilidad | Impacto | Mitigación                                                                                                                                                     | Owner   |
| :---------------------------- | :----------: | :-----: | :------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------ |
| **Overfitting (Sobreajuste)** |     Alta     |  Alto   | El modelo memoriza las actas específicas y pierde capacidad de generalización. **Mitigación:** Usar `val_set` riguroso y Early Stopping. Limitar epochs (3-5). | ML Eng  |
| **Corrupción de XML**         |    Media     | Crítico | El modelo aprende a escribir XML malformado. **Mitigación:** El Evaluador (T05) debe validar sintaxis XML estricta. Si falla, el modelo se descarta.           | Backend |
| **Explosión de Costos GPU**   |     Baja     |  Medio  | Errores en el código de entrenamiento dejan instancias vivas. **Mitigación:** Configurar `containerDisk` size y `execution_timeout` en la API de RunPod.       | DevOps  |
| **Latencia en Hot-Swap**      |    Media     |  Bajo   | El servicio se congela mientras carga el modelo. **Mitigación:** Cargar el nuevo modelo en hilo secundario, solo hacer swap cuando esté listo.                 | Backend |

## 7. Checklist de Aceptación (DoD Global de Fase)

- [ ] **Data Pipeline:** `run_mining.py` genera `train.jsonl` con formato Alpaca válido y sin PII obvio.
- [ ] **Training:** Se puede disparar un job desde la API del Orchestrator y ver el resultado en S3 tras ~20-30 mins.
- [ ] **Evaluation:** Existe un reporte JSON que compara el modelo Base vs. Fine-Tuned.
- [ ] **Inference:** `ASTRA-CORE` responde `/v1/process` usando el nuevo adaptador LoRA descargado automáticamente.
- [ ] **Stability:** No hay regresión en la alineación con el algoritmo corregido (Reporte de Cobertura > 50%).

## 8. Artefactos para Due Diligence

1.  **Curated Datasets:** Muestras anónimas de `train.jsonl` y `val.jsonl`.
2.  **Training Logs:** Gráficas de Loss/Accuracy de MLflow o Tensorboard (capturas).
3.  **Diff Reports:** Ejemplos de "Antes vs Después" del Fine-Tuning en la generación de XML.
4.  **Security Scan:** Reporte de escaneo de la imagen Docker del Trainer.

## 9. Export CSV

NO

Al completar este roadmap, habrás pasado de tener un **"Script que transcribe y falla"** a tener una **"Plataforma de Inteligencia Sistémica"**. Dejas de ser un implementador de IA para convertirte en el dueño de un ecosistema que aprende solo.

Aquí te detallo exactamente qué tendrás en tus manos y qué sucederá en la realidad de tu negocio:

---

### 1. ¿Qué tendrás? (Los Activos Técnicos)

- **Un Motor de Minería de Datos Infalible:** Tu alineador ya no será un "agujero negro". Tendrás un algoritmo quirúrgico que sabe exactamente qué segundo de audio corresponde a qué párrafo del acta, descartando el ruido y preservando el valor legal.
- **Una "Fábrica" de Datasets:** Un sistema que, con un solo comando, toma meses de grabaciones y actas viejas y las convierte en archivos de entrenamiento (`.jsonl`) limpios, sin nombres de personas reales (PII) y listos para la nube.
- **Infraestructura Elástica (Serverless):** No tendrás una GPU costosa encendida 24/7. Tendrás un "ejército de reserva" en RunPod que solo despierta cuando hay trabajo, entrena el modelo en 20 minutos por unos pocos centavos, y vuelve a desaparecer.
- **Cerebro con "Hot-Swap":** Tu servicio `ASTRA-CORE` tendrá la capacidad de actualizar su inteligencia sin reiniciarse. Será como cambiar el motor de un avión en pleno vuelo sin que los pasajeros (los usuarios) lo noten.

---

### 2. ¿Qué pasará? (La Realidad Operativa)

- **El Fin de las Alucinaciones de Estructura:** El modelo ya no mezclará intervenciones de 40 minutos en una sola línea. Aprenderá el "ritmo" del Concejo de Manizales: sabrá cómo resumen las oraciones, qué palabras técnicas usan y cómo estructuran el XML nativo de Word sin romperlo.
- **Precisión "Tailor-Made" (A medida):** Si el cliente mañana decide cambiar la forma en que redacta las votaciones, tú no tendrás que programar nada. Simplemente inyectas 5 actas nuevas al sistema, disparas el loop, y el modelo "aprenderá" el nuevo formato automáticamente.
- **Escalabilidad Infinita:** Podrás firmar contratos con 50 municipios mañana mismo. Tu sistema procesará el audio de todos en paralelo usando contenedores remotos y cada municipio tendrá su propio "cerebro" (adaptador LoRA) optimizado para su jerga local.
- **Auditoría de Grado Forense:** Cada vez que el sistema genere un párrafo, sabrás de qué milisegundo de audio vino y con qué nivel de confianza se generó. Si hay una duda legal, el sistema tiene las pruebas.

---

### 3. El Contraste: Antes vs. Después

| Característica    | Antes (Con el Reporte de Error)         | Después (Fase 3 Completada)                    |
| :---------------- | :-------------------------------------- | :--------------------------------------------- |
| **Alineación**    | Un bloque de 42 min = 1 línea de texto. | Bloques de 30-60 seg = Párrafos precisos.      |
| **Cobertura**     | 16% del acta emparejada (84% huérfano). | > 60-80% del acta emparejada y validada.       |
| **Aprendizaje**   | Manual, lento y propenso a errores.     | Automatizado, ciego a datos sensibles y veloz. |
| **Costo GPU**     | Fijo o por API cara de terceros.        | Variable (centavos por entrenamiento).         |
| **Mantenimiento** | Hard-coding de reglas y regex.          | Mejora continua mediante Fine-Tuning.          |

---

### 4. El "Momento Eureka" de tu Negocio

Cuando termines esto, pasará lo siguiente:
Un usuario subirá un audio de 7 horas. Tu sistema lo procesará. Si el modelo actual tiene dudas, el sistema **usará los datos de esa misma sesión para proponer un entrenamiento**. Al día siguiente, cuando el usuario abra el sistema para la siguiente sesión, **la IA será un 5% más inteligente que el día anterior.**

**Habrás creado una máquina que se hace más valiosa cada vez que se usa.** Eso es lo que separa a un proyecto de universidad de un SaaS millonario.

**¿Empezamos con la primera tarea (T01: Refactor del Alineador)?** Es el cimiento de todo este poder.
