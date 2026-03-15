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
  SupportRequestPayload,
  SupportRequestResponse,
} from "../types/api";
import { decodeJwtPayload } from "../../../lib/authIdentity";
import { supabase } from "@/lib/supabase";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const DEFAULT_TENANT_ID = "acme";

let currentConversationId: string | null = null;

function getTenantIdFromToken(token: string | null): string | null {
  if (!token) {
    return null;
  }

  const payload = decodeJwtPayload(token);
  if (!payload) {
    return null;
  }

  const candidates = [
    payload.tenant_id,
    payload.app_metadata?.tenant_id,
    payload.user_metadata?.tenant_id,
  ];

  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate;
    }
  }

  return DEFAULT_TENANT_ID;
}

async function getAccessToken(): Promise<string> {
  const session = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) {
    throw new Error("Authentication required");
  }

  return token;
}

async function getAuthHeaders(
  headers: HeadersInit = {},
): Promise<HeadersInit> {
  const token = await getAccessToken();

  return {
    Authorization: `Bearer ${token}`,
    ...headers,
  };
}

async function apiCall<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(await getAuthHeaders(options.headers)),
    },
  });

  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      await supabase.auth.signOut();
    }

    const errorText = await response.text();
    throw {
      status: response.status,
      body: errorText,
      url,
      endpoint,
    };
  }

  return response.json();
}

function generateConversationId(): string {
  return (
    "conv_" +
    (crypto.randomUUID?.() ??
      Date.now().toString(36) + Math.random().toString(36).slice(2))
  );
}

async function requireTenantId(): Promise<string> {
  const token = await getAccessToken();
  const tenantId = getTenantIdFromToken(token);
  if (!tenantId) {
    await supabase.auth.signOut();
    throw new Error("Authenticated tenant is missing");
  }

  return tenantId;
}

export const api = {
  AUTH_EVENT_NAME: supabase.AUTH_EVENT_NAME,

  getAuthState(): AuthState {
    const session = window.localStorage.getItem("p1.supabase.session");
    if (!session) {
      return "unauthenticated";
    }

    try {
      const parsed = JSON.parse(session) as { access_token?: string };
      return parsed.access_token ? "authenticated" : "unauthenticated";
    } catch {
      return "unauthenticated";
    }
  },

  getAuthHeader(): string | null {
    const raw = window.localStorage.getItem("p1.supabase.session");
    if (!raw) {
      return null;
    }

    try {
      const parsed = JSON.parse(raw) as { access_token?: string };
      return parsed.access_token ? `Bearer ${parsed.access_token}` : null;
    } catch {
      return null;
    }
  },

  getTenantId(): string | null {
    const raw = window.localStorage.getItem("p1.supabase.session");
    if (!raw) {
      return null;
    }

    try {
      const parsed = JSON.parse(raw) as { access_token?: string };
      return getTenantIdFromToken(parsed.access_token ?? null);
    } catch {
      return null;
    }
  },

  async signOut() {
    currentConversationId = null;
    await supabase.auth.signOut();
  },

  async submitQuery(
    query: string,
    conversationId?: string,
  ): Promise<QueryResponse> {
    const convId =
      conversationId || currentConversationId || generateConversationId();

    if (!conversationId) {
      currentConversationId = convId;
    }

    return apiCall<QueryResponse>("/query", {
      method: "POST",
      body: JSON.stringify({
        query,
        conversation_id: convId,
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

  async listConversations(): Promise<Conversation[]> {
    const response = await apiCall<ConversationsListResponse>("/conversations");

    return response.conversations.map((conv) => ({
      conversation_id: conv.conversation_id,
      created_at: conv.created_at,
      last_activity_at: conv.last_activity_at,
      title: conv.title,
      turns: [],
    }));
  },

  async getConversation(conversationId: string): Promise<Conversation | null> {
    const response = await apiCall<ConversationDetail>(
      `/conversations/${conversationId}`,
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
  },

  async deleteConversation(conversationId: string): Promise<void> {
    await apiCall<{ status: string }>(`/conversations/${conversationId}`, {
      method: "DELETE",
    });
  },

  async listDocuments(): Promise<Document[]> {
    const tenantId = await requireTenantId();
    const response = await apiCall<DocumentsListResponse>(
      `/tenants/${tenantId}/documents`,
    );

    return response.documents.map((doc) => ({
      filename: doc.filename,
      uploaded_at: doc.uploaded_at,
      size_bytes: doc.size_bytes,
      indexed: true,
    }));
  },

  async uploadDocument(file: File): Promise<UploadResponse> {
    const tenantId = await requireTenantId();
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${API_BASE_URL}/tenants/${tenantId}/documents`, {
      method: "POST",
      headers: await getAuthHeaders(),
      body: formData,
    });

    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        await supabase.auth.signOut();
      }

      const errorText = await response.text();
      throw new Error(`Upload failed: ${response.status} - ${errorText}`);
    }

    return response.json();
  },

  async triggerIndexing(): Promise<IndexingResponse> {
    const tenantId = await requireTenantId();
    return apiCall<IndexingResponse>(`/tenants/${tenantId}/documents/index`, {
      method: "POST",
    });
  },

  async deleteDocument(filename: string): Promise<void> {
    const tenantId = await requireTenantId();
    await apiCall<DeleteResponse>(`/tenants/${tenantId}/documents/${filename}`, {
      method: "DELETE",
    });
  },

  async submitSupportRequest(
    payload: SupportRequestPayload,
  ): Promise<SupportRequestResponse> {
    return apiCall<SupportRequestResponse>("/support/requests", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
