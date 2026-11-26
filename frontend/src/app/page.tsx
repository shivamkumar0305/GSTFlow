"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
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

function LandingPage() {
  return (
    <main className="landing-page">
      <section className="landing-hero">
        <div className="landing-copy">
          <p className="landing-kicker"><span aria-hidden="true" /> GST invoice reconciliation · Student project prototype</p>
          <h1>Make invoice reconciliation easier to review.</h1>
          <p className="landing-lede">
            Compare your purchase register with a GST statement, find likely invoice matches,
            and bring differences into one clear review workflow.
          </p>
          <div className="landing-actions">
            <Link href="/register" className="primary-button">Create your workspace <span aria-hidden="true">→</span></Link>
            <Link href="/login" className="landing-signin">Sign in <span aria-hidden="true">↗</span></Link>
          </div>
          <p className="landing-note">Designed for assisted review. You remain in control of every decision.</p>
        </div>
        <div className="landing-visual" aria-label="Illustration of invoice reconciliation">
          <div className="visual-topline"><span className="visual-dot" /> Reconciliation overview <span className="visual-period">PERIOD · MONTHLY</span></div>
          <div className="visual-flow">
            <div className="visual-file"><span className="file-icon">PR</span><span><b>Purchase register</b><small>Your invoice records</small></span><span className="file-check">✓</span></div>
            <div className="visual-connector"><span /> <i>Compare</i> <span /></div>
            <div className="visual-file"><span className="file-icon file-icon-green">GST</span><span><b>GST statement</b><small>Supplier reported records</small></span><span className="file-check">✓</span></div>
          </div>
          <div className="visual-result">
            <div className="result-icon">✓</div>
            <div><b>Review the results</b><small>Matches, differences and missing records</small></div>
            <span className="result-arrow">→</span>
          </div>
          <div className="visual-caption"><span>01 · Upload</span><span>02 · Compare</span><span>03 · Review</span></div>
        </div>
        <div className="hero-watermark" aria-hidden="true">GST</div>
      </section>

      <section className="landing-proof" aria-label="Project principles">
        <div><span className="proof-symbol">01</span><span><b>Rule based matching</b><small>Compare invoice details with transparent criteria.</small></span></div>
        <div><span className="proof-symbol">02</span><span><b>Exceptions brought forward</b><small>Focus review on records that need attention.</small></span></div>
        <div><span className="proof-symbol">03</span><span><b>Human led decisions</b><small>Use results as review indicators, not tax advice.</small></span></div>
      </section>

      <section className="landing-how">
        <div className="landing-section-title"><p className="page-eyebrow">A straightforward workflow</p><h2>From two files to a focused review.</h2><p>GSTFlow helps organize the comparison so discrepancies are easier to inspect.</p></div>
        <div className="landing-steps">
          <article><span>1</span><h3>Upload both records</h3><p>Add a purchase register and the corresponding GST statement in a supported format.</p></article>
          <article><span>2</span><h3>Compare invoice details</h3><p>The reconciliation pipeline looks for exact and similar records, then flags differences.</p></article>
          <article><span>3</span><h3>Review and investigate</h3><p>Inspect match explanations and exceptions before taking any action outside the app.</p></article>
        </div>
      </section>
      <p className="landing-disclaimer">Academic prototype only. GSTFlow is not connected to GSTN, does not file returns, and does not determine ITC eligibility.</p>
    </main>
  );
}

export default function HomePage() {
  const { business, loading } = useAuth();
  if (loading) return <div className="portal-page"><p className="status-banner">Loading GSTFlow…</p></div>;
  return business ? <DashboardContent /> : <LandingPage />;
}
