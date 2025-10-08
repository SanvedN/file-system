"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { TenantSelect } from "@/components/tenant-select";
import { useFiles } from "@/lib/swr";
import {
  searchTenantEmbeddings,
  searchFileEmbeddings,
  getEmbeddings,
} from "@/lib/api";
import type { EmbeddingMatch } from "@/lib/types";
import { toast } from "@/hooks/use-toast";
import { useForm } from "react-hook-form";

type SearchForm = {
  query: string;
  top_k?: number;
};
type FileSearchForm = {
  fileId: string;
  query: string;
  top_k?: number;
};

export default function EmbeddingsPage() {
  const [tenantId, setTenantId] = React.useState<string | undefined>(undefined);
  const { data } = useFiles(tenantId);
  const files = data?.files || [];
  const filesKey = React.useMemo(
    () => (files && files.length ? files.map((f) => f.file_id).join("|") : ""),
    [files]
  );
  const prevEmbeddingsKeyRef = React.useRef<string>("");
  const [filesWithEmbeddings, setFilesWithEmbeddings] = React.useState<
    string[]
  >([]);
  const [checkingEmbeddings, setCheckingEmbeddings] = React.useState(false);

  const [matches, setMatches] = React.useState<EmbeddingMatch[]>([]);
  const [matchesFile, setMatchesFile] = React.useState<EmbeddingMatch[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [loadingFile, setLoadingFile] = React.useState(false);

  const { register, handleSubmit, reset } = useForm<SearchForm>({
    defaultValues: { top_k: 5 },
  });
  const {
    register: registerFile,
    handleSubmit: handleSubmitFile,
    reset: resetFile,
  } = useForm<FileSearchForm>({
    defaultValues: { top_k: 5 },
  });

  // Check which files have embeddings (safe against unmounts)
  React.useEffect(() => {
    let cancelled = false;
    if (!tenantId || files.length === 0) {
      // Reset only if changed to avoid extra renders
      if (prevEmbeddingsKeyRef.current !== "") {
        prevEmbeddingsKeyRef.current = "";
        setFilesWithEmbeddings([]);
      }
      if (checkingEmbeddings) setCheckingEmbeddings(false);
      return () => {
        cancelled = true;
      };
    }

    const checkEmbeddings = async () => {
      setCheckingEmbeddings(true);
      const collected: string[] = [];

      // Check all files concurrently and ignore errors
      await Promise.allSettled(
        files.map(async (file) => {
          try {
            const result = await getEmbeddings(tenantId, file.file_id);
            if (!cancelled && result.pages && result.pages.length > 0) {
              collected.push(file.file_id);
            }
          } catch {
            // ignore missing embeddings per file
          }
        })
      );

      if (!cancelled) {
        const newKey = collected.sort().join("|");
        if (newKey !== prevEmbeddingsKeyRef.current) {
          prevEmbeddingsKeyRef.current = newKey;
          setFilesWithEmbeddings(collected);
        }
        setCheckingEmbeddings(false);
      }
    };

    checkEmbeddings();

    return () => {
      cancelled = true;
    };
  }, [tenantId, filesKey]);

  const onTenantSearch = async (values: SearchForm) => {
    if (!tenantId) {
      toast({
        title: "Select a tenant",
        description: "Choose a tenant to search.",
      });
      return;
    }
    setLoading(true);
    try {
      const res = await searchTenantEmbeddings(
        tenantId,
        values.query,
        values.top_k || 5
      );
      setMatches(res.matches);
    } catch {
      setMatches([]);
    } finally {
      setLoading(false);
    }
  };

  const onFileSearch = async (values: FileSearchForm) => {
    if (!tenantId) {
      toast({
        title: "Select a tenant",
        description: "Choose a tenant to search.",
      });
      return;
    }
    if (!values.fileId) {
      toast({
        title: "Select a file",
        description: "Choose a file with embeddings to search.",
      });
      return;
    }
    setLoadingFile(true);
    try {
      const res = await searchFileEmbeddings(
        tenantId,
        values.fileId,
        values.query,
        values.top_k || 5
      );
      setMatchesFile(res.matches);
      if (res.matches.length === 0) {
        toast({
          title: "No matches found",
          description:
            "No embeddings found for this query in the selected file.",
        });
      }
    } catch (error: any) {
      setMatchesFile([]);
      const message =
        error?.response?.data?.detail || error?.message || "Search failed";
      toast({
        title: "Search failed",
        description: message,
        variant: "destructive",
      });
    } finally {
      setLoadingFile(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="grid gap-6"
    >
      <section className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 backdrop-blur-md">
        <h2 className="text-pretty text-lg font-semibold">
          Tenant-wide search
        </h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">
              Tenant
            </label>
            <TenantSelect value={tenantId} onChange={setTenantId} />
          </div>
          <form
            onSubmit={handleSubmit(onTenantSearch)}
            className="sm:col-span-2 grid grid-cols-1 items-end gap-3 sm:grid-cols-[1fr_auto_auto]"
          >
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">
                Query
              </label>
              <input
                type="text"
                {...register("query", { required: true })}
                placeholder="Find invoices with PO #123..."
                className="w-full rounded-md border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">
                Top K
              </label>
              <input
                type="number"
                min={1}
                max={20}
                {...register("top_k", { valueAsNumber: true })}
                className="w-full rounded-md border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
            <button
              type="submit"
              className="h-10 rounded-md bg-primary px-4 text-sm text-primary-foreground transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {loading ? "Searching…" : "Search"}
            </button>
          </form>
        </div>

        <div className="mt-4">
          <AnimatePresence initial={false}>
            {matches.length === 0 ? (
              <p className="text-sm text-muted-foreground">No results yet.</p>
            ) : (
              <ul className="grid gap-2">
                {matches.map((m, i) => (
                  <motion.li
                    key={i}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-md border border-zinc-800 bg-zinc-950/60 p-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-sm">
                        <span className="text-muted-foreground">file_id:</span>{" "}
                        <span className="font-mono">{m.file_id}</span>
                      </div>
                      <div className="text-sm">
                        <span className="text-muted-foreground">score:</span>{" "}
                        <span className="font-mono">{m.score.toFixed(3)}</span>
                      </div>
                    </div>
                    {m.ocr ? (
                      <p className="mt-2 text-pretty text-sm text-muted-foreground">
                        {m.ocr}
                      </p>
                    ) : null}
                    <div className="mt-2 flex items-center gap-2">
                      <button
                        onClick={() => {
                          if (!tenantId || !m.file_id) return;
                          window.open(
                            `${
                              process.env.NEXT_PUBLIC_API_BASE ||
                              "http://localhost:8000"
                            }/v2/tenants/${tenantId}/download/${
                              m.file_id
                            }?inline=true`,
                            "_blank"
                          );
                        }}
                        className="rounded-md bg-primary px-3 py-1 text-sm text-primary-foreground transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        Open file
                      </button>
                      <div>page_id: {m.page_id}</div>
                    </div>
                  </motion.li>
                ))}
              </ul>
            )}
          </AnimatePresence>
        </div>
      </section>

      <section className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 backdrop-blur-md">
        <h2 className="text-pretty text-lg font-semibold">
          File-specific search
        </h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">
              Select file
            </label>
            <select
              {...registerFile("fileId", { required: true })}
              disabled={checkingEmbeddings || filesWithEmbeddings.length === 0}
              className="w-full rounded-md border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
            >
              <option value="">
                {checkingEmbeddings
                  ? "Checking embeddings..."
                  : filesWithEmbeddings.length === 0
                  ? "No files with embeddings found"
                  : "-- choose file with embeddings --"}
              </option>
              {files
                .filter((f) => filesWithEmbeddings.includes(f.file_id))
                .map((f) => (
                  <option key={f.file_id} value={f.file_id}>
                    {f.file_name}
                  </option>
                ))}
            </select>
            {!checkingEmbeddings &&
              filesWithEmbeddings.length === 0 &&
              files.length > 0 && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Generate embeddings for files first in the Files page
                </p>
              )}
          </div>
          <form
            onSubmit={handleSubmitFile(onFileSearch)}
            className="sm:col-span-2 grid grid-cols-1 items-end gap-3 sm:grid-cols-[1fr_auto_auto]"
          >
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">
                Query
              </label>
              <input
                type="text"
                {...registerFile("query", { required: true })}
                placeholder="Search within selected file…"
                className="w-full rounded-md border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">
                Top K
              </label>
              <input
                type="number"
                min={1}
                max={20}
                {...registerFile("top_k", { valueAsNumber: true })}
                className="w-full rounded-md border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
            <button
              type="submit"
              className="h-10 rounded-md bg-primary px-4 text-sm text-primary-foreground transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {loadingFile ? "Searching…" : "Search"}
            </button>
          </form>
        </div>

        <div className="mt-4">
          <AnimatePresence initial={false}>
            {matchesFile.length === 0 ? (
              <p className="text-sm text-muted-foreground">No results yet.</p>
            ) : (
              <ul className="grid gap-2">
                {matchesFile.map((m, i) => (
                  <motion.li
                    key={i}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-md border border-zinc-800 bg-zinc-950/60 p-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-sm">
                        <span className="text-muted-foreground">page_id:</span>{" "}
                        <span className="font-mono">{m.page_id}</span>
                      </div>
                      <div className="text-sm">
                        <span className="text-muted-foreground">score:</span>{" "}
                        <span className="font-mono">{m.score.toFixed(3)}</span>
                      </div>
                    </div>
                    {m.ocr ? (
                      <p className="mt-2 text-pretty text-sm text-muted-foreground">
                        {m.ocr}
                      </p>
                    ) : null}
                    <div className="mt-2 flex items-center gap-2">
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(m.page_id);
                          toast({
                            title: "Copied page_id",
                            description: m.page_id,
                          });
                        }}
                        className="rounded-md px-3 py-1 text-sm text-foreground transition hover:bg-zinc-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        Copy page_id
                      </button>
                    </div>
                  </motion.li>
                ))}
              </ul>
            )}
          </AnimatePresence>
        </div>
      </section>
    </motion.div>
  );
}
