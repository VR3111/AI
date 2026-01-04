export interface DocumentItem {
  filename: string;
  size_bytes: number;
  uploaded_at: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

async function authFetch(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: "include",
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }

  return res.json();
}

export function listDocuments(tenantId: string) {
  return authFetch(`/tenants/${tenantId}/documents`);
}

export function uploadDocument(tenantId: string, file: File) {
  const form = new FormData();
  form.append("file", file);

  return authFetch(`/tenants/${tenantId}/documents`, {
    method: "POST",
    body: form,
  });
}

export function deleteDocument(tenantId: string, filename: string) {
  return authFetch(`/tenants/${tenantId}/documents/${filename}`, {
    method: "DELETE",
  });
}
