"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useForm } from "react-hook-form";
import { TenantSelect } from "@/components/tenant-select";
import { useFiles, mutate } from "@/lib/swr";
import { uploadFile, updateFile, searchFiles } from "@/lib/api";
import { SWR_KEYS } from "@/lib/constants";
import type { FileItem } from "@/lib/types";
import { FileRow } from "@/components/file-row";
import { JsonEditor } from "@/components/json-editor";
import { toast } from "@/hooks/use-toast";

type UploadForm = {
  file: FileList;
  tag?: string;
};

type SearchForm = {
  query: string;
  media_type: string;
  tag: string;
  sort_field: "file_name" | "file_size_bytes" | "created_at" | "modified_at";
  sort_order: "asc" | "desc";
};

export default function FilesPage() {
  const [tenantId, setTenantId] = React.useState<string | undefined>(undefined);
  const { data, isLoading } = useFiles(tenantId);
  const files: FileItem[] = data?.files || [];
  const [searchResults, setSearchResults] = React.useState<FileItem[] | null>(
    null
  );
  const [isSearching, setIsSearching] = React.useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { isSubmitting },
  } = useForm<UploadForm>();

  const {
    register: registerSearch,
    handleSubmit: handleSearchSubmit,
    reset: resetSearch,
    formState: { isSubmitting: isSearchSubmitting },
  } = useForm<SearchForm>();

  const onUpload = async (values: UploadForm) => {
    if (!tenantId) {
      toast({
        title: "Select a tenant first",
        description: "Choose a tenant to upload into.",
      });
      return;
    }
    const f = values.file?.[0];
    if (!f) return;
    try {
      await uploadFile(tenantId, f, values.tag);
      await mutate(SWR_KEYS.FILES_LIST(tenantId));
      toast({ title: "Uploaded", description: f.name });
      reset();
    } catch (error: any) {
      const message =
        error?.response?.data?.detail || error?.message || "Upload failed";
      toast({
        title: "Upload failed",
        description: message,
        variant: "destructive",
      });
    }
  };

  const onSearch = async (values: SearchForm) => {
    if (!tenantId) {
      toast({
        title: "Select a tenant first",
        description: "Choose a tenant to search in.",
      });
      return;
    }
    setIsSearching(true);
    try {
      const filters: any = {};
      if (values.media_type) filters.media_type = values.media_type;
      if (values.tag) filters.tag = values.tag;

      const sort = values.sort_field
        ? {
            field: values.sort_field,
            order: values.sort_order || "asc",
          }
        : undefined;

      const result = await searchFiles(tenantId, values.query, filters, sort);
      setSearchResults(result.files);
      toast({
        title: "Search completed",
        description: `Found ${result.files.length} files`,
      });
    } catch {
      toast({
        title: "Search failed",
        description: "Please try again",
        variant: "destructive",
      });
    } finally {
      setIsSearching(false);
    }
  };

  const clearSearch = () => {
    setSearchResults(null);
    resetSearch();
  };

  const [metaOpen, setMetaOpen] = React.useState(false);
  const [metaFile, setMetaFile] = React.useState<FileItem | null>(null);
  const [metaObj, setMetaObj] = React.useState<Record<string, unknown>>({});
  const [metaError, setMetaError] = React.useState<string | null>(null);

  function openMetadata(file: FileItem) {
    setMetaFile(file);
    setMetaObj((file.file_metadata as any) || {});
    setMetaError(null);
    setMetaOpen(true);
  }

  async function saveMetadata() {
    if (!tenantId || !metaFile) return;
    if (metaError) {
      toast({
        title: "Fix JSON errors",
        description: metaError,
        variant: "destructive",
      });
      return;
    }
    try {
      await updateFile(tenantId, metaFile.file_id, { metadata: metaObj });
      await mutate(SWR_KEYS.FILES_LIST(tenantId));
      toast({ title: "Metadata saved", description: metaFile.file_name });
      setMetaOpen(false);
    } catch {}
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="grid gap-6"
    >
      <section className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 backdrop-blur-md">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="relative z-10 sm:col-span-1">
            <label className="mb-1 block text-sm text-muted-foreground">
              Tenant
            </label>
            <TenantSelect value={tenantId} onChange={setTenantId} />
          </div>
          <form
            onSubmit={handleSubmit(onUpload)}
            className="sm:col-span-2 grid grid-cols-1 items-end gap-3 sm:grid-cols-[1fr_auto_auto]"
          >
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">
                File
              </label>
              <input
                type="file"
                {...register("file", { required: true })}
                className="w-full rounded-md border border-zinc-800 bg-zinc-950/60 file:mr-3 file:rounded file:border-0 file:bg-zinc-800/70 file:px-3 file:py-2 file:text-sm file:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">
                Tag (optional)
              </label>
              <input
                type="text"
                {...register("tag")}
                placeholder="invoices"
                className="w-full rounded-md border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
            <button
              type="submit"
              disabled={isSubmitting || !tenantId}
              className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
            >
              {isSubmitting ? "Uploading…" : "Upload"}
            </button>
          </form>
        </div>
      </section>

      <section className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 backdrop-blur-md">
        <h2 className="mb-3 text-pretty text-lg font-semibold">Search Files</h2>
        <form
          onSubmit={handleSearchSubmit(onSearch)}
          className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
        >
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">
              Search query
            </label>
            <input
              type="text"
              {...registerSearch("query")}
              placeholder="Search file names..."
              className="w-full rounded-md border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">
              Media type
            </label>
            <select
              {...registerSearch("media_type")}
              className="w-full rounded-md border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="">All types</option>
              <option value="application/pdf">PDF</option>
              <option value="image/jpeg">JPEG</option>
              <option value="image/png">PNG</option>
              <option value="text/plain">Text</option>
              <option value="application/msword">Word</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">
              Tag
            </label>
            <input
              type="text"
              {...registerSearch("tag")}
              placeholder="Filter by tag..."
              className="w-full rounded-md border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          <div className="flex items-end gap-2">
            <button
              type="submit"
              disabled={isSearchSubmitting || !tenantId}
              className="flex-1 inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
            >
              {isSearchSubmitting ? "Searching..." : "Search"}
            </button>
            {searchResults && (
              <button
                type="button"
                onClick={clearSearch}
                className="inline-flex h-10 items-center justify-center rounded-md border border-zinc-800 bg-zinc-900/60 px-4 text-sm font-medium text-foreground transition hover:bg-zinc-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                Clear
              </button>
            )}
          </div>
        </form>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">
              Sort by
            </label>
            <select
              {...registerSearch("sort_field")}
              className="w-full rounded-md border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="">Default</option>
              <option value="file_name">Name</option>
              <option value="file_size_bytes">Size</option>
              <option value="created_at">Created</option>
              <option value="modified_at">Modified</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">
              Order
            </label>
            <select
              {...registerSearch("sort_order")}
              className="w-full rounded-md border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="asc">Ascending</option>
              <option value="desc">Descending</option>
            </select>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 backdrop-blur-md">
        <div className="flex items-center justify-between">
          <h2 className="text-pretty text-lg font-semibold">
            {searchResults
              ? `Search Results (${searchResults.length})`
              : "Files"}
          </h2>
          {searchResults && (
            <button
              onClick={clearSearch}
              className="text-sm text-muted-foreground hover:text-foreground transition"
            >
              Show all files
            </button>
          )}
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full table-fixed border-collapse">
            <thead>
              <tr className="text-left text-sm text-muted-foreground">
                <th className="w-[40%] px-3 py-2">Name</th>
                <th className="w-[10%] px-3 py-2">Type</th>
                <th className="w-[10%] px-3 py-2">Size</th>
                <th className="w-[15%] px-3 py-2">Tag</th>
                <th className="w-[10%] px-3 py-2">Metadata</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading || isSearching || !tenantId ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i} className="border-b border-zinc-800/60">
                    <td className="px-3 py-3">
                      <div className="h-5 w-64 animate-pulse rounded bg-zinc-800/80" />
                      <div className="mt-2 h-4 w-40 animate-pulse rounded bg-zinc-800/60" />
                    </td>
                    <td className="px-3 py-3">
                      <div className="h-5 w-12 animate-pulse rounded bg-zinc-800/80" />
                    </td>
                    <td className="px-3 py-3">
                      <div className="h-5 w-14 animate-pulse rounded bg-zinc-800/80" />
                    </td>
                    <td className="px-3 py-3">
                      <div className="h-8 w-28 animate-pulse rounded bg-zinc-800/80" />
                    </td>
                    <td className="px-3 py-3">
                      <div className="h-8 w-24 animate-pulse rounded bg-zinc-800/80" />
                    </td>
                    <td className="px-3 py-3">
                      <div className="h-8 w-40 animate-pulse rounded bg-zinc-800/80" />
                    </td>
                  </tr>
                ))
              ) : (searchResults || files).length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-3 py-6 text-center text-sm text-muted-foreground"
                  >
                    {searchResults
                      ? "No files found matching your search."
                      : "No files yet. Upload a file to get started."}
                  </td>
                </tr>
              ) : (
                <AnimatePresence initial={false}>
                  {(searchResults || files).map((f) => (
                    <FileRow
                      key={f.file_id}
                      tenantId={tenantId!}
                      item={f}
                      onOpenMetadata={openMetadata}
                    />
                  ))}
                </AnimatePresence>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <AnimatePresence>
        {metaOpen ? (
          <motion.div
            role="dialog"
            aria-modal="true"
            className="fixed inset-0 z-50 grid place-items-center p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div
              className="absolute inset-0 bg-black/50"
              onClick={() => setMetaOpen(false)}
              aria-hidden
            />
            <motion.div
              initial={{ y: 16, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 16, opacity: 0 }}
              className="relative z-10 w-full max-w-2xl rounded-lg border border-zinc-800 bg-zinc-950/80 p-5 backdrop-blur-xl"
            >
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-lg font-semibold">Edit metadata</h3>
                <button
                  onClick={() => setMetaOpen(false)}
                  className="rounded-md px-2 py-1 text-sm text-muted-foreground transition hover:bg-zinc-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  Close
                </button>
              </div>
              <JsonEditor
                value={(metaFile?.file_metadata as any) || {}}
                onChange={(obj) => setMetaObj(obj)}
                onError={setMetaError}
              />
              <div className="mt-4 flex justify-end gap-2">
                <button
                  onClick={() => setMetaOpen(false)}
                  className="rounded-md px-4 py-2 text-sm text-muted-foreground transition hover:bg-zinc-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  Cancel
                </button>
                <button
                  onClick={saveMetadata}
                  className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  Save
                </button>
              </div>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.div>
  );
}
