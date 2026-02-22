# client_simulation.py
import requests
import time
import os

# Configuración
API_URL = "http://localhost:8001/v1/session"
TENANT_ID = "concejo_manizales"
# EL SKELETON_ID DEBE SER EL QUE OBTUVISTE EN EL PASO 1 (Revisa tu DB o Logs de Ingest)
# Si no lo tienes, el sistema usará uno por defecto si está mockeado, pero idealmente usa el real.
SKELETON_ID = "skel_123abc" 
AUDIO_FILE = "sample_audio.wav" # Pon un archivo de audio real aquí (pequeño para probar, 1-2 min)

def run_simulation():
    # 1. Iniciar Sesión
    print(f"🚀 Iniciando sesión para {TENANT_ID}...")
    start_payload = {
        "tenant_id": TENANT_ID,
        "skeleton_id": SKELETON_ID,
        "client_timezone": "America/Bogota",
        "metadata": {
            "numero_acta": "001-2024",
            "presidente": "Honorable Concejal X"
        }
    }
    
    try:
        resp = requests.post(f"{API_URL}/start", json=start_payload)
        if resp.status_code != 201:
            print(f"❌ Error iniciando: {resp.text}")
            return
        
        session_data = resp.json()
        session_id = session_data["session_id"]
        print(f"✅ Sesión creada: {session_id}")

        # 2. Enviar Audio (Simulando chunks o un archivo entero)
        if not os.path.exists(AUDIO_FILE):
            print(f"⚠️ Creando archivo dummy '{AUDIO_FILE}' para probar.")
            with open(AUDIO_FILE, 'wb') as f: f.write(b'ruido_simulado_123')
        
        print(f"🎙️ Enviando audio...")
        with open(AUDIO_FILE, 'rb') as f:
            files = {'file': (AUDIO_FILE, f, 'audio/wav')}
            data = {'sequence_id': 1}
            resp = requests.post(f"{API_URL}/{session_id}/append", files=files, data=data)
            
        print(f"   Status carga: {resp.status_code} - {resp.json()}")

        # 3. Esperar procesamiento (Simulado)
        print("⏳ Esperando procesamiento de IA...")
        time.sleep(5) 

        # 4. Finalizar y Construir
        print("🏗️ Finalizando sesión y construyendo documento...")
        resp = requests.post(f"{API_URL}/{session_id}/finalize")
        
        if resp.status_code == 202:
            print("⚠️ El sistema está terminando de procesar (Draining). Intenta de nuevo en unos segundos.")
            # En un sistema real, harías polling aquí
        elif resp.status_code == 200:
            result = resp.json()
            print("\n" + "="*40)
            print("🎉 ¡ACTA GENERADA CON ÉXITO!")
            print("="*40)
            print(f"📥 URL Descarga: {result.get('download_url')}")
            print(f"🛡️ Hash Integridad: {result.get('integrity_hash')}")
        else:
            print(f"❌ Error finalizando: {resp.text}")
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        print("Asegúrate de que el Orchestrator esté corriendo en el puerto 8001.")

if __name__ == "__main__":
    run_simulation()
