import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from src.core.mapping.sync_worker import SyncManager
from src.db.models import ZoneMapping

class TestSyncManager:
    
    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.update_zone_mappings.return_value = True
        return client

    def test_sync_success_updates_timestamp(self, mock_db, mock_client):
        """DoD: Si el cliente retorna True, se actualiza synced_at y se hace commit."""
        manager = SyncManager(mock_db, mock_client)
        tenant_id = "test_tenant"

        # Mock de datos pendientes
        record1 = ZoneMapping(id="1", template_id="t1", zone_id="HEADER", is_locked=True, synced_at=None)
        
        # Configurar query mock
        mock_db.query.return_value.filter.return_value.all.return_value = [record1]

        # Ejecutar
        count = manager.sync_tenant_mappings(tenant_id)

        # Verificaciones
        assert count == 1
        mock_client.update_zone_mappings.assert_called_once()
        assert record1.synced_at is not None  # Debe tener fecha actual
        mock_db.commit.assert_called_once()

    def test_sync_no_pending_records(self, mock_db, mock_client):
        """DoD: Si no hay registros, no se llama al cliente."""
        manager = SyncManager(mock_db, mock_client)
        
        # Configurar query mock vacía
        mock_db.query.return_value.filter.return_value.all.return_value = []

        count = manager.sync_tenant_mappings("test_tenant")

        assert count == 0
        mock_client.update_zone_mappings.assert_not_called()
        mock_db.commit.assert_not_called()

    def test_sync_failure_rollbacks(self, mock_db, mock_client):
        """DoD: Si el cliente falla, se hace rollback y no se actualiza fecha."""
        manager = SyncManager(mock_db, mock_client)
        
        # Simular fallo en cliente
        mock_client.update_zone_mappings.side_effect = Exception("Service Down")
        
        record1 = ZoneMapping(id="1", is_locked=True, synced_at=None)
        mock_db.query.return_value.filter.return_value.all.return_value = [record1]

        with pytest.raises(Exception):
            manager.sync_tenant_mappings("test_tenant")

        mock_db.rollback.assert_called_once()
        # synced_at debe seguir siendo None (o lo que tenía antes)
        assert record1.synced_at is None