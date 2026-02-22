from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from src.infrastructure.database import get_db
from src.infrastructure.models import Skeleton, Asset
from src.core.atomizer import OOXMLDissector
from src.core.asset_manager import AssetManager

# Mantenemos el prefijo vacío aquí porque main.py le pondrá /v1
# pero la ruta final debe ser /v1/ingest (POST) para que el Dashboard no se rompa
router = APIRouter(tags=["Document"])

@router.post("/ingest", status_code=201)
async def ingest_document(
    file: UploadFile = File(...),
    tenant_id: str = Form(...),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith('.docx'):
        raise HTTPException(status_code=422, detail="Formato no soportado. Use .docx")

    content = await file.read()
    
    # 1. Dissectar OOXML
    try:
        dissector = OOXMLDissector(content)
        skeleton_xml = dissector.extract_skeleton()
        media_map = dissector.extract_media_map()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error parseando DOCX: {str(e)}")

    # 2. Procesar Assets
    asset_manager = AssetManager()
    processed_assets = []
    
    for fname, fbytes in media_map.items():
        asset_meta = asset_manager.process_image(fname, fbytes)
        if asset_meta:
            processed_assets.append(asset_meta)

    # 3. Guardar Skeleton en S3
    skeleton_s3_path = asset_manager.upload_skeleton(skeleton_xml, tenant_id)

    # 4. Persistir en DB
    db_skeleton = Skeleton(
        tenant_id=tenant_id,
        s3_path=skeleton_s3_path,
        original_filename=file.filename
    )
    db.add(db_skeleton)
    db.flush() # Para obtener ID

    for asset in processed_assets:
        db_asset = Asset(
            skeleton_id=db_skeleton.id,
            p_hash=asset['p_hash'],
            original_name=asset['original_name'],
            s3_path=asset['s3_path']
        )
        db.add(db_asset)

    db.commit()

    return {
        "status": "success",
        "skeleton_id": db_skeleton.id,
        "assets_extracted": len(processed_assets),
        "s3_skeleton": skeleton_s3_path
    }
