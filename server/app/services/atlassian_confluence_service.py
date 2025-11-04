"""
Atlassian Confluence API Integration Service

Handles OAuth token management and Confluence Cloud API calls for page/space access.
All API calls go through this service to ensure proper token refresh and error handling.
"""

import httpx
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlencode
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
    PermissionDeniedException,
)
from app.models.provider_connection import ProviderConnection, ProviderType
from app.services.token_encryption_service import get_token_encryption_service


class AtlassianConfluenceService:
    """
    Service for interacting with Atlassian Confluence Cloud API.

    Handles OAuth flow, token refresh, and API requests to Confluence
    for space and page access.
    """

    OAUTH_AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
    OAUTH_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
    ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"

    # OAuth scopes for Confluence access
    REQUIRED_SCOPES = [
        "read:confluence-content.all",  # Read all Confluence content
        "read:confluence-space.summary",  # Read space information
        "offline_access",  # For refresh tokens
    ]

    def __init__(self, db: Session):
        """
        Initialize Confluence service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.client_id = settings.confluence_client_id
        self.client_secret = settings.confluence_client_secret
        self.redirect_uri = settings.confluence_redirect_uri

        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            raise ValueError(
                "Confluence provider not configured. Set CONFLUENCE_CLIENT_ID, "
                "CONFLUENCE_CLIENT_SECRET, and CONFLUENCE_REDIRECT_URI environment variables."
            )

    # ========================================================================
    # OAuth Flow
    # ========================================================================

    def generate_auth_url(self, state: str) -> str:
        """
        Generate Atlassian OAuth authorization URL.

        Args:
            state: CSRF protection state parameter

        Returns:
            Authorization URL to redirect user to
        """
        params = {
            "audience": "api.atlassian.com",
            "client_id": self.client_id,
            "scope": " ".join(self.REQUIRED_SCOPES),
            "redirect_uri": self.redirect_uri,
            "state": state,
            "response_type": "code",
            "prompt": "consent",
        }
        return f"{self.OAUTH_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code_for_tokens(
        self, code: str
    ) -> Tuple[Dict[str, Any], str]:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Tuple of (token_data dict, cloud_id string)

        Raises:
            BadRequestException: If token exchange fails
        """
        token_data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }

        async with httpx.AsyncClient() as client:
            # Exchange code for tokens
            response = await client.post(
                self.OAUTH_TOKEN_URL,
                json=token_data,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                raise BadRequestException(
                    f"Failed to exchange authorization code: {response.text}"
                )

            tokens = response.json()

            # Get accessible resources to find cloud ID
            cloud_id = await self._get_cloud_id(tokens["access_token"])

            # Prepare token data for encryption
            token_info = {
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token"),
                "expires_at": (
                    datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
                ).isoformat(),
                "scope": tokens.get("scope"),
            }

            return token_info, cloud_id

    async def _get_cloud_id(self, access_token: str) -> str:
        """
        Get Atlassian cloud ID from accessible resources.

        Args:
            access_token: OAuth access token

        Returns:
            Cloud ID of the first accessible Confluence instance

        Raises:
            NotFoundException: If no accessible Confluence instances found
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.ACCESSIBLE_RESOURCES_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code != 200:
                raise BadRequestException(
                    f"Failed to get accessible resources: {response.text}"
                )

            resources = response.json()

            if not resources or len(resources) == 0:
                raise NotFoundException("No accessible Atlassian sites found")

            # Use the first accessible resource
            return resources[0]["id"]

    async def refresh_access_token(
        self, connection: ProviderConnection
    ) -> Dict[str, Any]:
        """
        Refresh expired access token using refresh token.

        Args:
            connection: Provider connection with encrypted tokens

        Returns:
            New token data dict

        Raises:
            BadRequestException: If token refresh fails
        """
        encryption_service = get_token_encryption_service()
        token_data = encryption_service.decrypt_tokens(connection.encrypted_tokens)

        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            raise BadRequestException("No refresh token available")

        refresh_data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.OAUTH_TOKEN_URL,
                json=refresh_data,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                raise BadRequestException(
                    f"Failed to refresh access token: {response.text}"
                )

            tokens = response.json()

            # Update token data
            new_token_data = {
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token", refresh_token),
                "expires_at": (
                    datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600))
                ).isoformat(),
                "scope": tokens.get("scope"),
            }

            # Update database
            encrypted_tokens = encryption_service.encrypt_tokens(new_token_data)
            connection.encrypted_tokens = encrypted_tokens
            self.db.commit()

            return new_token_data

    async def get_valid_token(self, connection: ProviderConnection) -> str:
        """
        Get valid access token, refreshing if necessary.

        Args:
            connection: Provider connection

        Returns:
            Valid access token

        Raises:
            BadRequestException: If unable to get valid token
        """
        encryption_service = get_token_encryption_service()
        token_data = encryption_service.decrypt_tokens(connection.encrypted_tokens)

        expires_at_str = token_data.get("expires_at")
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
            # Refresh if token expires in less than 5 minutes
            if expires_at < datetime.utcnow() + timedelta(minutes=5):
                token_data = await self.refresh_access_token(connection)

        return token_data["access_token"]

    # ========================================================================
    # Confluence API Calls
    # ========================================================================

    def _get_api_base_url(self, cloud_id: str) -> str:
        """Get Confluence API base URL for a specific cloud instance."""
        return f"https://api.atlassian.com/ex/confluence/{cloud_id}/wiki/rest/api"

    async def _make_api_request(
        self,
        connection: ProviderConnection,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated API request to Confluence.

        Args:
            connection: Provider connection
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Optional query parameters

        Returns:
            Response JSON data

        Raises:
            NotFoundException: If resource not found
            PermissionDeniedException: If access denied
            BadRequestException: For other errors
        """
        access_token = await self.get_valid_token(connection)
        base_url = self._get_api_base_url(connection.tenant_id)  # tenant_id stores cloud_id

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                f"{base_url}{endpoint}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                params=params,
            )

            if response.status_code == 404:
                raise NotFoundException("Resource not found")
            elif response.status_code == 403:
                raise PermissionDeniedException("Access denied to resource")
            elif response.status_code >= 400:
                raise BadRequestException(
                    f"API request failed: {response.status_code} - {response.text}"
                )

            return response.json()

    # ========================================================================
    # Space Operations
    # ========================================================================

    async def get_spaces(
        self,
        connection: ProviderConnection,
        start: int = 0,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """
        Get list of Confluence spaces.

        Args:
            connection: Provider connection
            start: Pagination start index
            limit: Number of results per page

        Returns:
            Response with spaces list
        """
        return await self._make_api_request(
            connection,
            "GET",
            "/space",
            params={"start": start, "limit": limit},
        )

    async def get_space(
        self, connection: ProviderConnection, space_key: str
    ) -> Dict[str, Any]:
        """
        Get specific space details.

        Args:
            connection: Provider connection
            space_key: Space key

        Returns:
            Space details
        """
        return await self._make_api_request(
            connection, "GET", f"/space/{space_key}"
        )

    # ========================================================================
    # Content/Page Operations
    # ========================================================================

    async def get_space_content(
        self,
        connection: ProviderConnection,
        space_key: str,
        content_type: str = "page",
        start: int = 0,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """
        Get content (pages) from a space.

        Args:
            connection: Provider connection
            space_key: Space key
            content_type: Content type (page, blogpost, etc.)
            start: Pagination start index
            limit: Number of results per page

        Returns:
            Response with content list
        """
        return await self._make_api_request(
            connection,
            "GET",
            "/content",
            params={
                "spaceKey": space_key,
                "type": content_type,
                "start": start,
                "limit": limit,
                "expand": "version,space",
            },
        )

    async def get_content(
        self, connection: ProviderConnection, content_id: str
    ) -> Dict[str, Any]:
        """
        Get specific content/page details.

        Args:
            connection: Provider connection
            content_id: Content ID

        Returns:
            Content details with body
        """
        return await self._make_api_request(
            connection,
            "GET",
            f"/content/{content_id}",
            params={"expand": "body.storage,version,space"},
        )

    async def get_content_as_export(
        self, connection: ProviderConnection, content_id: str, format: str = "view"
    ) -> bytes:
        """
        Get content body in specified format for export.

        Args:
            connection: Provider connection
            content_id: Content ID
            format: Export format (view, export_view, storage)

        Returns:
            Content body as bytes
        """
        access_token = await self.get_valid_token(connection)
        base_url = self._get_api_base_url(connection.tenant_id)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{base_url}/content/{content_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
                params={"expand": f"body.{format}"},
            )

            if response.status_code >= 400:
                raise BadRequestException(
                    f"Failed to get content: {response.status_code} - {response.text}"
                )

            data = response.json()
            body_content = data.get("body", {}).get(format, {}).get("value", "")
            return body_content.encode("utf-8")

    async def search_content(
        self,
        connection: ProviderConnection,
        cql: str,
        start: int = 0,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """
        Search for content using CQL (Confluence Query Language).

        Args:
            connection: Provider connection
            cql: CQL query string
            start: Pagination start index
            limit: Number of results per page

        Returns:
            Search results
        """
        return await self._make_api_request(
            connection,
            "GET",
            "/content/search",
            params={"cql": cql, "start": start, "limit": limit, "expand": "space,version"},
        )


def generate_state_token() -> str:
    """Generate secure random state token for OAuth CSRF protection."""
    return secrets.token_urlsafe(32)
