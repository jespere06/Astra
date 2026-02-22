---
description: Cómo realizar construcciones rápidas en Mac (M1/M2/M3)
---

Este flujo optimiza los tiempos de construcción de Docker en arquitecturas Apple Silicon.

### 1. Configuración de Docker Desktop (Crítico)

Para que los volúmenes y la construcción sean instantáneos:

1. Abre **Settings** → **General**.
2. Marca **"Use Virtualization framework"**.
3. Ve a **Resources** → **File Sharing**.
4. Cambia de "gRPC FUSE" a **"VirtioFS"**.
5. Haz clic en **Apply & Restart**.

### 2. Uso del Script de Construcción Rápida

He creado un script que desactiva los metadatos de seguridad pesados (`provenance`) y fuerza la arquitectura nativa.

// turbo

```bash
./ops/scripts/fast_build.sh
```

### 3. Limpieza de Caché

Si los builds siguen tardando o hay errores extraños, limpia el caché acumulado:

// turbo

```bash
./ops/scripts/fast_build.sh --clean
```

---

**Nota:** El servicio `astra-worker` está configurado en un perfil separado para no ser construido localmente, ya que contiene librerías pesadas de GPU.
