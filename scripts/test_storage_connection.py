import sys
import os
import logging
import requests

# Añadir el root al path para importar libs
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from libs.shared_kernel.src.storage import S3StorageAdapter, StorageSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StorageTest")

def run_test():
    try:
        # 1. Inicializar
        logger.info("🔧 Inicializando adaptador S3...")
        # Asegurarse de tener las variables de entorno seteadas o crear un .env
        adapter = S3StorageAdapter()
        
        test_bucket = "astra-dev-test" 
        test_key = "test_connectivity/hello.txt"
        test_content = b"Hola Mundo desde ASTRA Storage Adapter!"

        # 2. Prueba de Subida
        logger.info(f"pV Subiendo archivo a {test_bucket}/{test_key}...")
        uri = adapter.upload(test_content, test_key, bucket=test_bucket)
        logger.info(f"✅ Subida exitosa. URI: {uri}")

        # 3. Prueba de Existencia
        exists = adapter.exists(test_key, bucket=test_bucket)
        if exists:
            logger.info("✅ Verificación de existencia exitosa.")
        else:
            logger.error("❌ El archivo subido no parece existir.")
            return

        # 4. Prueba de Presigned URL
        logger.info("🔗 Generando URL prefirmada...")
        url = adapter.generate_presigned_url(test_key, bucket=test_bucket, expiration=60)
        logger.info(f"   URL: {url}")
        
        # 5. Validación de Acceso Externo (Simular Worker)
        logger.info("🌍 Probando acceso HTTP a la URL prefirmada...")
        resp = requests.get(url)
        if resp.status_code == 200 and resp.content == test_content:
            logger.info("✅ Acceso HTTP exitoso y contenido verificado.")
        else:
            logger.error(f"❌ Fallo al descargar vía HTTP: {resp.status_code}")
            return

        # 6. Limpieza
        logger.info("🧹 Limpiando archivo de prueba...")
        adapter.delete(test_key, bucket=test_bucket)
        logger.info("✅ Limpieza completada.")
        
        print("\n🎉 PRUEBA DE ALMACENAMIENTO COMPLETADA CON ÉXITO")

    except Exception as e:
        logger.error(f"❌ Error durante la prueba: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
