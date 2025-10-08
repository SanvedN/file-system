export const API_BASE =
  (typeof window !== "undefined" ? process.env.NEXT_PUBLIC_API_BASE : process.env.NEXT_PUBLIC_API_BASE) ||
  "http://localhost:8000"

export const TENANTS_BASE = "/v2/tenants"

export const SWR_KEYS = {
  TENANTS_LIST: "TENANTS_LIST",
  FILES_LIST: (tenantId: string) => `FILES_LIST:${tenantId}`,
  FILE_DETAIL: (tenantId: string, fileId: string) => `FILE_DETAIL:${tenantId}:${fileId}`,
}
