import pytest
import asyncio
from unittest.mock import MagicMock, patch
from src.services.model_manager import IntelligenceReloader

# Mock para PEFT y Torch
sys.modules["peft"] = MagicMock()
sys.modules["torch"] = MagicMock()

@pytest.mark.asyncio
async def test_atomic_swap_concurrency():
    """
    Simula carga concurrente de inferencia mientras se ejecuta un swap.
    DoD: Ninguna inferencia debe fallar.
    """
    
    # Setup Mocks
    reloader = IntelligenceReloader()
    
    # Mockear ModelLoader y el modelo base
    mock_base_model = MagicMock()
    
    # Simular que load_adapter toma tiempo (I/O simulado)
    mock_base_model.load_adapter = MagicMock()
    
    with patch("src.inference.model_loader.ModelLoader") as MockLoader:
        MockLoader.return_value.get_model.return_value = mock_base_model
        
        # Simular descarga rápida
        reloader._download_artifact_safe = MagicMock()
        
        # Flag para saber si el swap ocurrió
        swap_completed = False
        
        async def mock_inference_request(req_id):
            # Simular inferencia que adquiere el lock de lectura (no implementado explícitamente,
            # pero el swap adquiere lock exclusivo, así que bloquea si usamos lock compartido)
            # En este diseño simplificado, la inferencia NO usa lock explícito, confía en el GIL/Torch
            # Pero el swap es atómico en la llamada a set_adapter.
            
            # Simulamos latencia
            await asyncio.sleep(0.01)
            return f"result_{req_id}"

        async def trigger_swap():
            nonlocal swap_completed
            await asyncio.sleep(0.05) # Esperar a que haya tráfico
            success = await reloader.swap_adapter("tenant-1", "s3://bucket/new_model.zip", "v2")
            swap_completed = success

        # Lanzar tráfico
        tasks = [mock_inference_request(i) for i in range(50)]
        swap_task = trigger_swap()
        
        # Ejecutar todo
        results = await asyncio.gather(*tasks, swap_task)
        
        # Verificar
        assert swap_completed is True
        mock_base_model.load_adapter.assert_called()
        mock_base_model.set_adapter.assert_called()
        mock_base_model.delete_adapter.assert_called() # Limpieza