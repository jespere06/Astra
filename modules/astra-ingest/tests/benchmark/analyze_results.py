
import json
import os
import sys
import numpy as np
from sklearn.linear_model import LinearRegression

# Rutas
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_FILE = os.path.join(BASE_DIR, "results_raw.json")
REPORT_FILE = os.path.join(BASE_DIR, "final_report.md")

def analyze():
    print(f"🔍 Analizando resultados desde: {RESULTS_FILE}")
    
    if not os.path.exists(RESULTS_FILE):
        print(f"❌ Error: No se encontró el archivo {RESULTS_FILE}. Ejecute run_load_test.py primero.")
        sys.exit(1)

    try:
        with open(RESULTS_FILE, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print("❌ Error: Archivo JSON corrupto.")
        sys.exit(1)

    if not data:
        print("⚠️ No hay datos para analizar.")
        return

    # Filtrar solo ejecuciones exitosas
    valid_data = [d for d in data if d.get('success', False)]
    
    if not valid_data:
        print("❌ No hay ejecuciones exitosas para analizar.")
        return

    # Preparar datos para regresión
    X = np.array([d['n_docs'] for d in valid_data]).reshape(-1, 1)
    y = np.array([d['duration_seconds'] for d in valid_data])
    
    # Modelo Lineal (y = mx + b)
    # Asumimos comportamiento lineal para el parser/embedder, aunque HDBSCAN es O(N log N) o peor.
    model = LinearRegression()
    model.fit(X, y)
    
    # Proyección para 1000 documentos
    N_TARGET = 1000
    pred_seconds = model.predict([[N_TARGET]])[0]
    pred_minutes = pred_seconds / 60
    
    # Análisis de No-Linealidad (Factor de Crecimiento)
    min_batch = valid_data[0]
    max_batch = valid_data[-1]
    
    t_doc_min = min_batch['duration_seconds'] / min_batch['n_docs']
    t_doc_max = max_batch['duration_seconds'] / max_batch['n_docs']
    
    growth_factor = t_doc_max / t_doc_min if t_doc_min > 0 else 1.0
    
    is_stable = growth_factor < 1.3 # Permitimos 30% de degradación
    
    # Evaluación SLA (< 60 minutos)
    sla_threshold_seconds = 3600
    status = "PASS" if pred_seconds < sla_threshold_seconds else "FAIL"
    status_icon = "✅" if status == "PASS" else "❌"

    # Generar Reporte Markdown
    report_content = f"""# 📊 Reporte de Benchmark ASTRA-INGEST

## Resumen Ejecutivo
* **Estado SLA (1000 docs < 1h):** {status_icon} **{status}**
* **Tiempo Proyectado (N=1000):** {pred_minutes:.2f} minutos ({pred_seconds:.0f} segundos)
* **Estabilidad:** {'🟢 Lineal/Estable' if is_stable else '🔴 Degradación Detectada'}
* **Factor de Crecimiento:** {growth_factor:.2f}x (Tiempo por doc entre N={min_batch['n_docs']} y N={max_batch['n_docs']})

## Detalles de Ejecución
| N Documentos | Tiempo Total (s) | Tiempo/Doc (s) | RAM Pico (MB) | CPU Pico (%) |
|:---:|:---:|:---:|:---:|:---:|
"""
    
    for d in valid_data:
        t_doc = d['duration_seconds'] / d['n_docs']
        report_content += f"| {d['n_docs']} | {d['duration_seconds']:.2f} | {t_doc:.2f} | {d['peak_ram_mb']:.1f} | {d['peak_cpu_percent']}% |\n"

    report_content += "\n## Análisis Técnico\n"
    report_content += f"- **Ecuación de Regresión:** T(n) = {model.coef_[0]:.4f} * n + {model.intercept_:.2f}\n"
    
    if not is_stable:
        report_content += "- ⚠️ **Alerta:** Se detectó que el tiempo de procesamiento por documento aumenta con el tamaño del lote. Esto sugiere que el paso de **Clustering (HDBSCAN)** está dominando la complejidad computacional.\n"
    else:
        report_content += "- ✅ El sistema escala linealmente dentro de los rangos probados.\n"

    # Guardar reporte
    with open(REPORT_FILE, 'w') as f:
        f.write(report_content)
    
    print(f"\n📝 Reporte generado en: {REPORT_FILE}")
    print("-" * 40)
    print(report_content)
    print("-" * 40)

if __name__ == "__main__":
    analyze()
