import { useState } from 'react';
import { Document } from '../types/api';

interface DocumentListProps {
  documents: Document[];
  onUpload: (file: File) => void;
  onIndex: (documentId: string) => void;
  onDelete: (documentId: string) => void;
  isLoading?: boolean;
}

export function DocumentList({
  documents,
  onUpload,
  onIndex,
  onDelete,
  isLoading = false,
}: DocumentListProps) {
  const [isUploading, setIsUploading] = useState(false);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setIsUploading(true);
      await onUpload(file);
      setIsUploading(false);
      e.target.value = '';
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  };

  return (
    <div className="h-full flex flex-col bg-card border-l border-border/50">
      <div className="p-6 border-b border-border/50">
        <h2 className="mb-4">Documents</h2>
        <label className="block group cursor-pointer">
          <input
            type="file"
            className="hidden"
            onChange={handleFileChange}
            accept=".pdf,.doc,.docx,.txt"
            disabled={isUploading}
          />
          <div className="relative px-5 py-3 bg-gradient-to-r from-primary to-primary/90 text-primary-foreground rounded-xl text-center overflow-hidden transition-all duration-200 hover:shadow-lg hover:shadow-primary/25 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed">
            <div className="relative z-10 flex items-center justify-center gap-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <span>{isUploading ? 'Uploading...' : 'Upload Document'}</span>
            </div>
          </div>
        </label>
        <p className="text-xs text-muted-foreground mt-3 px-1">
          Upload does not automatically index. Trigger indexing separately.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-6 text-center">
            <div className="inline-flex items-center gap-2 text-muted-foreground">
              <div className="w-4 h-4 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
              <span>Loading documents...</span>
            </div>
          </div>
        ) : documents.length === 0 ? (
          <div className="p-6 text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-secondary/50 rounded-xl mb-3">
              <svg className="w-6 h-6 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-sm text-muted-foreground">No documents uploaded</p>
          </div>
        ) : (
          <div className="p-3 space-y-2">
            {documents.map(doc => (
              <div key={doc.filename} className="group bg-secondary/30 hover:bg-secondary/50 rounded-xl p-4 border border-border/30 hover:border-border/60 transition-all duration-200">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 mt-1">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center">
                      <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="truncate mb-2">{doc.filename}</div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground mb-3">
                      <span>{formatBytes(doc.size_bytes)}</span>
                      <span>•</span>
                      <span>{formatDate(doc.uploaded_at)}</span>
                    </div>
                    <div className="flex items-center gap-2 mb-3">
                      {doc.indexed ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-emerald-500/20 text-emerald-400 rounded-lg border border-emerald-500/30 backdrop-blur-sm">
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                          </svg>
                          <span className="text-xs">Indexed</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-zinc-500/20 text-zinc-400 rounded-lg border border-zinc-500/30 backdrop-blur-sm">
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <span className="text-xs">Not Indexed</span>
                        </span>
                      )}
                    </div>
                    <div className="flex gap-2">
                      {!doc.indexed && (
                        <button
                          onClick={() => onIndex(doc.filename)}
                          className="px-3 py-1.5 text-xs bg-primary/10 text-primary rounded-lg hover:bg-primary/20 border border-primary/20 hover:border-primary/30 transition-all duration-200"
                        >
                          Trigger Indexing
                        </button>
                      )}
                      <button
                        onClick={() => onDelete(doc.filename)}
                        className="px-3 py-1.5 text-xs bg-destructive/10 text-destructive rounded-lg hover:bg-destructive/20 border border-destructive/20 hover:border-destructive/30 transition-all duration-200"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}