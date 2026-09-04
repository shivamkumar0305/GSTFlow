"use client";

import { use, useEffect, useState } from "react";
import RequireAuth from "@/components/RequireAuth";
import { apiFetch } from "@/lib/api";
import type { Discrepancy, DiscrepancyType, Paginated, ReconciliationRun } from "@/lib/types";
import { DISCREPANCY_LABELS } from "@/lib/types";

const TYPE_FILTERS: (DiscrepancyType | "all")[] = [
  "all",
  "missing_in_2a",
  "missing_in_books",
  "value_mismatch",
  "duplicate",
  "gstin_mismatch",
  "date_mismatch",
];

function RunDetail({ runId }: { runId: string }) {
  const [run, setRun] = useState<ReconciliationRun | null>(null);
  const [discrepancies, setDiscrepancies] = useState<Discrepancy[]>([]);
  const [filter, setFilter] = useState<DiscrepancyType | "all">("all");
  const [loadingList, setLoadingList] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;

    async function loadRun() {
      const data = await apiFetch<ReconciliationRun>(`/api/reconcile/${runId}/`);
      if (cancelled) return;
      setRun(data);
      if (data.status === "processing") {
        pollTimer = setTimeout(loadRun, 1200);
      }
    }

    void loadRun();

    return () => {
      cancelled = true;
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [runId]);

  useEffect(() => {
    if (!run || run.status !== "done") return;
    let cancelled = false;

    async function loadDiscrepancies() {
      setLoadingList(true);
      try {
        const qs = filter === "all" ? "" : `?discrepancy_type=${filter}`;
        const data = await apiFetch<Paginated<Discrepancy>>(
          `/api/reconcile/${runId}/discrepancies/${qs}`
        );
        if (!cancelled) setDiscrepancies(data.results);
      } finally {
        if (!cancelled) setLoadingList(false);
      }
    }

    queueMicrotask(() => void loadDiscrepancies());

    return () => {
      cancelled = true;
    };
  }, [run, runId, filter]);

  async function toggleResolved(d: Discrepancy) {
    const updated = await apiFetch<Discrepancy>(`/api/reconcile/discrepancies/${d.id}/`, {
      method: "PATCH",
      body: { resolved: !d.resolved },
    });
    setDiscrepancies((prev) => prev.map((x) => (x.id === d.id ? updated : x)));
  }

  if (!run) return <p className="px-6 py-8 text-slate-500">Loading...</p>;

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-2xl font-semibold">Reconciliation Run #{run.id}</h1>
      <p className="mt-1 text-sm text-slate-500">Period: {run.period || "—"}</p>

      {run.status === "processing" && (
        <p className="mt-4 text-slate-500">Reconciling... this updates automatically.</p>
      )}
      {run.status === "failed" && (
        <p className="mt-4 text-red-600">Reconciliation failed: {run.error_message}</p>
      )}

      {run.status === "done" && (
        <>
          <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatCard label="Books invoices" value={run.total_books_invoices} />
            <StatCard label="2A/2B invoices" value={run.total_statement_invoices} />
            <StatCard label="Matched" value={run.matched_count} />
            <StatCard label="Flagged" value={run.flagged_count} />
          </div>
          <div className="mt-4">
            <StatCard label="ITC at risk (₹)" value={Number(run.itc_at_risk_value).toLocaleString("en-IN")} />
          </div>

          <div className="mt-8 flex flex-wrap gap-2">
            {TYPE_FILTERS.map((t) => (
              <button
                key={t}
                onClick={() => setFilter(t)}
                className={`rounded-full px-3 py-1 text-sm ${
                  filter === t
                    ? "bg-slate-900 text-white"
                    : "bg-white text-slate-600 border border-slate-300"
                }`}
              >
                {t === "all" ? "All" : DISCREPANCY_LABELS[t]}
              </button>
            ))}
          </div>

          <div className="mt-4 flex flex-col gap-3">
            {loadingList && <p className="text-sm text-slate-500">Loading...</p>}
            {!loadingList && discrepancies.length === 0 && (
              <p className="text-sm text-slate-500">No discrepancies of this type.</p>
            )}
            {discrepancies.map((d) => (
              <div key={d.id} className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                      {DISCREPANCY_LABELS[d.discrepancy_type]}
                    </span>
                    <p className="mt-2 text-sm font-medium">
                      {d.books_invoice?.invoice_number || d.statement_invoice?.invoice_number}
                      {" — "}
                      {d.books_invoice?.supplier_gstin || d.statement_invoice?.supplier_gstin}
                    </p>
                    <p className="mt-1 text-sm text-slate-600">{d.ai_explanation || d.detail}</p>
                    {Number(d.value_at_risk) > 0 && (
                      <p className="mt-1 text-xs text-slate-500">
                        Value at risk: ₹{Number(d.value_at_risk).toLocaleString("en-IN")}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => toggleResolved(d)}
                    className={`shrink-0 rounded-md border px-3 py-1.5 text-xs ${
                      d.resolved
                        ? "border-green-300 bg-green-50 text-green-700"
                        : "border-slate-300 text-slate-600"
                    }`}
                  >
                    {d.resolved ? "Resolved" : "Mark resolved"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

export default function RunPage(props: PageProps<"/runs/[id]">) {
  const { id } = use(props.params);
  return (
    <RequireAuth>
      <RunDetail runId={id} />
    </RequireAuth>
  );
}
