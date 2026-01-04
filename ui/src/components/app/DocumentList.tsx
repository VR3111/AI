"use client";

import { useEffect, useState } from "react";
import { api } from "@/services/api";
import { DocumentItem } from "@/types/document";

type Props = {
  tenantId: string;
};

export default function DocumentList({ tenantId }: Props) {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  async function loadDocuments() {
    setLoading(true);
    try {
      const res = await api.listDocuments(tenantId);
      setDocuments(res.documents);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDocuments();
  }, [tenantId]);

  async function handleUpload(file: File) {
    setUploading(true);
    try {
      await api.uploadDocument(tenantId, file);
      await loadDocuments();
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(filename: string) {
    await api.deleteDocument(tenantId, filename);
    await loadDocuments();
  }

  function formatBytes(bytes: number) {
    if (!bytes) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
  }

  function formatDate(value: string) {
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  }

  return (
    <div className="h-full flex flex-col bg-card border-l border-border/50">
      {/* Header */}
      <div className="p-6 border-b border-border/50">
        <h2 className="mb-4">Documents</h2>

        <label className="block cursor-pointer">
          <input
            type="file"
            accept=".pdf"
            className="hidden"
            disabled={uploading}
            onChange={e => {
              const file = e.target.files?.[0];
              if (file) handleUpload(file);
              e.currentTarget.value = "";
            }}
          />

          <div className="px-5 py-3 rounded-xl bg-gradient-to-r from-primary to-primary/90 text-primary-foreground text-center transition hover:shadow-lg hover:shadow-primary/25 active:scale-[0.98]">
            {uploading ? "Uploading & indexing…" : "Upload document"}
          </div>
        </label>

        <p className="text-xs text-muted-foreground mt-3">
          Documents are indexed automatically after upload.
        </p>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-6 text-center text-muted-foreground">
            Loading documents…
          </div>
        ) : documents.length === 0 ? (
          <div className="p-6 text-center text-muted-foreground">
            No documents uploaded
          </div>
        ) : (
          <div className="p-3 space-y-2">
            {documents.map(doc => (
              <div
                key={doc.filename}
                className="group rounded-xl p-4 bg-secondary/30 border border-border/30 hover:bg-secondary/50 transition"
              >
                <div className="truncate mb-2">{doc.filename}</div>

                <div className="text-xs text-muted-foreground mb-3 flex gap-2">
                  <span>{formatBytes(doc.size_bytes)}</span>
                  <span>•</span>
                  <span>{formatDate(doc.uploaded_at)}</span>
                </div>

                <button
                  onClick={() => handleDelete(doc.filename)}
                  className="px-3 py-1.5 text-xs rounded-lg bg-destructive/10 text-destructive hover:bg-destructive/20 border border-destructive/20 transition"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
