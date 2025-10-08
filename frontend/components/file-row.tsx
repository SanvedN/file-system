"use client";

import * as React from "react";
import { motion } from "framer-motion";
import {
  getDownloadUrl,
  deleteFile,
  updateFile,
  getEmbeddings,
  generateEmbeddings,
  searchFileEmbeddings,
} from "@/lib/api";
import type { FileItem } from "@/lib/types";
import { mutate } from "@/lib/swr";
import { SWR_KEYS } from "@/lib/constants";
import { toast } from "@/hooks/use-toast";

function formatBytes(bytes: number) {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${Number.parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${
    sizes[i]
  }`;
}

export function FileRow({
  tenantId,
  item,
  onOpenMetadata,
}: {
  tenantId: string;
  item: FileItem;
  onOpenMetadata: (file: FileItem) => void;
}) {
  const [tag, setTag] = React.useState(item.tag || "");
  const [saving, setSaving] = React.useState(false);
  const [embState, setEmbState] = React.useState<
    "unknown" | "available" | "none" | "loading"
  >("unknown");
  const [q, setQ] = React.useState("");
  const [matches, setMatches] = React.useState<any[]>([]);

  async function saveTag() {
    if (tag === (item.tag || "")) return;
    const key = SWR_KEYS.FILES_LIST(tenantId);
    const optimistic = (prev: { files: FileItem[] } | undefined) =>
      prev
        ? {
            files: prev.files.map((f) =>
              f.file_id === item.file_id ? { ...f, tag } : f
            ),
          }
        : prev;
    try {
      setSaving(true);
      await mutate(key, optimistic, false);
      await updateFile(tenantId, item.file_id, { tag: tag || undefined });
      await mutate(key);
      toast({ title: "Tag updated", description: `${item.file_name}` });
    } catch {
      await mutate(key); // rollback by revalidation
    } finally {
      setSaving(false);
    }
  }

  React.useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const r = await getEmbeddings(tenantId, item.file_id);
        if (!mounted) return;
        setEmbState((r.pages?.length || 0) > 0 ? "available" : "none");
      } catch {
        if (!mounted) return;
        setEmbState("none");
      }
    })();
    return () => {
      mounted = false;
    };
  }, [tenantId, item.file_id]);

  async function onGenerate() {
    if (embState === "available") {
      toast({ title: "Embeddings already exist", description: item.file_name });
      return;
    }
    try {
      setEmbState("loading");
      const result = await generateEmbeddings(tenantId, item.file_id);
      setEmbState("available");
      toast({
        title: "Embeddings generated successfully",
        description: `Processed ${result.pages_processed} pages for ${item.file_name}`,
      });
    } catch (error: any) {
      setEmbState("none");
      const message =
        error?.response?.data?.detail ||
        error?.message ||
        "Failed to generate embeddings";
      toast({
        title: "Embeddings generation failed",
        description: message,
        variant: "destructive",
      });
    }
  }

  async function onSearchFile() {
    if (!q.trim()) return;
    try {
      const res = await searchFileEmbeddings(
        tenantId,
        item.file_id,
        q.trim(),
        5
      );
      setMatches(res.matches || []);
      if ((res.matches || []).length === 0) {
        toast({
          title: "No matches found",
          description: "No embeddings found for this file or query",
        });
      }
    } catch (error: any) {
      const message =
        error?.response?.data?.detail || error?.message || "Search failed";
      toast({
        title: "Search failed",
        description: message,
        variant: "destructive",
      });
      setMatches([]);
    }
  }

  return (
    <motion.tr
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.18 }}
      className="border-b border-zinc-800/60"
    >
      <td className="px-3 py-3 align-middle">
        <div className="text-sm">{item.file_name}</div>
        <div className="text-xs text-muted-foreground">
          {new Date(item.created_at || Date.now()).toLocaleString()}
        </div>
      </td>
      <td className="px-3 py-3 align-middle text-sm text-muted-foreground">
        {item.media_type}
      </td>
      <td className="px-3 py-3 align-middle text-sm text-muted-foreground">
        {formatBytes(item.file_size_bytes)}
      </td>
      <td className="px-3 py-3 align-middle">
        <input
          className="w-40 rounded-md border border-zinc-800 bg-zinc-900/60 px-2 py-1 text-sm text-foreground backdrop-blur-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          defaultValue={tag}
          onChange={(e) => setTag(e.target.value)}
          onBlur={saveTag}
          disabled={saving}
          placeholder="Add tag"
          aria-label={`Tag for ${item.file_name}`}
        />
      </td>
      <td className="px-3 py-3 align-middle">
        <button
          onClick={() => onOpenMetadata(item)}
          className="rounded-md px-3 py-1 text-sm text-foreground transition hover:bg-zinc-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Metadata
        </button>
      </td>
      <td className="px-3 py-3 align-middle">
        <div className="flex items-center gap-2">
          <a
            href={getDownloadUrl(tenantId, item.file_id, true)}
            target="_blank"
            rel="noreferrer"
            className="rounded-md bg-primary px-3 py-1 text-sm text-primary-foreground transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Open
          </a>
          <a
            href={getDownloadUrl(tenantId, item.file_id, false)}
            className="rounded-md px-3 py-1 text-sm text-foreground transition hover:bg-zinc-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Download
          </a>
          <button
            onClick={async () => {
              if (!confirm(`Delete ${item.file_name}?`)) return;
              const key = SWR_KEYS.FILES_LIST(tenantId);
              const optimistic = (prev: { files: FileItem[] } | undefined) =>
                prev
                  ? {
                      files: prev.files.filter(
                        (f) => f.file_id !== item.file_id
                      ),
                    }
                  : prev;
              try {
                await mutate(key, optimistic, false);
                await deleteFile(tenantId, item.file_id);
                await mutate(key);
                toast({ title: "Deleted", description: item.file_name });
              } catch {
                await mutate(key); // rollback
              }
            }}
            className="rounded-md px-3 py-1 text-sm text-destructive transition hover:bg-zinc-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Delete
          </button>
          <button
            onClick={onGenerate}
            disabled={embState === "loading"}
            className="rounded-md px-3 py-1 text-sm text-foreground transition hover:bg-zinc-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {embState === "available"
              ? "Embeddings ✓"
              : embState === "loading"
              ? "Generating…"
              : "Generate"}
          </button>
        </div>
        <div className="mt-2 flex items-center gap-2">
          <input
            placeholder="Search this file"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-48 rounded-md border border-zinc-800 bg-zinc-900/60 px-2 py-1 text-sm"
          />
          <button
            onClick={onSearchFile}
            className="rounded-md px-3 py-1 text-sm text-foreground transition hover:bg-zinc-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Search
          </button>
        </div>
        {matches.length > 0 && (
          <div className="mt-2 space-y-1 text-xs text-muted-foreground">
            {matches.map((m, i) => (
              <div
                key={i}
                className="rounded border border-zinc-800 bg-zinc-900/40 p-2"
              >
                <div>
                  Page {m.page_id} • Score {m.score?.toFixed?.(3)}
                </div>
                {m.ocr && (
                  <div className="mt-1 line-clamp-2 text-foreground">
                    {m.ocr}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </td>
    </motion.tr>
  );
}
