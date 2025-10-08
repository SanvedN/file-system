"use client";
import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useForm } from "react-hook-form";
import { useTenants, mutate } from "@/lib/swr";
import { createTenant, deleteTenant, getTenant, patchTenant } from "@/lib/api";
import type { Tenant } from "@/lib/types";
import { SWR_KEYS } from "@/lib/constants";
import { toast } from "@/hooks/use-toast";
import { JsonEditor } from "@/components/json-editor";

type FormValues = { tenant_code: string };

// Normalize backend data → frontend-friendly tenant object
function normalizeTenant(raw: any): Tenant {
  if (!raw) return {} as Tenant;
  return {
    tenant_id: raw.tenant_id || raw.id || "",
    tenant_code: raw.tenant_code || raw.code || "",
    configuration: raw.configuration || {},
    created_at: raw.created_at || raw.created || "",
    updated_at: raw.updated_at || raw.updated || "",
  };
}

export default function TenantsPage() {
  const { data, isLoading } = useTenants();
  const tenants = (data || []).map(normalizeTenant);

  const [cfgOpen, setCfgOpen] = React.useState(false);
  const [cfgTenant, setCfgTenant] = React.useState<Tenant | null>(null);
  const [cfgObj, setCfgObj] = React.useState<Record<string, any>>({});
  const [cfgError, setCfgError] = React.useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>();

  const onSubmit = async (values: FormValues) => {
    try {
      const created = await createTenant(values.tenant_code);
      await mutate(SWR_KEYS.TENANTS_LIST);
      toast({ title: "Tenant created", description: created.tenant_code });
      reset();
    } catch (err: any) {
      toast({
        title: "Failed to create tenant",
        description: err.message || "Unknown error",
        variant: "destructive",
      });
    }
  };

  const handleEditTenant = async (tenantCode: string) => {
    try {
      const raw = await getTenant(tenantCode);
      const full = normalizeTenant(raw);
      setCfgTenant(full);
      setCfgObj(full.configuration || {});
      setCfgError(null);
      setCfgOpen(true);
    } catch (err: any) {
      toast({
        title: "Failed to load tenant configuration",
        description: err.message || "Unknown error",
        variant: "destructive",
      });
    }
  };

  const handleSaveConfig = async () => {
    if (!cfgTenant) return;
    if (cfgError) {
      toast({
        title: "Fix JSON errors",
        description: cfgError,
        variant: "destructive",
      });
      return;
    }
    try {
      await patchTenant(cfgTenant.tenant_code, cfgObj);
      await mutate(SWR_KEYS.TENANTS_LIST);
      toast({
        title: "Configuration updated",
        description: cfgTenant.tenant_code,
      });
      setCfgOpen(false);
    } catch (err: any) {
      toast({
        title: "Failed to update configuration",
        description: err.message || "Unknown error",
        variant: "destructive",
      });
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="grid gap-6"
    >
      {/* ---------- Create Tenant ---------- */}
      <section className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 backdrop-blur-md">
        <h2 className="text-pretty text-lg font-semibold">Create tenant</h2>
        <p className="text-sm text-muted-foreground">
          Tenant code must match pattern: {"^[A-Z][A-Z0-9]*$"}
        </p>

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="mt-3 flex flex-col items-start gap-3 sm:flex-row"
        >
          <input
            {...register("tenant_code", {
              required: "Tenant code is required",
              pattern: {
                value: /^[A-Z][A-Z0-9]*$/,
                message: "Use pattern: ^[A-Z][A-Z0-9]*$",
              },
            })}
            maxLength={32}
            placeholder="ACME"
            className="w-40 rounded-md border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-invalid={!!errors.tenant_code}
          />
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center rounded-md bg-primary px-4 py-2 text-primary-foreground transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
          >
            {isSubmitting ? "Creating…" : "Create"}
          </button>
          {errors.tenant_code ? (
            <span className="text-sm text-destructive">
              {errors.tenant_code.message}
            </span>
          ) : null}
        </form>
      </section>

      {/* ---------- Tenants Table ---------- */}
      <section className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 backdrop-blur-md">
        <h2 className="text-pretty text-lg font-semibold">Tenants</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full table-fixed border-collapse">
            <thead>
              <tr className="text-left text-sm text-muted-foreground">
                <th className="w-40 px-3 py-2">Code</th>
                <th className="w-64 px-3 py-2">Created</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <tr key={i} className="border-b border-zinc-800/60">
                    <td className="px-3 py-3">
                      <div className="h-5 w-16 animate-pulse rounded bg-zinc-800/80" />
                    </td>
                    <td className="px-3 py-3">
                      <div className="h-5 w-40 animate-pulse rounded bg-zinc-800/80" />
                    </td>
                    <td className="px-3 py-3">
                      <div className="h-8 w-20 animate-pulse rounded bg-zinc-800/80" />
                    </td>
                  </tr>
                ))
              ) : tenants.length === 0 ? (
                <tr>
                  <td
                    colSpan={3}
                    className="px-3 py-6 text-center text-sm text-muted-foreground"
                  >
                    No tenants yet. Create your first tenant above.
                  </td>
                </tr>
              ) : (
                tenants.map((t) => (
                  <motion.tr
                    key={t.tenant_id || t.tenant_code}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="border-b border-zinc-800/60"
                  >
                    <td className="px-3 py-3">{t.tenant_code}</td>
                    <td className="px-3 py-3 text-sm text-muted-foreground">
                      {t.created_at
                        ? new Date(t.created_at).toLocaleString()
                        : "—"}
                    </td>
                    <td className="px-3 py-3">
                      <button
                        onClick={async () => {
                          if (!confirm(`Delete tenant ${t.tenant_code}?`))
                            return;
                          try {
                            await deleteTenant(t.tenant_code);
                            await mutate(SWR_KEYS.TENANTS_LIST);
                            toast({
                              title: "Tenant deleted",
                              description: t.tenant_code,
                            });
                          } catch (err: any) {
                            toast({
                              title: "Failed to delete tenant",
                              description: err.message || "Unknown error",
                              variant: "destructive",
                            });
                          }
                        }}
                        className="rounded-md px-3 py-2 text-sm text-destructive transition hover:bg-zinc-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        Delete
                      </button>
                      <button
                        onClick={() => handleEditTenant(t.tenant_code)}
                        className="ml-2 rounded-md px-3 py-2 text-sm text-foreground transition hover:bg-zinc-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        Edit config
                      </button>
                    </td>
                  </motion.tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ---------- Edit Tenant Config Modal ---------- */}
      <AnimatePresence>
        {cfgOpen ? (
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
              onClick={() => setCfgOpen(false)}
              aria-hidden
            />
            <motion.div
              initial={{ y: 16, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 16, opacity: 0 }}
              className="relative z-10 w-full max-w-3xl rounded-lg border border-zinc-800 bg-zinc-950/80 p-5 backdrop-blur-xl"
            >
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-lg font-semibold">
                  Edit tenant config — {cfgTenant?.tenant_code}
                </h3>
                <button
                  onClick={() => setCfgOpen(false)}
                  className="rounded-md px-2 py-1 text-sm text-muted-foreground transition hover:bg-zinc-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  Close
                </button>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <div className="mb-2 text-sm text-muted-foreground">
                    Current
                  </div>
                  <pre className="h-80 overflow-auto rounded-md border border-zinc-800 bg-zinc-900/60 p-3 text-xs">
                    {JSON.stringify(cfgTenant?.configuration || {}, null, 2)}
                  </pre>
                </div>
                <div>
                  <div className="mb-2 text-sm text-muted-foreground">
                    New configuration (JSON)
                  </div>
                  <JsonEditor
                    value={cfgObj}
                    onChange={setCfgObj}
                    onError={setCfgError}
                  />
                </div>
              </div>
              <div className="mt-4 flex justify-end gap-2">
                <button
                  onClick={() => setCfgOpen(false)}
                  className="rounded-md px-4 py-2 text-sm text-muted-foreground transition hover:bg-zinc-800/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveConfig}
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
