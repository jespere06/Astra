import argparse
import sys
import os
import logging
from tabulate import tabulate

# Setup path to allow importing from src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.db.base import SessionLocal
from src.core.admin.label_manager import LabelManager
from src.db.models import EntityType

def list_unlabeled(args):
    db = SessionLocal()
    try:
        mgr = LabelManager(db)
        templates = mgr.get_unlabeled_templates(args.tenant_id, args.limit)
        
        data = []
        for t in templates:
            # Mostramos metadatos básicos
            vars_str = ",".join(t.variables_metadata) if t.variables_metadata else "N/A"
            data.append([
                str(t.id)[:8], 
                t.structure_hash[:12], 
                vars_str, 
                t.created_at.strftime("%Y-%m-%d")
            ])
        
        if not data:
            print(f"✅ No se encontraron templates sin etiqueta para el tenant: {args.tenant_id}")
        else:
            print(tabulate(data, headers=["ID", "Hash", "Variables", "Fecha"], tablefmt="grid"))
    finally:
        db.close()

def label_hash(args):
    db = SessionLocal()
    try:
        mgr = LabelManager(db)
        lbl = mgr.assign_label(
            args.tenant_id, 
            args.hash, 
            args.name, 
            EntityType.TEMPLATE
        )
        print(f"✅ Etiqueta asignada exitosamente: {lbl} para hash {args.hash}")
    except Exception as e:
        print(f"❌ Error al asignar etiqueta: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ASTRA Admin CLI - Gestión de Etiquetas")
    subparsers = parser.add_subparsers(dest="command")

    # Listar unlabeled
    list_parser = subparsers.add_parser("list-unlabeled", help="Listar templates pendientes de etiquetado")
    list_parser.add_argument("--tenant-id", required=True, help="ID del Tenant")
    list_parser.add_argument("--limit", type=int, default=15, help="Límite de resultados")

    # Asignar etiqueta
    label_parser = subparsers.add_parser("set-label", help="Asignar nombre semántico a un hash estructural")
    label_parser.add_argument("--tenant-id", required=True, help="ID del Tenant")
    label_parser.add_argument("--hash", required=True, help="Structure Hash del template")
    label_parser.add_argument("--name", required=True, help="Nombre semántico (ej. CIERRE_ACTA)")

    args = parser.parse_args()
    
    if args.command == "list-unlabeled":
        list_unlabeled(args)
    elif args.command == "set-label":
        label_hash(args)
    else:
        parser.print_help()