import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Adjust path to import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.scripts.bootstrap_tenant import TenantBootstrapper

class TestTenantBootstrapper(unittest.TestCase):

    @patch('src.scripts.bootstrap_tenant.get_qdrant_client')
    @patch('src.scripts.bootstrap_tenant.SessionLocal')
    @patch('src.scripts.bootstrap_tenant.TextEmbedder')
    @patch('src.scripts.bootstrap_tenant.EntityExtractor')
    @patch('src.scripts.bootstrap_tenant.DataMiningPipeline')
    @patch('src.scripts.bootstrap_tenant.os.listdir')
    @patch('src.scripts.bootstrap_tenant.DocxAtomizer')
    def test_pipeline_trigger(self, mock_atomizer, mock_listdir, mock_pipeline, mock_extractor, mock_embedder, mock_session, mock_qdrant):
        # Setup
        tenant_id = "test-tenant"
        source_dir = "/tmp/docs"
        transcripts_dir = "/tmp/transcripts"
        dataset_output = "/tmp/output"
        
        # Mocking file listing and content extraction
        mock_listdir.return_value = ["test.docx"]
        mock_atomizer_instance = MagicMock()
        mock_atomizer_instance.extract_content.return_value = [{"text": "content", "metadata": {}}]
        mock_atomizer.return_value = mock_atomizer_instance
        
        # Test
        bootstrapper = TenantBootstrapper(
            tenant_id, 
            source_dir, 
            transcripts_dir=transcripts_dir,
            dataset_output=dataset_output
        )
        
        # Mock os.path.exists to return True for the transcripts check
        # We need to selectively mock only the transcript dir check if possible, or just all checks.
        # Since bootstrapper checks `os.path.exists(self.transcripts_dir)`, simply patching it globally is easiest for this unit test.
        with patch('src.scripts.bootstrap_tenant.os.path.exists') as mock_exists:
            mock_exists.return_value = True 
            
            bootstrapper.process_files()
            
            # Verify Pipeline Initialization
            mock_pipeline.assert_called_once_with(
                docs_dir=source_dir,
                transcripts_dir=transcripts_dir,
                output_dir=dataset_output
            )
            
            # Verify Pipeline Run
            mock_pipeline.return_value.run.assert_called_once()
    
    @patch('src.scripts.bootstrap_tenant.get_qdrant_client')
    @patch('src.scripts.bootstrap_tenant.SessionLocal')
    @patch('src.scripts.bootstrap_tenant.TextEmbedder')
    @patch('src.scripts.bootstrap_tenant.EntityExtractor')
    @patch('src.scripts.bootstrap_tenant.DataMiningPipeline')
    @patch('src.scripts.bootstrap_tenant.os.listdir')
    def test_pipeline_skip(self, mock_listdir, mock_pipeline, mock_extractor, mock_embedder, mock_session, mock_qdrant):
         # Setup without transcript dir
        tenant_id = "test-tenant"
        source_dir = "/tmp/docs"
        
        mock_listdir.return_value = []
        
        bootstrapper = TenantBootstrapper(tenant_id, source_dir)
        bootstrapper.process_files()
        
        mock_pipeline.assert_not_called()

if __name__ == '__main__':
    unittest.main()
