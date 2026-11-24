"use client";

import { use, useEffect, useState } from "react";
import RequireAuth from "@/components/RequireAuth";
import { apiFetch } from "@/lib/api";
import type { AuditEvent, Discrepancy, DiscrepancyType, Paginated, ReconciliationRun, ReviewStatus } from "@/lib/types";
import { DISCREPANCY_LABELS } from "@/lib/types";

const TYPE_FILTERS: (DiscrepancyType | "all")[] = [
  "all",
  "missing_in_2a",
  "missing_in_books",
  "value_mismatch",
  "duplicate",
  "gstin_mismatch",
  "date_mismatch",
  "fuzzy_match",
];

const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
  open: "Open",
  in_review: "In review",
  supplier_contacted: "Supplier contacted",
  resolved: "Resolved",
  ignored: "Ignored",
};

function RunDetail({ runId }: { runId: string }) {
  const [run, setRun] = useState<ReconciliationRun | null>(null);
  const [discrepancies, setDiscrepancies] = useState<Discrepancy[]>([]);
  const [filter, setFilter] = useState<DiscrepancyType | "all">("all");
  const [loadingList, setLoadingList] = useState(false);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [auditEvents, setAuditEvents] = useState<Record<number, AuditEvent[]>>({});

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

  async function updateReview(d: Discrepancy, reviewStatus: ReviewStatus) {
    const updated = await apiFetch<Discrepancy>(`/api/reconcile/discrepancies/${d.id}/`, {
      method: "PATCH",
      body: { review_status: reviewStatus, resolution_note: notes[d.id] ?? d.resolution_note },
    });
    setDiscrepancies((prev) => prev.map((x) => (x.id === d.id ? updated : x)));
  }

  async function loadAudit(d: Discrepancy) {
    if (auditEvents[d.id]) {
      setAuditEvents((current) => {
        const next = { ...current };
        delete next[d.id];
        return next;
      });
      return;
    }
    const events = await apiFetch<Paginated<AuditEvent>>(`/api/reconcile/discrepancies/${d.id}/audit/`);
    setAuditEvents((current) => ({ ...current, [d.id]: events.results }));
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
              <div key={d.id} className="border border-slate-200 bg-white p-4">
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
                    <div className="mt-2 flex flex-wrap gap-2 text-xs">
                      <span className={`rounded-full px-2 py-0.5 font-medium ${
                        d.risk_level === "high"
                          ? "bg-red-100 text-red-700"
                          : d.risk_level === "medium"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-slate-100 text-slate-600"
                      }`}>
                        {d.risk_level} risk ({d.risk_score}/100)
                      </span>
                      {d.discrepancy_type === "fuzzy_match" && (
                        <span className="rounded-full bg-blue-100 px-2 py-0.5 font-medium text-blue-700">
                          {d.confidence_score}% match confidence
                        </span>
                      )}
                    </div>
                    {Number(d.value_at_risk) > 0 && (
                      <p className="mt-1 text-xs text-slate-500">
                        Value at risk: ₹{Number(d.value_at_risk).toLocaleString("en-IN")}
                      </p>
                    )}
                  </div>
                  <select
                    aria-label="Review status"
                    value={d.review_status}
                    onChange={(event) => void updateReview(d, event.target.value as ReviewStatus)}
                    className="shrink-0 border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-700"
                  >
                    {Object.entries(REVIEW_STATUS_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </div>
                <div className="mt-3 flex flex-col gap-2 border-t border-slate-100 pt-3 sm:flex-row">
                  <input
                    value={notes[d.id] ?? d.resolution_note}
                    onChange={(event) => setNotes((current) => ({ ...current, [d.id]: event.target.value }))}
                    placeholder="Add a review note"
                    className="min-w-0 flex-1 border border-slate-300 px-2 py-1.5 text-xs"
                  />
                  <button
                    onClick={() => void updateReview(d, d.review_status)}
                    className="border border-slate-300 px-3 py-1.5 text-xs text-slate-700"
                  >
                    Save note
                  </button>
                  <button onClick={() => void loadAudit(d)} className="text-left text-xs text-slate-600 underline">
                    {auditEvents[d.id] ? "Hide history" : "Review history"}
                  </button>
                </div>
                {auditEvents[d.id] && (
                  <ul className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-500">
                    {auditEvents[d.id].length === 0 ? (
                      <li>No review activity yet.</li>
                    ) : auditEvents[d.id].map((event) => (
                      <li key={event.id} className="py-1">
                        {new Date(event.created_at).toLocaleString()} - {event.actor_email}: {event.detail}
                      </li>
                    ))}
                  </ul>
                )}
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
