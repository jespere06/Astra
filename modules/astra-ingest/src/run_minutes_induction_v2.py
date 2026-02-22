import os
import sys
import logging
from sqlalchemy.orm import Session
from src.db.base import SessionLocal
from src.core.ingest_orchestrator import IngestOrchestrator

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def run_minutes_induction():
    # Ruta absoluta basada en tu estructura actual
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    minutes_dir = os.path.join(base_path, "minutes")
    
    # Archivo opcional de "Deber ser"
    manual_path = os.path.join(base_path, "minutes-txt", "Formato actas 2025.docx")
    
    if not os.path.exists(minutes_dir):
        logger.error(f"❌ No se encontró el directorio de actas: {minutes_dir}")
        return

    # 1. Cargar documentos reales
    docx_files = [os.path.join(minutes_dir, f) for f in os.listdir(minutes_dir) if f.endswith('.docx')]
    
    if not docx_files:
        logger.error("❌ No hay archivos .docx en la carpeta minutes.")
        return

    # Tomamos una muestra representativa (o todos si son pocos)
    test_files = docx_files[:20] 
    logger.info(f"📂 Cargados {len(test_files)} documentos para inducción de patrones.")

    # 2. Configurar Tenant y DB
    db = SessionLocal()
    tenant_id = "concejo_manizales_learning"
    
    try:
        orchestrator = IngestOrchestrator(db)
        
        # --- LÓGICA RESILIENTE DE SEMILLA ---
        seed_file = None
        
        if os.path.exists(manual_path):
            logger.info(f"📘 Usando Manual Maestro como semilla: {manual_path}")
            seed_file = manual_path
        else:
            logger.warning(f"⚠️ No se encontró manual en {manual_path}")
            logger.info(f"🧠 ESTRATEGIA ADAPTATIVA: Usando el primer documento real como semilla de aprendizaje.")
            seed_file = test_files[0]

        # Ingestar semilla
        orchestrator.seed_engine.ingest_manual(seed_file)
        orchestrator.seed_engine.save_anchors_to_db(db, tenant_id)

        # 3. Procesar el lote completo (Minería de Patrones)
        logger.info("🚀 Iniciando clustering y extracción de pares Transcripción <> XML...")
        result_msg = orchestrator.process_batch(test_files, tenant_id=tenant_id)
        
        logger.info("="*50)
        logger.info(f"✅ {result_msg}")
        logger.info("="*50)

        # 4. Reporte de Resultados
        from src.db.models import Template, Skeleton
        templates = db.query(Template).filter_by(tenant_id=tenant_id).all()
        skeletons = db.query(Skeleton).filter_by(tenant_id=tenant_id).all()

        print(f"\n📊 RESULTADOS DE APRENDIZAJE:")
        print(f"➤ Patrones XML Únicos Detectados: {len(templates)}")
        print(f"➤ Documentos Estructurados (Skeletons): {len(skeletons)}")
        
        if templates:
            print("\n🔹 MUESTRA DE PARES GENERADOS (TRANSCRIPCIÓN -> XML):")
            for i, t in enumerate(templates[:5]):
                label = "BOILERPLATE (Fijo)" if t.is_boilerplate else "DINÁMICO (Variable)"
                print(f"  {i+1}. [{label}] ID: {t.id}")
                print(f"     Variables detectadas: {t.variables_metadata}")
                print(f"     Preview: {t.preview_text[:100]}...")
                print("-" * 30)

    except Exception as e:
        logger.error(f"❌ Error crítico en el pipeline: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    # Inyectar path para encontrar 'src'
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    run_minutes_induction()