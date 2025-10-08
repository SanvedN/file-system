export type Tenant = {
  tenant_id: string;
  tenant_code: string;
  configuration?: Record<string, unknown> | null;
  created_at: string;
  updated_at?: string | null;
};

export type FileItem = {
  file_id: string;
  file_name: string;
  media_type: string;
  file_size_bytes: number;
  tag?: string | null;
  file_metadata?: Record<string, unknown> | null;
  created_at?: string;
  updated_at?: string;
};

export type FilesListResponse = {
  files: FileItem[];
};

export type FileResponse = FileItem;

export type EmbeddingMatch = {
  file_id?: string;
  page_id: string;
  score: number;
  ocr?: string;
  embeddings?: number[];
};

export type SearchResponse = {
  matches: EmbeddingMatch[];
};
