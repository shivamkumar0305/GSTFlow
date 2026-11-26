"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import RequireAuth from "@/components/RequireAuth";
import { apiFetch } from "@/lib/api";
import type { Dashboard, SupplierAnalytics } from "@/lib/types";
import { DISCREPANCY_LABELS } from "@/lib/types";

function Metric({ label, value, accent = "" }: { label: string; value: string | number; accent?: string }) {
  return <div className={`metric-card ${accent}`}><p className="metric-label">{label}</p><p className="metric-value">{value}</p></div>;
}

function DashboardContent() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [suppliers, setSuppliers] = useState<SupplierAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Dashboard>("/api/dashboard/").then(setData).catch(() => setError("Could not load dashboard."));
    apiFetch<SupplierAnalytics>("/api/reconcile/suppliers/").then(setSuppliers).catch(() => undefined);
  }, []);

  if (error) return <div className="portal-page"><p className="status-banner error">{error}</p></div>;
  if (!data) return <div className="portal-page"><p className="status-banner">Loading dashboard information…</p></div>;

  return (
    <div className="portal-page">
      <div className="page-heading">
        <div>
          <p className="page-eyebrow">GSTFlow / Overview</p>
          <h1>Reconciliation dashboard</h1>
          <p>Review invoice matching activity, outstanding exceptions, and tax amounts that may need attention.</p>
        </div>
        <Link href="/upload" className="primary-button">Start a reconciliation</Link>
      </div>

      <div className="mb-5 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Metric label="Purchase invoices" value={data.total_purchase_invoices} />
        <Metric label="GSTR-2A/2B invoices" value={data.total_statement_invoices} />
        <Metric label="Matched" value={data.total_matched} accent="accent-green" />
        <Metric label="Flagged" value={data.total_flagged} accent="accent-saffron" />
      </div>
      <div className="mb-8">
        <Metric label="Tax amount linked to flagged records" value={`₹${data.total_itc_at_risk.toLocaleString("en-IN")}`} accent="accent-saffron" />
        <p className="metric-note mt-1">Review indicator only · not a decision about ITC eligibility</p>
      </div>

      {Object.keys(data.discrepancies_by_type).length > 0 && (
        <section className="portal-panel mb-8">
          <h2 className="section-heading"><span>Exceptions by category</span></h2>
          <ul className="flex flex-col gap-1 text-sm">
            {Object.entries(data.discrepancies_by_type).map(([type, count]) => (
              <li key={type} className="flex justify-between border-b border-slate-100 py-2.5">
                <span className="text-slate-700">{DISCREPANCY_LABELS[type as keyof typeof DISCREPANCY_LABELS] ?? type}</span>
                <span className="font-semibold text-slate-900">{count}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {suppliers && suppliers.suppliers.length > 0 && (
        <section className="portal-panel mb-8">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="section-heading mb-0"><span>Supplier review list</span></h2>
            <span className="text-xs text-slate-500">Ordered by flagged tax amount</span>
          </div>
          <div className="overflow-x-auto">
            <table className="data-table min-w-[680px] text-left">
              <thead><tr><th>Supplier</th><th>GSTIN</th><th className="text-right">Flags</th><th className="text-right">High risk</th><th className="text-right">Tax amount</th></tr></thead>
              <tbody>{suppliers.suppliers.map((supplier) => (
                <tr key={supplier.supplier_gstin}>
                  <td className="font-semibold text-slate-900">{supplier.supplier_name}</td>
                  <td className="font-mono text-xs">{supplier.supplier_gstin}</td>
                  <td className="text-right">{supplier.flagged_count}</td>
                  <td className="text-right">{supplier.high_risk_count}</td>
                  <td className="text-right font-semibold">₹{supplier.itc_at_risk.toLocaleString("en-IN")}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </section>
      )}

      {data.latest_run ? (
        <div className="status-banner flex flex-wrap items-center justify-between gap-3">
          <span>Latest processed period: {data.latest_run.period || "not specified"}</span>
          <Link href={`/runs/${data.latest_run.id}`} className="font-bold underline underline-offset-2">View run details</Link>
        </div>
      ) : (
        <div className="status-banner">No completed reconciliation run yet. <Link href="/upload" className="font-bold underline">Upload both files to begin.</Link></div>
      )}
    </div>
  );
}

export default function HomePage() {
  return <RequireAuth><DashboardContent /></RequireAuth>;
}
