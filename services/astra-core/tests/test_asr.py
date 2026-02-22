import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.asr.providers.openai_whisper import OpenAIWhisperAPI

@pytest.mark.asyncio
async def test_openai_transcribe_success():
    # Mock del cliente de OpenAI
    mock_client = AsyncMock()
    # Mock de la respuesta de la API
    # The real client.audio.transcriptions.create returns a string when format="text"
    mock_client.audio.transcriptions.create.return_value = "Texto transcrito de prueba."

    # Inyección del mock
    with patch("src.asr.providers.openai_whisper.AsyncOpenAI", return_value=mock_client):
        provider = OpenAIWhisperAPI(api_key="sk-fake-key")
        
        # Ejecución
        audio_dummy = b"fake_audio_bytes"
        result = await provider.transcribe(audio_dummy, filename="test.wav")
        
        # Verificación
        assert result == "Texto transcrito de prueba."
        mock_client.audio.transcriptions.create.assert_called_once()
        
        # Verificar argumentos de llamada
        call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
        assert call_kwargs["model"] == "whisper-1"
        assert call_kwargs["language"] == "es"
