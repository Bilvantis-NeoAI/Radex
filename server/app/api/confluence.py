"""
Confluence Provider API Endpoints

Implements OAuth flow, content browsing, and sync functionality for Atlassian Confluence integration.
All endpoints require user authentication. No tokens or secrets are exposed to the frontend.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.core.dependencies import get_db, get_current_active_user
from app.models.user import User
from app.models.provider_connection import ProviderConnection, ProviderType
from app.models.provider_item_ref import ProviderItemRef
from app.schemas.confluence import (
    ConfluenceAuthStartResponse,
    ConfluenceAuthCallbackRequest,
    ConfluenceAuthCallbackResponse,
    ConfluenceSpace,
    ConfluenceSpacesResponse,
    ConfluencePage,
    ConfluencePagesResponse,
    ConfluenceSearchResponse,
    ConfluenceSearchResult,
)
from app.schemas.sharepoint import (
    ProviderConnectionInfo,
    ProviderConnectionsResponse,
)
from app.services.atlassian_confluence_service import (
    AtlassianConfluenceService,
    generate_state_token,
)
from app.services.token_encryption_service import get_token_encryption_service
from app.core.exceptions import BadRequestException, NotFoundException
from app.config import settings

router = APIRouter(
    tags=["Confluence Provider"],
)

# In-memory state storage (in production, use Redis with TTL)
# Maps state -> user_id for OAuth CSRF protection
_oauth_states: dict[str, UUID] = {}


def check_confluence_enabled():
    """
    Dependency to check if Confluence provider is enabled.

    Raises:
        HTTPException: If Confluence provider is not enabled
    """
    if not settings.enable_confluence_provider:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Confluence provider is not enabled. Set ENABLE_CONFLUENCE_PROVIDER=true",
        )


# ============================================================================
# OAuth Flow Endpoints
# ============================================================================

@router.post("/auth/start", response_model=ConfluenceAuthStartResponse)
async def start_oauth_flow(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    _enabled: None = Depends(check_confluence_enabled),
):
    """
    Start OAuth flow for Confluence access.

    Generates authorization URL and secure state token. Frontend should
    redirect user to the returned auth_url.

    **Security**: State token is stored server-side for CSRF protection.
    """
    confluence_service = AtlassianConfluenceService(db)

    # Generate secure state token
    state = generate_state_token()

    # Store state with user ID for validation in callback
    _oauth_states[state] = current_user.id

    # Generate Atlassian authorization URL
    auth_url = confluence_service.generate_auth_url(state)

    return ConfluenceAuthStartResponse(auth_url=auth_url, state=state)


@router.post("/auth/callback", response_model=ConfluenceAuthCallbackResponse)
async def oauth_callback(
    callback_data: ConfluenceAuthCallbackRequest,
    db: Session = Depends(get_db),
    _enabled: None = Depends(check_confluence_enabled),
):
    """
    Handle OAuth callback from Atlassian.

    Exchanges authorization code for tokens, encrypts them, and stores
    in database. Returns connection_id for subsequent API calls.

    **Security**:
    - Validates state parameter against stored value
    - Tokens are encrypted before database storage
    - Returns only connection_id, never tokens
    """
    # Validate state parameter
    user_id = _oauth_states.pop(callback_data.state, None)
    if not user_id:
        raise BadRequestException("Invalid or expired state parameter")

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("User not found")

    confluence_service = AtlassianConfluenceService(db)

    # Exchange code for tokens
    token_data, cloud_id = await confluence_service.exchange_code_for_tokens(
        callback_data.code
    )

    # Encrypt tokens
    encryption_service = get_token_encryption_service()
    encrypted_tokens = encryption_service.encrypt_tokens(token_data)

    # Check if connection already exists for this user+cloud_id
    existing_connection = (
        db.query(ProviderConnection)
        .filter(
            ProviderConnection.provider == ProviderType.confluence,
            ProviderConnection.user_id == user_id,
            ProviderConnection.tenant_id == cloud_id,
        )
        .first()
    )

    if existing_connection:
        # Update existing connection with new tokens
        existing_connection.encrypted_tokens = encrypted_tokens
        db.commit()
        db.refresh(existing_connection)
        connection = existing_connection
    else:
        # Create new connection
        connection = ProviderConnection(
            provider=ProviderType.confluence,
            user_id=user_id,
            tenant_id=cloud_id,
            encrypted_tokens=encrypted_tokens,
        )
        db.add(connection)
        db.commit()
        db.refresh(connection)

    return ConfluenceAuthCallbackResponse(
        connection_id=connection.id,
        cloud_id=connection.tenant_id,
        created_at=connection.created_at,
    )


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(
    connection_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    _enabled: None = Depends(check_confluence_enabled),
):
    """
    Disconnect and delete a Confluence provider connection.

    Removes encrypted tokens from database. User will need to re-authorize
    to access Confluence again.

    **Security**: Users can only delete their own connections.
    """
    connection = (
        db.query(ProviderConnection)
        .filter(
            ProviderConnection.id == connection_id,
            ProviderConnection.user_id == current_user.id,
        )
        .first()
    )

    if not connection:
        raise NotFoundException("Connection not found")

    db.delete(connection)
    db.commit()


@router.get("/connections", response_model=ProviderConnectionsResponse)
async def list_connections(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    _enabled: None = Depends(check_confluence_enabled),
):
    """
    List user's Confluence provider connections.

    Returns:
        List of connections (without tokens)
    """
    connections = (
        db.query(ProviderConnection)
        .filter(
            ProviderConnection.provider == ProviderType.confluence,
            ProviderConnection.user_id == current_user.id,
        )
        .all()
    )

    return ProviderConnectionsResponse(
        connections=[
            ProviderConnectionInfo(
                id=conn.id,
                provider=conn.provider.value,
                tenant_id=conn.tenant_id,
                created_at=conn.created_at,
                updated_at=conn.updated_at,
            )
            for conn in connections
        ]
    )


# ============================================================================
# Confluence Space Browsing Endpoints
# ============================================================================

@router.get("/{connection_id}/spaces", response_model=ConfluenceSpacesResponse)
async def list_spaces(
    connection_id: UUID,
    start: int = Query(0, ge=0, description="Pagination start index"),
    limit: int = Query(25, ge=1, le=100, description="Number of results per page"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    _enabled: None = Depends(check_confluence_enabled),
):
    """
    List Confluence spaces.

    Args:
        connection_id: Provider connection ID
        start: Pagination start index
        limit: Number of results per page

    Returns:
        List of spaces
    """
    connection = _get_user_connection(db, connection_id, current_user.id)
    confluence_service = AtlassianConfluenceService(db)

    response_data = await confluence_service.get_spaces(connection, start, limit)

    spaces = [
        ConfluenceSpace(
            id=space["id"],
            key=space["key"],
            name=space.get("name", ""),
            type=space.get("type", "global"),
            status=space.get("status"),
        )
        for space in response_data.get("results", [])
    ]

    # Get next link if available
    next_link = None
    if "_links" in response_data and "next" in response_data["_links"]:
        next_link = response_data["_links"]["next"]

    return ConfluenceSpacesResponse(spaces=spaces, next_link=next_link)


@router.get("/{connection_id}/spaces/{space_key}/pages", response_model=ConfluencePagesResponse)
async def list_space_pages(
    connection_id: UUID,
    space_key: str,
    start: int = Query(0, ge=0, description="Pagination start index"),
    limit: int = Query(25, ge=1, le=100, description="Number of results per page"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    _enabled: None = Depends(check_confluence_enabled),
):
    """
    List pages in a Confluence space.

    Args:
        connection_id: Provider connection ID
        space_key: Space key
        start: Pagination start index
        limit: Number of results per page

    Returns:
        List of pages with sync status
    """
    connection = _get_user_connection(db, connection_id, current_user.id)
    confluence_service = AtlassianConfluenceService(db)

    response_data = await confluence_service.get_space_content(
        connection, space_key, "page", start, limit
    )

    # Get list of already synced pages for this space
    synced_page_ids = set(
        db.query(ProviderItemRef.item_id)
        .filter(
            ProviderItemRef.connection_id == connection_id,
            ProviderItemRef.drive_id == space_key,
        )
        .all()
    )
    synced_page_ids = {page_id[0] for page_id in synced_page_ids}

    pages = []
    for page_data in response_data.get("results", []):
        # Parse timestamp
        last_modified = None
        version_data = page_data.get("version", {})
        if "when" in version_data:
            try:
                from dateutil import parser
                last_modified = parser.isoparse(version_data["when"])
            except:
                pass

        pages.append(
            ConfluencePage(
                id=page_data["id"],
                type=page_data.get("type", "page"),
                status=page_data.get("status", "current"),
                title=page_data.get("title", "Untitled"),
                space_key=space_key,
                version=version_data.get("number"),
                last_modified=last_modified,
                web_url=page_data.get("_links", {}).get("webui"),
                is_synced=page_data["id"] in synced_page_ids,
            )
        )

    # Get next link if available
    next_link = None
    if "_links" in response_data and "next" in response_data["_links"]:
        next_link = response_data["_links"]["next"]

    return ConfluencePagesResponse(pages=pages, next_link=next_link)


@router.get("/{connection_id}/search", response_model=ConfluenceSearchResponse)
async def search_content(
    connection_id: UUID,
    query: str = Query(..., min_length=1, max_length=500, description="Search query"),
    start: int = Query(0, ge=0, description="Pagination start index"),
    limit: int = Query(25, ge=1, le=100, description="Number of results per page"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    _enabled: None = Depends(check_confluence_enabled),
):
    """
    Search for Confluence content using CQL.

    Args:
        connection_id: Provider connection ID
        query: Search query string (will be converted to CQL)
        start: Pagination start index
        limit: Number of results per page

    Returns:
        Search results with sync status
    """
    connection = _get_user_connection(db, connection_id, current_user.id)
    confluence_service = AtlassianConfluenceService(db)

    # Build CQL query - search in title and text
    cql = f'type=page AND (title ~ "{query}" OR text ~ "{query}")'

    response_data = await confluence_service.search_content(
        connection, cql, start, limit
    )

    results = []
    for result_data in response_data.get("results", []):
        content_data = result_data.get("content", result_data)
        space_data = content_data.get("space", {})
        space_key = space_data.get("key", "")

        # Check if synced
        is_synced = (
            db.query(ProviderItemRef)
            .filter(
                ProviderItemRef.connection_id == connection_id,
                ProviderItemRef.drive_id == space_key,
                ProviderItemRef.item_id == content_data["id"],
            )
            .first()
        ) is not None

        # Parse timestamp
        last_modified = None
        version_data = content_data.get("version", {})
        if "when" in version_data:
            try:
                from dateutil import parser
                last_modified = parser.isoparse(version_data["when"])
            except:
                pass

        page = ConfluencePage(
            id=content_data["id"],
            type=content_data.get("type", "page"),
            status=content_data.get("status", "current"),
            title=content_data.get("title", "Untitled"),
            space_key=space_key,
            version=version_data.get("number"),
            last_modified=last_modified,
            web_url=content_data.get("_links", {}).get("webui"),
            is_synced=is_synced,
        )

        results.append(
            ConfluenceSearchResult(
                content=page,
                excerpt=result_data.get("excerpt"),
            )
        )

    # Get next link if available
    next_link = None
    if "_links" in response_data and "next" in response_data["_links"]:
        next_link = response_data["_links"]["next"]

    return ConfluenceSearchResponse(
        results=results,
        total_size=response_data.get("totalSize", len(results)),
        next_link=next_link,
    )


# ============================================================================
# Helper Functions
# ============================================================================

def _get_user_connection(
    db: Session, connection_id: UUID, user_id: UUID
) -> ProviderConnection:
    """
    Get and validate provider connection for the current user.

    Args:
        db: Database session
        connection_id: Connection ID
        user_id: Current user ID

    Returns:
        ProviderConnection

    Raises:
        NotFoundException: If connection not found or doesn't belong to user
    """
    connection = (
        db.query(ProviderConnection)
        .filter(
            ProviderConnection.id == connection_id,
            ProviderConnection.user_id == user_id,
        )
        .first()
    )

    if not connection:
        raise NotFoundException("Connection not found or access denied")

    return connection
