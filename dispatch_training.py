import os
import json
import time
import asyncio
import boto3
from botocore.client import Config
from datetime import datetime
from dotenv import load_dotenv

# 1. Cargar el entorno
load_dotenv(".env.hybrid")

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "services/astra-learn")))
from src.infrastructure.clients.runpod_client import RunPodClient

# ================= CONFIGURACIÓN DE RED (THE HACKER WAY) =================
TENANT_ID = "concejo_manizales"
TRAIN_PATH = "dataset_final/train.jsonl"
VAL_PATH = "dataset_final/val.jsonl"
S3_BUCKET = "astra-models"

# ⚠️ PEGA AQUÍ TU URL DE NGROK (sin el slash final)
NGROK_URL = "https://5b84-186-82-100-9.ngrok-free.app"

# MinIO default creds (las que tienes en local)
AWS_AK = "admin"
AWS_SK = "astra_minio_pass"
# =========================================================================

async def run_dispatch():
    print(f"\n🚀 Iniciando Despacho (Ngrok Mode) para {TENANT_ID}...")
    print(f"🌍 Endpoint Público: {NGROK_URL}")

    # 1. Configurar Cliente S3 apuntando a NGROK
    # IMPORTANTE: s3={'addressing_style': 'path'} es vital para que MinIO entienda las peticiones de ngrok
    s3 = boto3.client(
        's3',
        endpoint_url=NGROK_URL,
        aws_access_key_id=AWS_AK,
        aws_secret_access_key=AWS_SK,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}),
        region_name="us-east-1"
    )

    # Asegurar que el bucket exista
    try:
        s3.head_bucket(Bucket=S3_BUCKET)
    except:
        print(f"🪣 Creando bucket {S3_BUCKET}...")
        s3.create_bucket(Bucket=S3_BUCKET)

    # 2. Subir Datasets y Generar URLs
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    train_key = f"training/datasets/{TENANT_ID}/{timestamp}/train.jsonl"
    val_key = f"training/datasets/{TENANT_ID}/{timestamp}/val.jsonl"
    output_key = f"training/adapters/{TENANT_ID}/{timestamp}/adapter.zip"

    print("📦 Subiendo datasets a MinIO (via Ngrok)...")
    with open(TRAIN_PATH, 'rb') as f: s3.upload_fileobj(f, S3_BUCKET, train_key)
    with open(VAL_PATH, 'rb') as f: s3.upload_fileobj(f, S3_BUCKET, val_key)

    print("🔗 Generando URLs criptográficas temporales para el Worker (Válidas por 24h)...")
    train_url = s3.generate_presigned_url('get_object', Params={'Bucket': S3_BUCKET, 'Key': train_key}, ExpiresIn=86400)
    val_url = s3.generate_presigned_url('get_object', Params={'Bucket': S3_BUCKET, 'Key': val_key}, ExpiresIn=86400)
    upload_url = s3.generate_presigned_url('put_object', Params={'Bucket': S3_BUCKET, 'Key': output_key}, ExpiresIn=86400)

    # 3. Armar Payload para RunPod
    payload = {
        "dataset_url": train_url,
        "validation_url": val_url,
        "upload_url": upload_url,
        "hyperparameters": {
            "epochs": 3,
            "learning_rate": 2e-4,
            "max_seq_length": 2048,
            "batch_size": 2 # Ideal para RTX 4090
        }
    }

    # 4. Despachar a RunPod
    # Asume que RUNPOD_API_KEY y RUNPOD_ENDPOINT_ID están en tu .env.hybrid
    client = RunPodClient()
    
    try:
        print("🔥 Despertando GPU en RunPod y enviando la orden...")
        job_id = await client.submit_job(payload)
        print(f"🎫 JOB ACEPTADO: ID {job_id}")
        
        report_data = {
            "job_id": job_id,
            "tenant_id": TENANT_ID,
            "timestamp_started": timestamp,
            "output_s3_key": output_key,
            "payload": payload,
            "status": "IN_QUEUE"
        }
        
        report_file = f"reports_jobs/job_{job_id}.json"
        os.makedirs("reports_jobs", exist_ok=True)
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=4)
        
        print("\n⏳ Iniciando Radar de Monitoreo (Polling cada 20 segundos)...")
        print("   Nota: Un entrenamiento de 1600 pares puede tardar entre 15 y 30 minutos.")
        
        # 5. Polling del Estado
        while True:
            status_res = await client.get_status(job_id)
            status = status_res.get("status", "UNKNOWN")
            
            current_time = datetime.now().strftime('%H:%M:%S')
            print(f"   [{current_time}] Estado del Worker: {status}")
            
            if status == "COMPLETED":
                print("\n" + "="*50)
                print("🎉 ¡ENTRENAMIENTO COMPLETADO EXITOSAMENTE!")
                print("="*50)
                print(f"📥 El nuevo adaptador Lora bajó mágicamente a tu MinIO local en: {output_key}")
                
                report_data["status"] = "COMPLETED"
                report_data["timestamp_finished"] = datetime.now().isoformat()
                report_data["runpod_response"] = status_res
                with open(report_file, 'w') as f:
                    json.dump(report_data, f, indent=4)
                break
                
            elif status in ["FAILED", "CANCELLED"]:
                print("\n❌ EL ENTRENAMIENTO FALLÓ O FUE CANCELADO.")
                print(f"Detalles desde la nube: {status_res.get('error', status_res)}")
                
                report_data["status"] = status
                report_data["timestamp_finished"] = datetime.now().isoformat()
                report_data["error"] = status_res
                with open(report_file, 'w') as f:
                    json.dump(report_data, f, indent=4)
                break
            
            time.sleep(20)
            
    except Exception as e:
        print(f"\n❌ Error crítico en la orquestación: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_dispatch())