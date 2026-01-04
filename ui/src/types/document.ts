export type DocumentItem = {
  filename: string;
  size_bytes: number;
  uploaded_at: string;
};

export type DocumentListResponse = {
  tenant_id: string;
  documents: DocumentItem[];
};
