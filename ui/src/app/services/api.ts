// Real API client for P1 backend
// Supports authenticated users and backend-issued guest sessions.

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
  IdentitySession,
  GuestUpgradeResponse,
  GuestUpgradeTicketResponse,
} from "../types/api";
import { decodeJwtPayload } from "../../../lib/authIdentity";
import { supabase } from "@/lib/supabase";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const IDENTITY_STORAGE_KEY = "p1.identity.session";
const PENDING_GUEST_UPGRADE_STORAGE_KEY = "p1.pending_guest_upgrade";

let currentConversationId: string | null = null;
let currentIdentity = readStoredIdentity();

function readStoredIdentity(): IdentitySession | null {
  const raw = window.localStorage.getItem(IDENTITY_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as IdentitySession;
  } catch {
    window.localStorage.removeItem(IDENTITY_STORAGE_KEY);
    return null;
  }
}

function writeStoredIdentity(identity: IdentitySession | null) {
  currentIdentity = identity;

  if (!identity) {
    window.localStorage.removeItem(IDENTITY_STORAGE_KEY);
  } else {
    window.localStorage.setItem(IDENTITY_STORAGE_KEY, JSON.stringify(identity));
  }

  window.dispatchEvent(new Event(supabase.AUTH_EVENT_NAME));
}

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
    payload.sub,
  ];

  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate;
    }
  }

  return null;
}

async function getAuthenticatedAccessToken(): Promise<string | null> {
  const session = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

async function getAuthHeaders(
  headers: HeadersInit = {},
): Promise<HeadersInit> {
  const token = await getAuthenticatedAccessToken();
  if (!token) {
    return { ...headers };
  }

  return {
    Authorization: `Bearer ${token}`,
    ...headers,
  };
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

async function fetchSession(
  endpoint: string,
  options: RequestInit = {},
): Promise<Response> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = await getAuthHeaders(options.headers);

  return fetch(url, {
    ...options,
    credentials: "include",
    headers,
  });
}

async function apiCall<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const isFormData = options.body instanceof FormData;
  const authHeaders = await getAuthHeaders(options.headers);
  const headers: HeadersInit = isFormData
    ? authHeaders
    : {
        "Content-Type": "application/json",
        ...authHeaders,
      };

  const response = await fetch(url, {
    ...options,
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    let message = "Request failed";
    const errorText = await response.text();
    try {
      const parsed = JSON.parse(errorText) as { detail?: string; message?: string };
      message = parsed.detail || parsed.message || errorText || message;
    } catch {
      message = errorText || message;
    }

    if (response.status === 401 || response.status === 403) {
      await handleIdentityFailure();
    }

    const error = new Error(message);
    (error as Error & { status?: number; body?: string; url?: string; endpoint?: string }).status =
      response.status;
    (error as Error & { status?: number; body?: string; url?: string; endpoint?: string }).body =
      errorText;
    (error as Error & { status?: number; body?: string; url?: string; endpoint?: string }).url =
      url;
    (error as Error & { status?: number; body?: string; url?: string; endpoint?: string }).endpoint =
      endpoint;
    throw error;
  }

  return parseJsonResponse<T>(response);
}

function generateConversationId(): string {
  return (
    "conv_" +
    (crypto.randomUUID?.() ??
      Date.now().toString(36) + Math.random().toString(36).slice(2))
  );
}

async function ensureIdentity(): Promise<IdentitySession> {
  const token = await getAuthenticatedAccessToken();
  const endpoint = token ? "/auth/session" : "/auth/guest-session";
  const method = token ? "GET" : "POST";

  const response = await fetchSession(endpoint, { method });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Failed to establish session");
  }

  const identity = await parseJsonResponse<IdentitySession>(response);
  writeStoredIdentity(identity);
  return identity;
}

async function handleIdentityFailure() {
  const token = await getAuthenticatedAccessToken();
  if (token) {
    await supabase.auth.signOut();
  }
  writeStoredIdentity(null);
}

async function requireTenantId(): Promise<string> {
  const identity = currentIdentity ?? (await ensureIdentity());
  if (!identity?.tenant_id) {
    throw new Error("Tenant identity is missing");
  }

  return identity.tenant_id;
}

export const api = {
  AUTH_EVENT_NAME: supabase.AUTH_EVENT_NAME,

  async initializeSession(): Promise<IdentitySession> {
    await supabase.auth.initialize();
    return ensureIdentity();
  },

  async refreshIdentitySession(): Promise<IdentitySession> {
    return ensureIdentity();
  },

  getAuthState(): AuthState {
    return currentIdentity?.authenticated ? "authenticated" : "unauthenticated";
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
    if (currentIdentity?.tenant_id) {
      return currentIdentity.tenant_id;
    }

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

  getIdentity(): IdentitySession | null {
    return currentIdentity;
  },

  markPendingGuestUpgrade(ticket: string, email: string) {
    window.localStorage.setItem(
      PENDING_GUEST_UPGRADE_STORAGE_KEY,
      JSON.stringify({ ticket, email: email.trim().toLowerCase() }),
    );
  },

  clearPendingGuestUpgrade() {
    window.localStorage.removeItem(PENDING_GUEST_UPGRADE_STORAGE_KEY);
  },

  hasPendingGuestUpgrade(): boolean {
    return Boolean(window.localStorage.getItem(PENDING_GUEST_UPGRADE_STORAGE_KEY));
  },

  getPendingGuestUpgrade(): { ticket: string; email: string } | null {
    const raw = window.localStorage.getItem(PENDING_GUEST_UPGRADE_STORAGE_KEY);
    if (!raw) {
      return null;
    }

    try {
      const parsed = JSON.parse(raw) as { ticket?: string; email?: string };
      if (
        typeof parsed.ticket === "string" &&
        parsed.ticket.trim() &&
        typeof parsed.email === "string" &&
        parsed.email.trim()
      ) {
        return {
          ticket: parsed.ticket,
          email: parsed.email.trim().toLowerCase(),
        };
      }

      window.localStorage.removeItem(PENDING_GUEST_UPGRADE_STORAGE_KEY);
      return null;
    } catch {
      window.localStorage.removeItem(PENDING_GUEST_UPGRADE_STORAGE_KEY);
      return null;
    }
  },

  async signOut() {
    currentConversationId = null;
    await supabase.auth.signOut();
    writeStoredIdentity(null);
    api.clearPendingGuestUpgrade();
    await ensureIdentity();
  },

  async prepareGuestUpgrade(): Promise<GuestUpgradeResponse> {
    const pending = api.getPendingGuestUpgrade();
    if (!pending) {
      throw new Error("No pending guest upgrade");
    }

    return apiCall<GuestUpgradeResponse>("/auth/guest-session/upgrade", {
      method: "POST",
      body: JSON.stringify({ ticket: pending.ticket }),
    });
  },

  async createGuestUpgradeTicket(
    email: string,
  ): Promise<GuestUpgradeTicketResponse> {
    return apiCall<GuestUpgradeTicketResponse>(
      "/auth/guest-session/upgrade-ticket",
      {
        method: "POST",
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      },
    );
  },

  async deleteAccount(): Promise<void> {
    await apiCall<{ status: string }>("/auth/account", {
      method: "DELETE",
    });
    currentConversationId = null;
    await supabase.auth.signOut();
    writeStoredIdentity(null);
    api.clearPendingGuestUpgrade();
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

    const response = await apiCall<UploadResponse>(
      `/tenants/${tenantId}/documents`,
      {
        method: "POST",
        body: formData,
      },
    );

    return response;
  },

  async triggerIndexing(_documentId?: string): Promise<IndexingResponse> {
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
