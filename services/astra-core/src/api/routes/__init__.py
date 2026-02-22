from fastapi import APIRouter
from .transcription import router as transcription_router
from .core import router as core_logic_router

router = APIRouter()

# Registrar rutas de transcripción
router.include_router(transcription_router)

# Mantener las rutas anteriores de lógica de negocio (pipeline semántico)
router.include_router(core_logic_router)
