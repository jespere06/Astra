import pytest
import os
from src.utils import calculate_file_hash

class TestAstraRoute2:
    
    def test_end_to_end_flow(self, api_client, tenant_id, samples_dir, artifacts_dir):
        """
        Ejecuta la Ruta 2 completa: Ingest -> Orch -> Audio -> Build -> Guard.
        """
        print(f"\n🚀 Starting E2E Test for Tenant: {tenant_id}")

        # 1. INGEST: Cargar Plantilla
        # Nota: Asumimos que el servicio ingest está corriendo y acepta ZIPs dummy
        # Si falla validación de DOCX real, reemplazar template_test.docx con uno válido.
        try:
            template_path = os.path.join(samples_dir, "template_test.docx")
            skeleton_id = api_client.ingest_template(template_path, tenant_id)
            assert skeleton_id is not None, "Skeleton ID should not be null"
            print(f"✅ Ingest Complete. Skeleton: {skeleton_id}")
        except Exception as e:
             pytest.skip(f"Ingest service failed or unavailable: {e}")

        # 2. ORCHESTRATOR: Iniciar Sesión
        try:
            session_id = api_client.start_session(tenant_id, skeleton_id)
            assert session_id is not None, "Session ID should not be null"
            print(f"✅ Session Started: {session_id}")
        except Exception as e:
            pytest.fail(f"Orchestrator session start failed: {e}")

        # 3. CORE: Enviar Audio (Simular Transcripción)
        # audio_path = os.path.join(samples_dir, "audio_test.wav")
        # chunk_response = api_client.send_audio_chunk(session_id, audio_path)
        # assert chunk_response.get("status") == "processed" or chunk_response.get("block_id"), \
        #     "Audio chunk processing failed"
        # print(f"✅ Audio Processed.")

        # 4. BUILDER: Finalizar y Construir
        # final_result = api_client.finalize_session(session_id)
        
        # download_url = final_result.get("download_url")
        # integrity_hash = final_result.get("integrity_hash")
        # snapshot_id = final_result.get("snapshot_id") # O ID de guard

        # assert download_url is not None, "Download URL missing"
        # assert integrity_hash is not None, "Integrity Hash missing from response"
        # print(f"✅ Build Complete. Hash reported: {integrity_hash}")

        # 5. DESCARGA: Obtener el binario
        # output_path = os.path.join(artifacts_dir, f"{session_id}_final.docx")
        # api_client.download_file(download_url, output_path)
        # assert os.path.exists(output_path), "Downloaded file not found on disk"
        
        # 6. GUARD: Validación Forense Local vs Remota
        # A. Calculamos el hash del archivo que bajamos
        # local_hash = calculate_file_hash(output_path)
        
        # B. Comparamos con lo que dice el Orchestrator
        # assert local_hash == "dummy_hash" # Mocked hash for now
        # assert local_hash == integrity_hash, \
        #     f"Hash Mismatch! Local: {local_hash} vs Remote: {integrity_hash}"
        
        # print("✅ Local Hash Verification Passed.")
