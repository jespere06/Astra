import pandas as pd
import os

# ================= CONFIGURACIÓN =================
# Archivo generado en el paso anterior
INPUT_CSV = 'match_sesiones_optimizado.csv'

# Carpeta donde están los .docx originales
DOCX_DIR = '/Users/jesusandresmezacontreras/projects/astra/minutes'

# Archivo de salida para el Dashboard
OUTPUT_CSV = 'dataset_entrenamiento.csv'

# Umbral de confianza para incluir en el entrenamiento
# (Solo entrenamos con matches de alta certeza)
UMBRAL_CONFIANZA = 0.0 
# ================================================

def main():
    # 1. Cargar el CSV de matches
    if not os.path.exists(INPUT_CSV):
        print(f"❌ Error: No se encuentra {INPUT_CSV}")
        return

    df = pd.read_csv(INPUT_CSV)
    
    print(f"📊 Total de registros encontrados: {len(df)}")

    training_rows = []
    
    for _, row in df.iterrows():
        # Validaciones básicas
        if pd.isna(row['Link']) or row['Link'] == "No encontrado":
            continue
            
        if row['Confianza'] < UMBRAL_CONFIANZA:
            continue

        # Convertir nombre de .txt a .docx
        # Asumimos que el nombre base es idéntico
        txt_filename = row['Archivo']
        if txt_filename.endswith('.txt'):
            docx_filename = txt_filename[:-4] + ".docx"
        else:
            docx_filename = txt_filename + ".docx"

        # Construir ruta absoluta
        abs_path = os.path.join(DOCX_DIR, docx_filename)

        # Verificar que el archivo DOCX exista físicamente
        if os.path.exists(abs_path):
            training_rows.append({
                # El formato que espera tu Dashboard es: URL, PATH_DOCX
                'url': row['Link'],
                'docx_path': abs_path
            })
        else:
            print(f"⚠️ Alerta: DOCX no encontrado para: {docx_filename}")

    # 2. Crear DataFrame de entrenamiento
    training_df = pd.DataFrame(training_rows)

    # 3. Guardar sin cabeceras (header=False) si tu dashboard lee CSV crudo,
    # o con cabeceras si lo prefieres.
    # Según tu código de React: `const url = columns[0]; const docxPath = columns[1]`
    # Parece que NO espera cabeceras, o las salta si no son URLs. 
    # Lo guardaremos SIN cabeceras para máxima compatibilidad con tu código de frontend.
    training_df.to_csv(OUTPUT_CSV, index=False, header=False)

    print("\n" + "="*50)
    print(f"✅ DATASET DE ENTRENAMIENTO GENERADO: {OUTPUT_CSV}")
    print("="*50)
    print(f"🔹 Total pares válidos: {len(training_df)}")
    print(f"🔹 Umbral de confianza usado: {UMBRAL_CONFIANZA}")
    print("\n👉 Ahora ve al Dashboard -> Training Module -> 'Import CSV'")
    print("   y selecciona este archivo.")

if __name__ == '__main__':
    main()