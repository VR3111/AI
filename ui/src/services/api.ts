const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const AUTH_TOKEN = process.env.NEXT_PUBLIC_P1_AUTH_TOKEN;

if (!AUTH_TOKEN) {
  console.warn("NEXT_PUBLIC_P1_AUTH_TOKEN is not set");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "omit",
    headers: {
      "Content-Type": "application/json",
      ...(AUTH_TOKEN ? { Authorization: `Bearer ${AUTH_TOKEN}` } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }

  return res.json() as Promise<T>;
}

export const api = {
  listConversations() {
    return request<{
      tenant_id: string;
      conversations: {
        conversation_id: string;
        created_at: string;
        last_activity_at: string;
      }[];
    }>(`/conversations`);
  },

  getConversation(conversation_id: string) {
    return request<{
      tenant_id: string;
      conversation_id: string;
      items: {
        request_id: string;
        query: string;
        mode: string;
        answer: string;
      }[];
    }>(`/conversations/${conversation_id}`);
  },

  queryConversation(payload: {
    conversation_id: string;
    query: string;
  }) {
    return request<{
      request_id: string;
      query: string;
      mode: string;
      answer: string;
    }>(`/query`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  uploadDocument(tenantId: string, file: File) {
    const form = new FormData();
    form.append("file", file);

    return fetch(`${API_BASE}/tenants/${tenantId}/documents`, {
      method: "POST",
      headers: AUTH_TOKEN
        ? { Authorization: `Bearer ${AUTH_TOKEN}` }
        : undefined,
      body: form,
    }).then((res) => {
      if (!res.ok) throw new Error("Upload failed");
      return res.json();
    });
  },

  deleteDocument(tenantId: string, filename: string) {
    return request(`/tenants/${tenantId}/documents/${filename}`, {
      method: "DELETE",
    });
  },

  indexDocuments(tenantId: string) {
    return request(`/tenants/${tenantId}/documents/index`, {
      method: "POST",
    });
  },
};
