import type { RAGSource } from './rag';

// ---------- Frontend UI message (for rendering chat bubble) ----------
export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant'; // purely frontend display
  content: string;
  timestamp: Date;
  sources?: RAGSource[]; // assistant messages may carry sources
}

// ---------- Backend Chat Session ----------
export interface ChatSession {
  id: string;
  user_id: string;
  title: string;
  created_at: Date;
}

export interface ChatSessionCreate {
  title?: string; // optional (default = first question)
}

export interface ChatSessionResponse extends ChatSession {}

// ---------- Backend Chat Message ----------
export interface ChatMessageCreate {
  query: string;
  response: string;
  sources?: RAGSource[];
  chat_metadata?: Record<string, any>;
}

export interface ChatMessageResponse {
  id: string;
  session_id: string;
  user_id: string;
  created_at: string;
  query: string;
  response: string;
  sources: RAGSource[];
  chat_metadata: Record<string, any>;
}

// ---------- Composite ----------
export interface ChatSessionWithMessages extends ChatSession {
  messages: ChatMessageResponse[];
}
