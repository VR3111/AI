// Real API client for P1 backend
// Connects to FastAPI backend endpoints

import {
  AuthState,
  QueryResponse,
  ConversationsListResponse,
  ConversationDetail,
  Conversation,
  ConversationTurn,
  DocumentsListResponse,
  Document,
  UploadResponse,
  IndexingResponse,
  DeleteResponse,
} from '../types/api';

// =====================================================
// Configuration
// =====================================================
const API_BASE_URL = '/api';
const DEFAULT_TENANT_ID = 'acme';

// =====================================================
// DEV JWT (TEMPORARY)
// =====================================================
// 🔴 Replace this with a VALID JWT generated according to app/auth.py
// 🔴 Keep "Bearer " prefix
const DEV_JWT =
  'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0ZW5hbnRfaWQiOiJhY21lIn0.gQb7L0TmQahooswcDduYxwV8aHUshjTjyErUBMt8PWs';

// =====================================================
// Mock auth state (UI-level only)
// =====================================================
let currentAuthState: AuthState = 'authenticated';

// =====================================================
// Helper function to make API calls
// =====================================================
async function apiCall<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: DEV_JWT,
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API error: ${response.status} - ${errorText}`);
  }

  return response.json();
}

// =====================================================
// Conversation helpers
// =====================================================
function generateConversationId(): string {
  return 'conv_' + crypto.randomUUID();
}

let currentConversationId: string | null = null;

// =====================================================
// API Surface
// =====================================================
export const api = {
  // ---------------- Auth ----------------
  getAuthState(): AuthState {
    return currentAuthState;
  },

  setAuthState(state: AuthState) {
    currentAuthState = state;
  },

  // ---------------- Query ----------------
  async submitQuery(query: string, conversationId?: string): Promise<QueryResponse> {
    const convId = conversationId || currentConversationId || generateConversationId();

    if (!conversationId) {
      currentConversationId = convId;
    }

    return apiCall<QueryResponse>('/query', {
      method: 'POST',
      body: JSON.stringify({
        query,
        conversation_id: convId,
        tenant_id: DEFAULT_TENANT_ID,
        debug: false,
      }),
    });
  },

  resetConversation() {
    currentConversationId = null;
  },

  getCurrentConversationId(): string | null {
    return currentConversationId;
  },

  // ---------------- Conversations ----------------
  async listConversations(): Promise<Conversation[]> {
    try {
      const response = await apiCall<ConversationsListResponse>('/conversations');

      // IMPORTANT:
      // Backend list endpoint returns metadata only (no turns).
      // UI components expect `turns` to exist, so we attach empty array.
      return response.conversations.map((conv) => ({
        conversation_id: conv.conversation_id,
        created_at: conv.created_at,
        last_activity_at: conv.last_activity_at,
        turns: [],
      }));
    } catch (error) {
      console.error('Error listing conversations:', error);
      return [];
    }
  },

  async getConversation(conversationId: string): Promise<Conversation | null> {
    try {
      const response = await apiCall<ConversationDetail>(
        `/conversations/${conversationId}`
      );

      const turns: ConversationTurn[] = response.items.map((item) => {
        const citations = item.citations_json ? JSON.parse(item.citations_json) : [];
        const artifacts = item.artifacts_json ? JSON.parse(item.artifacts_json) : {};

        return {
          query: item.query,
          response: {
            request_id: item.request_id,
            created_at: item.created_at,
            tenant_id: response.tenant_id,
            conversation_id: response.conversation_id,
            query: item.query,
            mode: item.mode,
            answer: item.answer,
            citations,
            artifacts,
            debug: item.debug_json ? JSON.parse(item.debug_json) : null,
          },
        };
      });

      const created_at = response.items[0]?.created_at || new Date().toISOString();
      const last_activity_at =
        response.items[response.items.length - 1]?.created_at || created_at;

      return {
        conversation_id: response.conversation_id,
        created_at,
        last_activity_at,
        turns,
      };
    } catch (error) {
      console.error('Error getting conversation:', error);
      return null;
    }
  },

  // ---------------- Documents ----------------
  async listDocuments(): Promise<Document[]> {
    try {
      const response = await apiCall<DocumentsListResponse>(
        `/tenants/${DEFAULT_TENANT_ID}/documents`
      );

      return response.documents.map((doc) => ({
        filename: doc.filename,
        uploaded_at: doc.uploaded_at,
        size_bytes: doc.size_bytes,
        indexed: true,
      }));
    } catch (error) {
      console.error('Error listing documents:', error);
      return [];
    }
  },

  async uploadDocument(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(
      `${API_BASE_URL}/tenants/${DEFAULT_TENANT_ID}/documents`,
      {
        method: 'POST',
        headers: {
          Authorization: DEV_JWT,
        },
        body: formData,
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Upload failed: ${response.status} - ${errorText}`);
    }

    return response.json();
  },

  async triggerIndexing(): Promise<IndexingResponse> {
    return apiCall<IndexingResponse>(
      `/tenants/${DEFAULT_TENANT_ID}/documents/index`,
      { method: 'POST' }
    );
  },

  async deleteDocument(filename: string): Promise<void> {
    await apiCall<DeleteResponse>(
      `/tenants/${DEFAULT_TENANT_ID}/documents/${filename}`,
      { method: 'DELETE' }
    );
  },
};
