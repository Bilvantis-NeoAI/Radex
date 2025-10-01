
export interface RAGQuery {
  query: string;
  folder_ids?: string[];        // optional
  limit?: number;               // optional, defaults to 10
  session_id: string;           // required
}

export interface RAGResponse {
  query: string;
  answer: string;
  sources: RAGSource[];
  total_chunks: number;
  processing_time: number;      // in seconds
}

export interface RAGSource {
  document_id: string;
  document_name: string;
  folder_id: string;
  folder_name: string;
  chunk_text: string;
  relevance_score: number;      // 0.0 - 1.0
  metadata: Record<string, any>; // optional key-value data
  page_number?: number;
}

export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: RAGSource[];
}

export interface QuerySuggestion {
  suggestion: string;
  category: string;
}