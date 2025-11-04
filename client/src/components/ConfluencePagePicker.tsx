'use client';

import { useState, useEffect, useCallback } from 'react';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import {
  ChevronRight,
  FileText,
  Check,
  Search,
  AlertCircle,
  Layers,
  ArrowLeft,
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import type {
  ConfluenceSpace,
  ConfluencePage,
  ConfluenceSearchResult,
  SyncImportResponse,
} from '@/types/confluence';

interface ConfluencePagePickerProps {
  isOpen: boolean;
  onClose: () => void;
  connectionId: string | null;
  folderId: string;
  onImportComplete: (result: SyncImportResponse) => void;
}

type Tab = 'spaces' | 'search';

export function ConfluencePagePicker({
  isOpen,
  onClose,
  connectionId,
  folderId,
  onImportComplete,
}: ConfluencePagePickerProps) {
  const [activeTab, setActiveTab] = useState<Tab>('spaces');
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Spaces state
  const [spaces, setSpaces] = useState<ConfluenceSpace[]>([]);
  const [selectedSpace, setSelectedSpace] = useState<ConfluenceSpace | null>(null);
  const [pages, setPages] = useState<ConfluencePage[]>([]);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<ConfluenceSearchResult[]>([]);
  const [totalSearchResults, setTotalSearchResults] = useState(0);

  // Selection state
  const [selectedPages, setSelectedPages] = useState<Set<string>>(new Set());

  const loadSpaces = useCallback(async () => {
    if (!connectionId) return;

    try {
      setLoading(true);
      setError(null);

      const response = await apiClient.getConfluenceSpacesOAuth(connectionId);
      setSpaces(response.spaces);
    } catch (err: unknown) {
      const errorMessage =
        err && typeof err === 'object' && 'response' in err &&
        err.response && typeof err.response === 'object' && 'data' in err.response &&
        err.response.data && typeof err.response.data === 'object' && 'detail' in err.response.data
          ? String(err.response.data.detail)
          : 'Failed to load Confluence spaces';
      setError(errorMessage);
      console.error('Failed to load spaces:', err);
    } finally {
      setLoading(false);
    }
  }, [connectionId]);

  useEffect(() => {
    if (isOpen && connectionId && activeTab === 'spaces') {
      loadSpaces();
    }
  }, [isOpen, connectionId, activeTab, loadSpaces]);

  const selectSpace = async (space: ConfluenceSpace) => {
    if (!connectionId) return;

    try {
      setLoading(true);
      setError(null);
      setSelectedSpace(space);

      const response = await apiClient.getConfluenceSpacePagesOAuth(connectionId, space.key);
      setPages(response.pages);
    } catch (err: unknown) {
      const errorMessage =
        err && typeof err === 'object' && 'response' in err &&
        err.response && typeof err.response === 'object' && 'data' in err.response &&
        err.response.data && typeof err.response.data === 'object' && 'detail' in err.response.data
          ? String(err.response.data.detail)
          : 'Failed to load space pages';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const backToSpaces = () => {
    setSelectedSpace(null);
    setPages([]);
  };

  const performSearch = async () => {
    if (!connectionId || !searchQuery.trim()) return;

    try {
      setLoading(true);
      setError(null);

      const response = await apiClient.searchConfluenceContentOAuth(connectionId, searchQuery);
      setSearchResults(response.results);
      setTotalSearchResults(response.total_size);
    } catch (err: unknown) {
      const errorMessage =
        err && typeof err === 'object' && 'response' in err &&
        err.response && typeof err.response === 'object' && 'data' in err.response &&
        err.response.data && typeof err.response.data === 'object' && 'detail' in err.response.data
          ? String(err.response.data.detail)
          : 'Failed to search Confluence';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const togglePageSelection = (page: ConfluencePage) => {
    const key = `${page.space_key}:${page.id}`;
    const newSelection = new Set(selectedPages);

    if (newSelection.has(key)) {
      newSelection.delete(key);
    } else {
      newSelection.add(key);
    }

    setSelectedPages(newSelection);
  };

  const handleImport = async () => {
    if (!connectionId || selectedPages.size === 0) return;

    try {
      setImporting(true);
      setError(null);

      // Build import request from spaces view
      let itemsToImport: { space_key: string; content_id: string; version?: number }[] = [];

      if (activeTab === 'spaces' && pages.length > 0) {
        itemsToImport = pages
          .filter((page) => {
            const key = `${page.space_key}:${page.id}`;
            return selectedPages.has(key);
          })
          .map((page) => ({
            space_key: page.space_key,
            content_id: page.id,
            version: page.version,
          }));
      } else if (activeTab === 'search' && searchResults.length > 0) {
        itemsToImport = searchResults
          .map((result) => result.content)
          .filter((page) => {
            const key = `${page.space_key}:${page.id}`;
            return selectedPages.has(key);
          })
          .map((page) => ({
            space_key: page.space_key,
            content_id: page.id,
            version: page.version,
          }));
      }

      const result = await apiClient.importFromConfluence({
        connection_id: connectionId,
        folder_id: folderId,
        items: itemsToImport,
      });

      onImportComplete(result);
      setSelectedPages(new Set());
      onClose();
    } catch (err: unknown) {
      const errorMessage =
        err && typeof err === 'object' && 'response' in err &&
        err.response && typeof err.response === 'object' && 'data' in err.response &&
        err.response.data && typeof err.response.data === 'object' && 'detail' in err.response.data
          ? String(err.response.data.detail)
          : 'Failed to import pages';
      setError(errorMessage);
    } finally {
      setImporting(false);
    }
  };

  const renderPageList = (pagesToRender: ConfluencePage[]) => {
    if (loading) {
      return (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      );
    }

    if (pagesToRender.length === 0) {
      return (
        <div className="text-center py-12 text-gray-500">
          <FileText className="w-12 h-12 mx-auto mb-2 text-gray-400" />
          <p>No pages found</p>
        </div>
      );
    }

    return (
      <div className="border border-gray-200 rounded-lg divide-y divide-gray-200 max-h-96 overflow-y-auto">
        {pagesToRender.map((page) => {
          const key = `${page.space_key}:${page.id}`;
          const isSelected = selectedPages.has(key);

          return (
            <div
              key={page.id}
              className="flex items-center p-3 hover:bg-gray-50 cursor-pointer"
              onClick={() => togglePageSelection(page)}
            >
              <input
                type="checkbox"
                checked={isSelected}
                onChange={() => togglePageSelection(page)}
                onClick={(e) => e.stopPropagation()}
                disabled={page.is_synced}
                className="mr-3 h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
              />

              <div className="flex-shrink-0 mr-3">
                <FileText className="w-5 h-5 text-blue-500" />
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {page.title}
                </p>
                <div className="flex items-center space-x-2 text-xs text-gray-500">
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                    {page.space_key}
                  </span>
                  {page.version && <span>v{page.version}</span>}
                  {page.last_modified && (
                    <span>{new Date(page.last_modified).toLocaleDateString()}</span>
                  )}
                  {page.is_synced && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      <Check className="w-3 h-3 mr-1" />
                      Synced
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  const renderSpacesTab = () => {
    if (selectedSpace) {
      // Show pages in selected space
      return (
        <div>
          <div className="mb-4">
            <Button
              variant="secondary"
              size="sm"
              onClick={backToSpaces}
            >
              <ArrowLeft className="w-4 h-4 mr-1" />
              Back to spaces
            </Button>
            <h3 className="mt-2 font-semibold text-gray-900">{selectedSpace.name}</h3>
            <p className="text-sm text-gray-500">Space key: {selectedSpace.key}</p>
          </div>
          {renderPageList(pages)}
        </div>
      );
    }

    // Show space list
    if (loading) {
      return (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      );
    }

    if (spaces.length === 0) {
      return (
        <div className="text-center py-12 text-gray-500">
          <Layers className="w-12 h-12 mx-auto mb-2 text-gray-400" />
          <p>No Confluence spaces found</p>
        </div>
      );
    }

    return (
      <div className="border border-gray-200 rounded-lg divide-y divide-gray-200">
        {spaces.map((space) => (
          <button
            key={space.id}
            onClick={() => selectSpace(space)}
            className="w-full flex items-center p-3 hover:bg-gray-50 text-left"
          >
            <Layers className="w-5 h-5 text-blue-500 mr-3 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">{space.name}</p>
              <div className="flex items-center space-x-2 text-xs text-gray-500">
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                  {space.key}
                </span>
                <span className="capitalize">{space.type}</span>
              </div>
            </div>
            <ChevronRight className="w-5 h-5 text-gray-400 flex-shrink-0" />
          </button>
        ))}
      </div>
    );
  };

  const renderSearchTab = () => (
    <div>
      <div className="mb-4">
        <div className="flex space-x-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && performSearch()}
            placeholder="Search Confluence pages..."
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          <Button onClick={performSearch} disabled={loading || !searchQuery.trim()}>
            <Search className="w-4 h-4" />
          </Button>
        </div>
        {totalSearchResults > 0 && (
          <p className="mt-2 text-sm text-gray-600">
            Found {totalSearchResults} result{totalSearchResults !== 1 ? 's' : ''}
          </p>
        )}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : searchResults.length > 0 ? (
        <div className="border border-gray-200 rounded-lg divide-y divide-gray-200 max-h-96 overflow-y-auto">
          {searchResults.map((result) => {
            const page = result.content;
            const key = `${page.space_key}:${page.id}`;
            const isSelected = selectedPages.has(key);

            return (
              <div
                key={page.id}
                className="p-3 hover:bg-gray-50 cursor-pointer"
                onClick={() => togglePageSelection(page)}
              >
                <div className="flex items-start">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => togglePageSelection(page)}
                    onClick={(e) => e.stopPropagation()}
                    disabled={page.is_synced}
                    className="mr-3 mt-1 h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                  />

                  <div className="flex-shrink-0 mr-3 mt-0.5">
                    <FileText className="w-5 h-5 text-blue-500" />
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">{page.title}</p>
                    {result.excerpt && (
                      <p className="mt-1 text-xs text-gray-600 line-clamp-2"
                        dangerouslySetInnerHTML={{ __html: result.excerpt }}
                      />
                    )}
                    <div className="flex items-center space-x-2 mt-1 text-xs text-gray-500">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                        {page.space_key}
                      </span>
                      {page.version && <span>v{page.version}</span>}
                      {page.is_synced && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                          <Check className="w-3 h-3 mr-1" />
                          Synced
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-12 text-gray-500">
          <Search className="w-12 h-12 mx-auto mb-2 text-gray-400" />
          <p>Search for Confluence pages to import</p>
        </div>
      )}
    </div>
  );

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Import from Confluence" size="xl">
      <div className="space-y-4">
        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="flex space-x-4">
            <button
              onClick={() => setActiveTab('spaces')}
              className={`pb-3 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'spaces'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Layers className="w-4 h-4 inline-block mr-2" />
              Browse Spaces
            </button>
            <button
              onClick={() => setActiveTab('search')}
              className={`pb-3 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'search'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Search className="w-4 h-4 inline-block mr-2" />
              Search Pages
            </button>
          </nav>
        </div>

        {/* Error display */}
        {error && (
          <div className="flex items-center p-3 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-500 mr-2 flex-shrink-0" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Tab content */}
        <div className="min-h-[400px]">
          {activeTab === 'spaces' ? renderSpacesTab() : renderSearchTab()}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between pt-4 border-t border-gray-200">
          <div className="text-sm text-gray-600">
            {selectedPages.size > 0 && (
              <span>
                {selectedPages.size} page{selectedPages.size !== 1 ? 's' : ''} selected
              </span>
            )}
          </div>
          <div className="flex space-x-2">
            <Button variant="secondary" onClick={onClose} disabled={importing}>
              Cancel
            </Button>
            <Button
              onClick={handleImport}
              disabled={selectedPages.size === 0 || importing}
            >
              {importing ? 'Importing...' : 'Import Selected'}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
