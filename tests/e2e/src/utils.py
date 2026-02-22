import hashlib
import os

def calculate_file_hash(file_path: str) -> str:
    """Calcula SHA-256 de un archivo local."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Leer en chunks para ser eficiente en memoria
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def ensure_test_assets(samples_dir: str):
    """
    Genera archivos dummy si no existen, para que el test no falle por falta de inputs.
    """
    os.makedirs(samples_dir, exist_ok=True)
    
    docx_path = os.path.join(samples_dir, "template_test.docx")
    wav_path = os.path.join(samples_dir, "audio_test.wav")

    # Crear DOCX dummy (zip válido vacío o mínimo)
    if not os.path.exists(docx_path):
        # Escribimos un zip header mínimo válido para que INGEST no falle el unzip
        # En un escenario real, esto debería ser un DOCX válido copiado de recursos.
        # Aquí escribimos bytes de "PK..." (Magic number zip)
        with open(docx_path, 'wb') as f:
            # Esto es solo un placeholder, idealmente usar shutil para copiar uno real
            f.write(b'PK\x03\x04' + b'\x00' * 26) 
        print(f"⚠️ Created dummy DOCX at {docx_path}. Integration might fail if Ingest validates OOXML structure strictly.")

    # Crear WAV dummy (header mínimo)
    if not os.path.exists(wav_path):
        # Header WAV mínimo de 44 bytes
        with open(wav_path, 'wb') as f:
            f.write(b'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00')
        print(f"⚠️ Created dummy WAV at {wav_path}")
