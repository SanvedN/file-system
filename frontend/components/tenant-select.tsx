"use client";

import * as React from "react";
import { useTenants } from "@/lib/swr";
import { cn } from "@/lib/utils";

type Props = {
  value?: string;
  onChange: (tenantId: string) => void;
  placeholder?: string;
  className?: string;
};

export function TenantSelect({
  value,
  onChange,
  placeholder = "Select tenant",
  className,
}: Props) {
  const { data, isLoading } = useTenants();
  const [open, setOpen] = React.useState(false);
  const btnRef = React.useRef<HTMLButtonElement | null>(null);
  const [highlight, setHighlight] = React.useState<number>(-1);

  const tenants = data || [];

  React.useEffect(() => {
    if (!open) setHighlight(-1);
  }, [open]);

  function onKeyDown(e: React.KeyboardEvent) {
    if (!open) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => Math.min(h + 1, tenants.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter" && highlight >= 0) {
      e.preventDefault();
      onChange(tenants[highlight].tenant_id);
      setOpen(false);
      btnRef.current?.focus();
    } else if (e.key === "Escape") {
      setOpen(false);
      btnRef.current?.focus();
    }
  }

  return (
    <div className={cn("relative", className)}>
      <button
        ref={btnRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="inline-flex w-full items-center justify-between gap-2 rounded-md border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-sm text-foreground backdrop-blur-md transition hover:bg-zinc-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="truncate">
          {isLoading
            ? "Loading tenants…"
            : value
            ? tenants.find((t) => t.tenant_id === value)?.tenant_code
            : placeholder}
        </span>
        <span
          aria-hidden
          className="i-lucide:chevrons-up-down h-4 w-4 opacity-70"
        />
      </button>
      {open ? (
        <ul
          role="listbox"
          tabIndex={-1}
          onKeyDown={onKeyDown}
          className="absolute z-[100] mt-2 max-h-64 w-[min(22rem,80vw)] overflow-auto rounded-md border border-zinc-800 bg-zinc-900/95 p-1 shadow-2xl backdrop-blur-md"
        >
          {tenants.length === 0 ? (
            <li className="px-3 py-2 text-sm text-muted-foreground">
              No tenants
            </li>
          ) : (
            tenants.map((t, idx) => {
              const active = value === t.tenant_id;
              const hl = highlight === idx;
              return (
                <li key={t.tenant_id}>
                  <button
                    role="option"
                    aria-selected={active}
                    onMouseEnter={() => setHighlight(idx)}
                    onClick={() => {
                      onChange(t.tenant_id);
                      setOpen(false);
                      btnRef.current?.focus();
                    }}
                    className={cn(
                      "flex w-full items-center justify-between rounded-sm px-3 py-2 text-left text-sm transition",
                      hl ? "bg-zinc-800/70" : "hover:bg-zinc-800/50",
                      active ? "text-foreground" : "text-muted-foreground"
                    )}
                  >
                    <span className="truncate">{t.tenant_code}</span>
                    {active ? (
                      <span aria-hidden className="i-lucide:check h-4 w-4" />
                    ) : null}
                  </button>
                </li>
              );
            })
          )}
        </ul>
      ) : null}
    </div>
  );
}
