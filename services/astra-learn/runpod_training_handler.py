import runpod
import os
import sys
import requests
import shutil
import zipfile
import logging

# Configuración de Logging para RunPod (stdout)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ASTRA-WORKER")

# Asegurar que 'src' sea importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

try:
    from src.training.train import train
except ImportError:
    # Fallback para desarrollo local si el path no coincide exactamente
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))
    from src.training.train import train

def download_file(url: str, local_path: str):
    """Descarga un archivo desde una URL (Presigned S3)."""
    logger.info(f"⬇️ Descargando dataset desde {url[:20]}...")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    logger.info(f"✅ Dataset descargado en {local_path}")

def upload_file(local_path: str, upload_url: str):
    """Sube un archivo usando una URL Presigned PUT."""
    logger.info(f"⬆️ Subiendo resultado a {upload_url[:20]}...")
    with open(local_path, 'rb') as f:
        # Nota: Usamos PUT porque la mayoría de las Presigned URLs para upload en S3 son PUT
        response = requests.put(upload_url, data=f)
        response.raise_for_status()
    logger.info("✅ Upload completado exitosamente.")

def zip_directory(folder_path: str, output_path: str):
    """Comprime la carpeta de salida (adaptador LoRA)."""
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zipf.write(file_path, arcname)
    logger.info(f"📦 Artefactos comprimidos en {output_path}")

def handler(event):
    """
    Handler principal ejecutado por RunPod.
    Expected Input:
    {
        "input": {
            "dataset_url": "https://s3...",
            "validation_url": "https://...",
            "upload_url": "https://s3...",
            "hyperparameters": { "epochs": 3, "lr": 2e-4 }
        }
    }
    """
    job_input = event.get("input", {})
    
    dataset_url = job_input.get("dataset_url")
    upload_url = job_input.get("upload_url")
    validation_url = job_input.get("validation_url")
    params = job_input.get("hyperparameters", {})
    
    # 1. Validaciones
    if not dataset_url:
        return {"error": "Missing 'dataset_url' in input."}
    if not upload_url:
        return {"error": "Missing 'upload_url' in input."}

    local_train_path = "train.jsonl"
    local_val_path = "val.jsonl"
    output_dir = "astra-lora-adapter"
    output_zip = "adapter.zip"

    try:
        # 2. Descargar Datasets
        download_file(dataset_url, local_train_path)
        
        if validation_url:
            download_file(validation_url, local_val_path)
        else:
            # Si no hay validación, usamos train como dummy
            logger.info("⚠️ No validation set provided. Using train set for validation logic.")
            shutil.copy(local_train_path, local_val_path)

        # 3. Ejecutar Entrenamiento
        logger.info("🔥 Iniciando Fine-Tuning...")
        train(
            dataset_path=local_train_path,
            val_dataset_path=local_val_path,
            output_dir=output_dir,
            max_seq_length=params.get("max_seq_length", 2048),
            load_in_4bit=True
        )

        # 4. Empaquetar y Subir
        zip_directory(output_dir, output_zip)
        upload_file(output_zip, upload_url)

        return {
            "status": "success",
            "message": "Training completed and uploaded.",
            "metrics": {"epochs": params.get("epochs", 3)} 
        }

    except Exception as e:
        logger.error(f"❌ Error crítico en Worker: {str(e)}", exc_info=True)
        return {"status": "failed", "error": str(e)}

    finally:
        # 5. Limpieza
        if os.path.exists(local_train_path): os.remove(local_train_path)
        if os.path.exists(local_val_path): os.remove(local_val_path)
        if os.path.exists(output_zip): os.remove(output_zip)
        if os.path.exists(output_dir): shutil.rmtree(output_dir)

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})