"use client";

import axios from "axios";
import { API_BASE, TENANTS_BASE } from "./constants";
import type {
  Tenant,
  FilesListResponse,
  FileResponse,
  SearchResponse,
} from "./types";
import { toast } from "@/hooks/use-toast";

export const api = axios.create({
  baseURL: API_BASE,
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    const status = error?.response?.status;
    const message =
      error?.response?.data?.message ||
      error?.message ||
      "Something went wrong. Please try again.";
    toast({
      title: status ? `Error ${status}` : "Network Error",
      description: message,
      variant: "destructive",
    });
    return Promise.reject(error);
  }
);

// Tenants
export async function listTenants(): Promise<Tenant[]> {
  const { data } = await api.get<Tenant[]>(TENANTS_BASE + "/");
  return data;
}
export async function createTenant(tenant_code: string): Promise<Tenant> {
  const { data } = await api.post<Tenant>(TENANTS_BASE + "/", { tenant_code });
  return data;
}
export async function deleteTenant(tenant_code: string) {
  await api.delete(TENANTS_BASE + `/${encodeURIComponent(tenant_code)}`);
}
export async function getTenant(tenant_code: string): Promise<Tenant> {
  const { data } = await api.get<Tenant>(
    TENANTS_BASE + `/${encodeURIComponent(tenant_code)}`
  );
  return data;
}
export async function patchTenant(
  tenant_code: string,
  configuration: object
): Promise<Tenant> {
  try {
    const { data } = await api.patch<Tenant>(
      TENANTS_BASE + `/${encodeURIComponent(tenant_code)}`,
      { configuration }
    );
    return data;
  } catch (err: any) {
    // Some backends may return a 500 due to response schema validation even if update applied.
    // As a safe fallback, fetch the updated tenant and return it.
    const status = err?.response?.status;
    if (status === 500) {
      const refreshed = await getTenant(tenant_code);
      return refreshed;
    }
    throw err;
  }
}

// Files
export async function listFiles(tenantId: string): Promise<FilesListResponse> {
  const { data } = await api.get<FilesListResponse>(
    `${TENANTS_BASE}/${tenantId}/files`
  );
  return data;
}
export async function uploadFile(
  tenantId: string,
  file: File,
  tag?: string
): Promise<FileResponse> {
  const form = new FormData();
  form.append("file", file);
  const url = new URL(`${API_BASE}${TENANTS_BASE}/${tenantId}/upload`);
  if (tag) url.searchParams.set("tag", tag);
  const { data } = await axios.post<FileResponse>(url.toString(), form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: () => {},
  });
  return data;
}
export async function getFile(
  tenantId: string,
  fileId: string
): Promise<FileResponse> {
  const { data } = await api.get<FileResponse>(
    `${TENANTS_BASE}/${tenantId}/files/${fileId}`
  );
  return data;
}
export async function updateFile(
  tenantId: string,
  fileId: string,
  payload: { tag?: string; metadata?: object }
): Promise<FileResponse> {
  const { data } = await api.post<FileResponse>(
    `${TENANTS_BASE}/${tenantId}/files/${fileId}`,
    payload
  );
  return data;
}
export async function deleteFile(tenantId: string, fileId: string) {
  await api.delete(`${TENANTS_BASE}/${tenantId}/files/${fileId}`);
}
export function getDownloadUrl(
  tenantId: string,
  fileId: string,
  inline = true
) {
  const u = new URL(
    `${API_BASE}${TENANTS_BASE}/${tenantId}/download/${fileId}`
  );
  u.searchParams.set("inline", String(inline));
  return u.toString();
}

export async function searchFiles(
  tenantId: string,
  query: string,
  filters?: {
    media_type?: string;
    tag?: string;
    min_size?: number;
    max_size?: number;
  },
  sort?: {
    field: "file_name" | "file_size_bytes" | "created_at" | "modified_at";
    order: "asc" | "desc";
  },
  pagination?: {
    page: number;
    per_page: number;
  }
): Promise<FilesListResponse> {
  // Map frontend search params to backend schema
  const mappedFilters: any = {};
  if (query && query.trim()) mappedFilters.file_name = query.trim();
  if (filters?.media_type) mappedFilters.media_type = filters.media_type;
  if (filters?.tag) mappedFilters.tag = filters.tag;
  if (filters?.min_size != null) mappedFilters.file_size_min = filters.min_size;
  if (filters?.max_size != null) mappedFilters.file_size_max = filters.max_size;

  const body = {
    filters: mappedFilters,
    sort: sort ?? { field: "created_at", order: "desc" },
    pagination: pagination
      ? { page: pagination.page, limit: pagination.per_page }
      : { page: 1, limit: 50 },
  };

  const { data } = await api.post<FilesListResponse>(
    `${TENANTS_BASE}/${tenantId}/files/search`,
    body
  );
  return data;
}

// Embeddings
export async function searchTenantEmbeddings(
  tenantId: string,
  query: string,
  top_k = 5
): Promise<SearchResponse> {
  const { data } = await api.post<SearchResponse>(
    `${TENANTS_BASE}/${tenantId}/embeddings/search`,
    { query, top_k }
  );
  return data;
}
export async function searchFileEmbeddings(
  tenantId: string,
  fileId: string,
  query: string,
  top_k = 5
): Promise<SearchResponse> {
  const { data } = await api.post<SearchResponse>(
    `${TENANTS_BASE}/${tenantId}/embeddings/search/${fileId}`,
    {
      query,
      top_k,
    }
  );
  return data;
}

export async function getEmbeddings(tenantId: string, fileId: string) {
  const { data } = await api.get(
    `${TENANTS_BASE}/${tenantId}/embeddings/${fileId}`
  );
  return data as {
    file_id: string;
    pages: { page_id: number; ocr?: string }[];
  };
}

export async function generateEmbeddings(tenantId: string, fileId: string) {
  const { data } = await api.post(
    `${TENANTS_BASE}/${tenantId}/embeddings/${fileId}`
  );
  return data as { file_id: string; pages_processed: number; success: boolean };
}
