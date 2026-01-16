// API types for the document Q&A system

export type AuthState = "unauthenticated" | "unauthorized" | "authenticated";

export type ResponseMode = "direct_answer" | "guided_fallback" | "hard_refusal";

// Matches backend citation object returned by POST /query
export interface DocumentCitation {
  source: string; // e.g. "data/tenants/acme/docs/volvo.pdf"
  page: number;   // e.g. 18
  score: number;  // distance score
  snippet: string;
}

// Backend response from POST /query
export interface QueryResponse {
  request_id: string;
  created_at: string;
  tenant_id: string;
  conversation_id: string;
  query: string;
  mode: ResponseMode;
  answer: string;
  citations: DocumentCitation[];
  artifacts: {
    reason?: string;
    additional_resources?: any[];
    best_score?: number;
  };
  debug: any | null;
}

export interface ConversationTurn {
  query: string;
  response: QueryResponse;
}

// Backend response from GET /conversations/{id}
export interface ConversationDetail {
  tenant_id: string;
  conversation_id: string;
  items: Array<{
    request_id: string;
    created_at: string;
    query: string;
    mode: ResponseMode;
    answer: string;
    citations_json: string;
    artifacts_json: string;
    debug_json: string | null;
    response_json: string;
  }>;
}

// Backend response from GET /conversations
export interface ConversationListItem {
  conversation_id: string;
  created_at: string;
  last_activity_at: string;
}

export interface ConversationsListResponse {
  tenant_id: string;
  conversations: ConversationListItem[];
}

// Derived type for UI consumption
export interface Conversation {
  conversation_id: string;
  created_at: string;
  last_activity_at: string;
  turns?: ConversationTurn[];
}

// Backend response from GET /tenants/{id}/documents
export interface DocumentListItem {
  filename: string;
  size_bytes: number;
  uploaded_at: string;
}

export interface DocumentsListResponse {
  tenant_id: string;
  documents: DocumentListItem[];
}

// UI-friendly document type
export interface Document {
  filename: string;
  uploaded_at: string;
  size_bytes: number;
  indexed: boolean;
}

// Backend response from POST /tenants/{id}/documents
export interface UploadResponse {
  tenant_id: string;
  filename: string;
  stored_path: string;
  indexed: boolean;
  message: string;
}

// Backend response from POST /tenants/{id}/documents/index
export interface IndexingResponse {
  tenant_id: string;
  indexed: boolean;
  message: string;
}

// Backend response from DELETE /tenants/{id}/documents/{filename}
export interface DeleteResponse {
  tenant_id: string;
  deleted: boolean;
  filename: string;
  message: string;
}
