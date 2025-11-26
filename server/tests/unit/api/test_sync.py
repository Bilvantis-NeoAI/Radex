"""
Unit tests for sync API endpoints.
Tests API route logic and request/response handling.
"""
import pytest
from unittest.mock import AsyncMock, Mock
from uuid import uuid4
from app.models.provider_item_ref import ProviderItemRef, ProviderType
from app.models.document import Document
from app.models.provider_connection import ProviderConnection
from app.models.folder import Folder
from app.models.user import User
from app.schemas.sharepoint import SharePointItemToSync, SyncedItemInfo
from app.api.sync import _sync_single_item

class TestSyncSingleItem:
    """Test importing a single item from SharePoint/OneDrive"""

    @pytest.mark.asyncio
    async def test_sync_single_item_skipped_if_duplicate_same_connection(self):
        """Skip syncing only if the SAME connection already synced this item"""

        # ---- Arrange ----
        db_mock = Mock()
        connection = Mock(spec=ProviderConnection, id=uuid4())
        folder = Mock(spec=Folder, id=uuid4())
        current_user = Mock(spec=User, id=uuid4())

        graph_service = AsyncMock()
        document_service = AsyncMock()
        embedding_service = AsyncMock()

        sharepoint_item = SharePointItemToSync(
            drive_id="test_drive_id",
            item_id="test_item_id",
            e_tag="test_etag",
        )

        # Pretend item already exists in THIS SAME CONNECTION
        existing_document_id = uuid4()
        existing_ref = ProviderItemRef(
            provider=ProviderType.sharepoint,
            connection_id=connection.id,   # SAME CONNECTION
            document_id=existing_document_id,
            drive_id="test_drive_id",
            item_id="test_item_id",
            etag="old_etag",
            name="old_file.pdf",
        )

        # 1) ProviderItemRef lookup
        # 2) Document lookup
        db_mock.query.return_value.filter.return_value.first.side_effect = [
            existing_ref,
            Mock(
                spec=Document,
                id=existing_document_id,
                filename="existing_file.pdf"
            )
        ]

        # ---- Act ----
        result = await _sync_single_item(
            db=db_mock,
            connection=connection,
            folder=folder,
            item=sharepoint_item,
            current_user=current_user,
            graph_service=graph_service,
            document_service=document_service,
            embedding_service=embedding_service,
        )

        # ---- Assert ----
        assert isinstance(result, SyncedItemInfo)
        assert result.status == "skipped"
        assert result.message == "File already synced"
        assert result.document_id == existing_document_id
        assert result.sharepoint_item_id == "test_item_id"
        assert result.filename == "existing_file.pdf"

        # Ensure no new work was done
        graph_service.get_item_metadata.assert_not_called()
        graph_service.download_file.assert_not_called()
        document_service.create_document_from_file.assert_not_called()
        embedding_service.process_document_embeddings.assert_not_called()

        db_mock.add.assert_not_called()
        db_mock.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_single_item_successfully_when_duplicate_different_connection(self):
        """Even if item already exists, sync again if it was from a DIFFERENT connection

        Note:
            We do not mock an existing ProviderItemRef here because the function
            filters by the current connection_id. If the item was synced under a
            different connection, the query naturally returns None. This simulates
            the real scenario where the same file can be synced by multiple connections.
        """

        # ---- Arrange ----
        db_mock = Mock()

        current_connection = Mock(spec=ProviderConnection, id=uuid4())
        folder = Mock(spec=Folder, id=uuid4())
        current_user = Mock(spec=User, id=uuid4())

        graph_service = AsyncMock()
        document_service = AsyncMock()
        embedding_service = AsyncMock()

        sharepoint_item = SharePointItemToSync(
            drive_id="test_drive_id",
            item_id="test_item_id",
            e_tag="new_etag",
        )

        # First DB lookup: returns existing ref, but irrelevant because connection_id doesn't match
        db_mock.query.return_value.filter.return_value.first.side_effect = [
            None,
            None  # No document match on second query
        ]

        # Mock services for actual sync
        mock_metadata = {"name": "file.pdf", "size": 123}
        graph_service.get_item_metadata.return_value = mock_metadata
        graph_service.download_file.return_value = b"data"

        new_doc_id = uuid4()
        new_doc = Mock(spec=Document, id=new_doc_id, filename="file.pdf")
        document_service.create_document_from_file.return_value = new_doc

        # ---- Act ----
        result = await _sync_single_item(
            db=db_mock,
            connection=current_connection,
            folder=folder,
            item=sharepoint_item,
            current_user=current_user,
            graph_service=graph_service,
            document_service=document_service,
            embedding_service=embedding_service,
        )

        # ---- Assert ----
        assert result.status == "success"
        assert result.message == "File synced successfully"
        assert result.document_id == new_doc_id
        assert result.filename == "file.pdf"

        graph_service.get_item_metadata.assert_called_once()
        graph_service.download_file.assert_called_once()
        document_service.create_document_from_file.assert_called_once()
        embedding_service.process_document_embeddings.assert_called_once_with(new_doc_id)

        db_mock.add.assert_called_once()
        db_mock.commit.assert_called_once()