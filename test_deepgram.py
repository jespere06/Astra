# test_deepgram.py
import os
import sys
from dotenv import load_dotenv # <--- 1. Importar esto

# 2. Cargar el archivo .env (o .env.hybrid si usas ese nombre)
# Si tu archivo se llama .env.hybrid, usa load_dotenv(".env.hybrid")
load_dotenv() 

# Agregar la ruta de astra-core para que Python encuentre los módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "services/astra-core")))

from src.engine.transcription.factory import create_transcriber

def test_transcription():
    # ⚠️ CAMBIA ESTO por la ruta a un archivo de audio REAL
    audio_path = "/Users/jesusandresmezacontreras/projects/prueba.mp3" 
    
    if not os.path.exists(audio_path):
        print(f"❌ Error: No se encontró el archivo de audio '{audio_path}'")
        return

    print("🚀 Inicializando Motor de Transcripción (Deepgram)...")
    
    # Verificación de depuración para ver si cargó la key
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        print("❌ ALERTA: No se detectó DEEPGRAM_API_KEY en las variables de entorno.")
        print("   Asegúrate de tener un archivo .env en la misma carpeta.")
    else:
        print(f"🔑 API Key detectada: {api_key[:5]}...")

    try:
        engine = create_transcriber(
            provider="deepgram",
            config={
                "language": "es",
                "smart_format": True,
                "punctuate": True,
            }
        )
        
        print(f"🎙️ Enviando archivo '{audio_path}' a {engine.provider_name}...")
        
        # Ejecutamos la transcripción
        result = engine.transcribe(audio_path)
        
        print("\n" + "="*50)
        print("✅ TRANSCRIPCIÓN COMPLETADA EXITOSAMENTE")
        print("="*50)
        print(f"⏱️  Duración del audio : {result.duration_seconds} segundos")
        print(f"📝 TEXTO COMPLETO:\n{result.text}")
            
    except Exception as e:
        print(f"\n❌ Ocurrió un error en la prueba: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_transcription()