"""
File Sync/Import API Endpoints

Handles importing content from external providers (SharePoint/OneDrive/Confluence) into RADEX.
Content is downloaded to temp storage, uploaded to MinIO, and processed through
the existing document ingestion pipeline.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import tempfile
import os
from pathlib import Path

from app.core.dependencies import get_db, get_current_active_user
from app.models.user import User
from app.models.folder import Folder
from app.models.document import Document
from app.models.provider_connection import ProviderConnection
from app.models.provider_item_ref import ProviderItemRef, ProviderType
from app.schemas.sharepoint import (
    SyncImportRequest,
    SyncImportResponse,
    SyncedItemInfo,
    SharePointItemToSync,
)
from app.schemas.confluence import ConfluenceSyncImportRequest, ConfluenceItemToSync
from app.services.microsoft_graph_service import MicrosoftGraphService
from app.services.atlassian_confluence_service import AtlassianConfluenceService
from app.services.document_service import DocumentService
from app.services.permission_service import PermissionService
from app.core.exceptions import BadRequestException, NotFoundException, PermissionDeniedException
from app.config import settings

router = APIRouter(
    tags=["File Sync"],
)


@router.post("/import", response_model=SyncImportResponse)
async def import_from_sharepoint(
    request: SyncImportRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Import files from SharePoint/OneDrive into RADEX.

    **Process:**
    1. Downloads files from SharePoint to temporary storage
    2. Uploads to MinIO using existing document service
    3. Triggers embedding generation pipeline
    4. Stores provider references for idempotency
    5. Cleans up temporary files

    **Idempotency:** Files already synced (based on drive_id + item_id) are skipped.

    Args:
        request: Sync request with connection ID, folder ID, and items to sync

    Returns:
        Sync results with counts and per-item status
    """
    # Validate connection belongs to user
    connection = (
        db.query(ProviderConnection)
        .filter(
            ProviderConnection.id == request.connection_id,
            ProviderConnection.user_id == current_user.id,
        )
        .first()
    )

    if not connection:
        raise NotFoundException("Connection not found or access denied")

    # Validate target folder exists and user has write permission
    folder = db.query(Folder).filter(Folder.id == request.folder_id).first()
    if not folder:
        raise NotFoundException("Target folder not found")

    permission_service = PermissionService(db)
    if not permission_service.check_folder_access(current_user.id, folder.id, "write"):
        raise PermissionDeniedException("You don't have write access to this folder")

    # Initialize services
    graph_service = MicrosoftGraphService(db)
    document_service = DocumentService(db)

    # Track results
    results: List[SyncedItemInfo] = []
    succeeded = 0
    skipped = 0
    failed = 0

    # Process each item
    for item in request.items:
        try:
            result = await _sync_single_item(
                db=db,
                connection=connection,
                folder=folder,
                item=item,
                current_user=current_user,
                graph_service=graph_service,
                document_service=document_service,
            )

            results.append(result)

            if result.status == "success":
                succeeded += 1
            elif result.status == "skipped":
                skipped += 1
            else:
                failed += 1

        except Exception as e:
            # Log error and continue with next item
            results.append(
                SyncedItemInfo(
                    sharepoint_item_id=item.item_id,
                    document_id=UUID("00000000-0000-0000-0000-000000000000"),  # Placeholder
                    filename="Unknown",
                    status="failed",
                    message=str(e),
                )
            )
            failed += 1

    return SyncImportResponse(
        total=len(request.items),
        succeeded=succeeded,
        skipped=skipped,
        failed=failed,
        results=results,
    )


async def _sync_single_item(
    db: Session,
    connection: ProviderConnection,
    folder: Folder,
    item: SharePointItemToSync,
    current_user: User,
    graph_service: MicrosoftGraphService,
    document_service: DocumentService,
) -> SyncedItemInfo:
    """
    Sync a single file from SharePoint/OneDrive.

    Args:
        db: Database session
        connection: Provider connection
        folder: Target RADEX folder
        item: SharePoint item to sync
        current_user: Current user
        graph_service: Microsoft Graph service instance
        document_service: Document service instance

    Returns:
        SyncedItemInfo with result

    Raises:
        Exception: If sync fails (caught by caller)
    """
    # Check if item is already synced (idempotency)
    existing_ref = (
        db.query(ProviderItemRef)
        .filter(
            ProviderItemRef.provider == ProviderType.sharepoint,
            ProviderItemRef.drive_id == item.drive_id,
            ProviderItemRef.item_id == item.item_id,
        )
        .first()
    )

    if existing_ref:
        # Already synced - return existing document info
        document = db.query(Document).filter(Document.id == existing_ref.document_id).first()
        return SyncedItemInfo(
            sharepoint_item_id=item.item_id,
            document_id=existing_ref.document_id,
            filename=document.filename if document else "Unknown",
            status="skipped",
            message="File already synced",
        )

    # Get item metadata from SharePoint
    metadata = await graph_service.get_item_metadata(
        connection, item.drive_id, item.item_id
    )

    filename = metadata.get("name", "unnamed_file")

    # Check if it's a folder (we only sync files)
    if "folder" in metadata:
        return SyncedItemInfo(
            sharepoint_item_id=item.item_id,
            document_id=UUID("00000000-0000-0000-0000-000000000000"),
            filename=filename,
            status="skipped",
            message="Folders are not supported for sync (files only)",
        )

    # Download file content to temporary file
    file_content = await graph_service.download_file(
        connection, item.drive_id, item.item_id
    )

    # Use context manager for automatic cleanup
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save to temp file
        temp_file_path = os.path.join(temp_dir, filename)
        with open(temp_file_path, "wb") as f:
            f.write(file_content)

        # Upload to MinIO and create document record using existing service
        # This reuses the existing upload functionality
        document = await document_service.create_document_from_file(
            folder_id=folder.id,
            file_path=temp_file_path,
            filename=filename,
            file_size=len(file_content),
            uploaded_by=current_user.id,
        )

    # Create provider reference for idempotency
    provider_ref = ProviderItemRef(
        provider=ProviderType.sharepoint,
        connection_id=connection.id,
        document_id=document.id,
        drive_id=item.drive_id,
        item_id=item.item_id,
        etag=item.e_tag,
        name=filename,
        size=len(file_content),
        last_modified=metadata.get("lastModifiedDateTime"),
        content_hash=metadata.get("file", {}).get("hashes", {}).get("quickXorHash"),
    )
    db.add(provider_ref)
    db.commit()

    return SyncedItemInfo(
        sharepoint_item_id=item.item_id,
        document_id=document.id,
        filename=filename,
        status="success",
        message="File synced successfully",
    )


# ============================================================================
# Confluence Import Endpoint
# ============================================================================

@router.post("/import/confluence", response_model=SyncImportResponse)
async def import_from_confluence(
    request: ConfluenceSyncImportRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Import pages from Confluence into RADEX.

    **Process:**
    1. Downloads pages from Confluence as HTML
    2. Uploads to MinIO using existing document service
    3. Triggers embedding generation pipeline
    4. Stores provider references for idempotency
    5. Cleans up temporary files

    **Idempotency:** Pages already synced (based on space_key + content_id) are skipped.

    Args:
        request: Sync request with connection ID, folder ID, and pages to sync

    Returns:
        Sync results with counts and per-item status
    """
    # Validate connection belongs to user
    connection = (
        db.query(ProviderConnection)
        .filter(
            ProviderConnection.id == request.connection_id,
            ProviderConnection.user_id == current_user.id,
        )
        .first()
    )

    if not connection:
        raise NotFoundException("Connection not found or access denied")

    # Validate connection is for Confluence
    if connection.provider != ProviderType.confluence:
        raise BadRequestException("Connection is not a Confluence connection")

    # Validate target folder exists and user has write permission
    folder = db.query(Folder).filter(Folder.id == request.folder_id).first()
    if not folder:
        raise NotFoundException("Target folder not found")

    permission_service = PermissionService(db)
    if not permission_service.check_folder_access(current_user.id, folder.id, "write"):
        raise PermissionDeniedException("You don't have write access to this folder")

    # Initialize services
    confluence_service = AtlassianConfluenceService(db)
    document_service = DocumentService(db)

    # Track results
    results: List[SyncedItemInfo] = []
    succeeded = 0
    skipped = 0
    failed = 0

    # Process each item
    for item in request.items:
        try:
            result = await _sync_single_confluence_page(
                db=db,
                connection=connection,
                folder=folder,
                item=item,
                current_user=current_user,
                confluence_service=confluence_service,
                document_service=document_service,
            )

            results.append(result)

            if result.status == "success":
                succeeded += 1
            elif result.status == "skipped":
                skipped += 1
            else:
                failed += 1

        except Exception as e:
            # Log error and continue with next item
            results.append(
                SyncedItemInfo(
                    sharepoint_item_id=item.content_id,
                    document_id=UUID("00000000-0000-0000-0000-000000000000"),  # Placeholder
                    filename="Unknown",
                    status="failed",
                    message=str(e),
                )
            )
            failed += 1

    return SyncImportResponse(
        total=len(request.items),
        succeeded=succeeded,
        skipped=skipped,
        failed=failed,
        results=results,
    )


async def _sync_single_confluence_page(
    db: Session,
    connection: ProviderConnection,
    folder: Folder,
    item: ConfluenceItemToSync,
    current_user: User,
    confluence_service: AtlassianConfluenceService,
    document_service: DocumentService,
) -> SyncedItemInfo:
    """
    Sync a single Confluence page.

    Args:
        db: Database session
        connection: Provider connection
        folder: Target RADEX folder
        item: Confluence page to sync
        current_user: Current user
        confluence_service: Confluence service instance
        document_service: Document service instance

    Returns:
        SyncedItemInfo with result

    Raises:
        Exception: If sync fails (caught by caller)
    """
    # Check if page is already synced (idempotency)
    existing_ref = (
        db.query(ProviderItemRef)
        .filter(
            ProviderItemRef.provider == ProviderType.confluence,
            ProviderItemRef.drive_id == item.space_key,
            ProviderItemRef.item_id == item.content_id,
        )
        .first()
    )

    if existing_ref:
        # Already synced - return existing document info
        document = db.query(Document).filter(Document.id == existing_ref.document_id).first()
        return SyncedItemInfo(
            sharepoint_item_id=item.content_id,
            document_id=existing_ref.document_id,
            filename=document.filename if document else "Unknown",
            status="skipped",
            message="Page already synced",
        )

    # Get page metadata from Confluence
    metadata = await confluence_service.get_content(connection, item.content_id)

    page_title = metadata.get("title", "Untitled Page")
    filename = f"{page_title}.html"

    # Download page content as HTML
    page_content = await confluence_service.get_content_as_export(
        connection, item.content_id, "export_view"
    )

    # Use context manager for automatic cleanup
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save to temp file
        temp_file_path = os.path.join(temp_dir, filename)
        with open(temp_file_path, "wb") as f:
            f.write(page_content)

        # Upload to MinIO and create document record using existing service
        document = await document_service.create_document_from_file(
            folder_id=folder.id,
            file_path=temp_file_path,
            filename=filename,
            file_size=len(page_content),
            uploaded_by=current_user.id,
        )

    # Create provider reference for idempotency
    version_data = metadata.get("version", {})
    provider_ref = ProviderItemRef(
        provider=ProviderType.confluence,
        connection_id=connection.id,
        document_id=document.id,
        drive_id=item.space_key,
        item_id=item.content_id,
        etag=f"v{version_data.get('number', 1)}",
        name=page_title,
        size=len(page_content),
        last_modified=version_data.get("when"),
        content_hash=None,  # Confluence doesn't provide content hash
    )
    db.add(provider_ref)
    db.commit()

    return SyncedItemInfo(
        sharepoint_item_id=item.content_id,
        document_id=document.id,
        filename=filename,
        status="success",
        message="Page synced successfully",
    )
