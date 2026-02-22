import os
import sys
import csv
import logging
from src.db.base import SessionLocal
from src.db.models import Template

# Inyectar path para encontrar 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def export_templates_to_csv():
    output_file = "templates_report.csv"
    
    db = SessionLocal()
    try:
        templates = db.query(Template).all()
        
        if not templates:
            print("❌ No se encontraron plantillas en la base de datos.")
            return

        with open(output_file, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Cabeceras
            writer.writerow(["ID", "Type", "Tenant ID", "Structure Hash", "Variables", "Cluster Source", "Created At"])
            
            for t in templates:
                type_label = "BOILERPLATE" if t.is_boilerplate else "TEMPLATE"
                writer.writerow([
                    t.id, 
                    type_label,
                    t.tenant_id, 
                    t.structure_hash, 
                    ", ".join(t.variables_metadata) if t.variables_metadata else "None", 
                    t.cluster_source_id, 
                    t.created_at
                ])
        
        print(f"✅ Reporte generado: {os.path.abspath(output_file)}")
        print(f"📊 Total de plantillas exportadas: {len(templates)}")

    except Exception as e:
        print(f"❌ Error al exportar: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    export_templates_to_csv()
