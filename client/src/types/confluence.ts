/**
 * TypeScript types for Confluence provider
 */

// Reuse from SharePoint types
export interface ProviderConnectionInfo {
  id: string;
  provider: string;
  tenant_id: string;
  created_at: string;
  updated_at: string;
}

export interface ProviderConnectionsResponse {
  connections: ProviderConnectionInfo[];
}

// ============================================================================
// OAuth Flow Types
// ============================================================================

export interface ConfluenceAuthStartResponse {
  auth_url: string;
  state: string;
}

export interface ConfluenceAuthCallbackResponse {
  connection_id: string;
  cloud_id: string;
  created_at: string;
}

// ============================================================================
// Content Browsing Types
// ============================================================================

export interface ConfluenceSpace {
  id: string;
  key: string;
  name: string;
  type: string; // 'global' | 'personal'
  status?: string;
}

export interface ConfluenceSpacesResponse {
  spaces: ConfluenceSpace[];
  next_link?: string;
}

export interface ConfluencePage {
  id: string;
  type: string; // 'page' | 'blogpost' | 'attachment'
  status: string; // 'current' | 'archived'
  title: string;
  space_key: string;
  version?: number;
  last_modified?: string;
  web_url?: string;
  is_synced: boolean;
}

export interface ConfluencePagesResponse {
  pages: ConfluencePage[];
  next_link?: string;
}

export interface ConfluenceSearchResult {
  content: ConfluencePage;
  excerpt?: string;
}

export interface ConfluenceSearchResponse {
  results: ConfluenceSearchResult[];
  total_size: number;
  next_link?: string;
}

// ============================================================================
// Sync/Import Types
// ============================================================================

export interface ConfluenceItemToSync {
  space_key: string;
  content_id: string;
  version?: number;
}

export interface ConfluenceSyncImportRequest {
  connection_id: string;
  folder_id: string;
  items: ConfluenceItemToSync[];
}

export interface SyncedItemInfo {
  sharepoint_item_id: string;
  document_id: string;
  filename: string;
  status: 'success' | 'skipped' | 'failed';
  message?: string;
}

export interface SyncImportResponse {
  total: number;
  succeeded: number;
  skipped: number;
  failed: number;
  results: SyncedItemInfo[];
}

export interface BreadcrumbItem {
  id: string;
  name: string;
}
