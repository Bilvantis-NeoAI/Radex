"""
Confluence Provider Pydantic Schemas

Data models for Confluence OAuth, content browsing, and sync operations.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID


# ============================================================================
# OAuth Flow Schemas
# ============================================================================

class ConfluenceAuthStartResponse(BaseModel):
    """Response when starting Confluence OAuth flow."""
    auth_url: str = Field(..., description="URL to redirect user to for authorization")
    state: str = Field(..., description="CSRF protection state token")


class ConfluenceAuthCallbackRequest(BaseModel):
    """Request payload from OAuth callback."""
    code: str = Field(..., description="Authorization code from Atlassian")
    state: str = Field(..., description="State token for CSRF validation")


class ConfluenceAuthCallbackResponse(BaseModel):
    """Response after successful OAuth callback."""
    connection_id: UUID = Field(..., description="Created connection ID")
    cloud_id: str = Field(..., description="Atlassian cloud ID")
    created_at: datetime


# ============================================================================
# Content Browsing Schemas
# ============================================================================

class ConfluenceSpace(BaseModel):
    """Confluence space information."""
    id: str = Field(..., description="Space ID")
    key: str = Field(..., description="Space key")
    name: str = Field(..., description="Space name")
    type: str = Field(..., description="Space type (global, personal)")
    status: Optional[str] = Field(None, description="Space status")

    class Config:
        from_attributes = True


class ConfluenceSpacesResponse(BaseModel):
    """Response containing list of spaces."""
    spaces: List[ConfluenceSpace]
    next_link: Optional[str] = Field(None, description="Link to next page of results")


class ConfluencePage(BaseModel):
    """Confluence page/content information."""
    id: str = Field(..., description="Content ID")
    type: str = Field(..., description="Content type (page, blogpost, attachment)")
    status: str = Field(..., description="Content status (current, archived)")
    title: str = Field(..., description="Page title")
    space_key: str = Field(..., description="Space key this content belongs to")
    version: Optional[int] = Field(None, description="Content version number")
    last_modified: Optional[datetime] = Field(None, description="Last modified timestamp")
    web_url: Optional[str] = Field(None, description="Web URL to view content")
    is_synced: bool = Field(False, description="Whether this page has been synced to RADEX")

    class Config:
        from_attributes = True


class ConfluencePagesResponse(BaseModel):
    """Response containing list of pages."""
    pages: List[ConfluencePage]
    next_link: Optional[str] = Field(None, description="Link to next page of results")


class ConfluenceSearchResult(BaseModel):
    """Search result item."""
    content: ConfluencePage
    excerpt: Optional[str] = Field(None, description="Search excerpt/snippet")

    class Config:
        from_attributes = True


class ConfluenceSearchResponse(BaseModel):
    """Response containing search results."""
    results: List[ConfluenceSearchResult]
    total_size: int = Field(..., description="Total number of results")
    next_link: Optional[str] = Field(None, description="Link to next page of results")


# ============================================================================
# Sync/Import Schemas
# ============================================================================

class ConfluenceItemToSync(BaseModel):
    """Item to sync from Confluence."""
    space_key: str = Field(..., description="Confluence space key")
    content_id: str = Field(..., description="Content/page ID")
    version: Optional[int] = Field(None, description="Content version")


class ConfluenceSyncImportRequest(BaseModel):
    """Request to import Confluence pages."""
    connection_id: UUID = Field(..., description="Confluence connection ID")
    folder_id: UUID = Field(..., description="Target RADEX folder ID")
    items: List[ConfluenceItemToSync] = Field(..., description="Pages to import")


# Note: Sync import response reuses the generic SyncImportResponse from sharepoint.py
# This allows unified response format across providers
