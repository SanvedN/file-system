"use client"

import useSWR, { type SWRConfiguration, mutate } from "swr"
import { listTenants, listFiles, getFile } from "./api"
import { SWR_KEYS } from "./constants"
import type { Tenant, FilesListResponse, FileResponse } from "./types"

export function useTenants(config?: SWRConfiguration) {
  return useSWR<Tenant[]>(SWR_KEYS.TENANTS_LIST, () => listTenants(), {
    revalidateOnFocus: true,
    ...config,
  })
}

export function useFiles(tenantId?: string, config?: SWRConfiguration) {
  const key = tenantId ? SWR_KEYS.FILES_LIST(tenantId) : null
  return useSWR<FilesListResponse>(key, () => listFiles(tenantId as string), {
    revalidateOnFocus: true,
    ...config,
  })
}

export function useFileDetail(tenantId?: string, fileId?: string, config?: SWRConfiguration) {
  const key = tenantId && fileId ? SWR_KEYS.FILE_DETAIL(tenantId, fileId) : null
  return useSWR<FileResponse>(key, () => getFile(tenantId as string, fileId as string), {
    ...config,
  })
}

export { mutate }
