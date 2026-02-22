from pathlib import Path
from docx import Document

# Rutas
base_path = Path(__file__).parent.parent.parent.parent # /Users/jesusandresmezacontreras/projects/astra
input_dir = base_path / "minutes"
output_dir = base_path / "minutes-txt"

# Crear carpeta destino si no existe
output_dir.mkdir(parents=True, exist_ok=True)

# Procesar todos los .docx
for docx_file in input_dir.glob("*.docx"):
    try:
        document = Document(docx_file)
        
        # Extraer texto exactamente como está (por párrafos)
        full_text = "\n".join(paragraph.text for paragraph in document.paragraphs)

        # Nombre de salida
        output_file = output_dir / (docx_file.stem + ".txt")

        # Guardar sin modificar encoding (UTF-8 estándar)
        output_file.write_text(full_text, encoding="utf-8")

        print(f"Convertido: {docx_file.name} → {output_file.name}")

    except Exception as e:
        print(f"Error procesando {docx_file.name}: {e}")

print("Conversión finalizada.")
