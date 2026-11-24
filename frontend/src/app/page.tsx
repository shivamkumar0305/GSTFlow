"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import RequireAuth from "@/components/RequireAuth";
import { apiFetch } from "@/lib/api";
import type { Dashboard, SupplierAnalytics } from "@/lib/types";
import { DISCREPANCY_LABELS } from "@/lib/types";

function Card({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function DashboardContent() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [suppliers, setSuppliers] = useState<SupplierAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<Dashboard>("/api/dashboard/")
      .then(setData)
      .catch(() => setError("Could not load dashboard."));
    apiFetch<SupplierAnalytics>("/api/reconcile/suppliers/").then(setSuppliers).catch(() => undefined);
  }, []);

  if (error) return <p className="px-6 py-8 text-red-600">{error}</p>;
  if (!data) return <p className="px-6 py-8 text-slate-500">Loading...</p>;

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <Link href="/upload" className="rounded-md bg-slate-900 px-4 py-2 text-sm text-white">
          Upload & Reconcile
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card label="Purchase invoices" value={data.total_purchase_invoices} />
        <Card label="GSTR-2A/2B invoices" value={data.total_statement_invoices} />
        <Card label="Matched" value={data.total_matched} />
        <Card label="Flagged" value={data.total_flagged} />
      </div>

      <div className="mt-4">
        <Card label="ITC at risk (₹)" value={data.total_itc_at_risk.toLocaleString("en-IN")} />
      </div>

      {Object.keys(data.discrepancies_by_type).length > 0 && (
        <div className="mt-8 rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-3 font-medium">Discrepancies by type</h2>
          <ul className="flex flex-col gap-2 text-sm">
            {Object.entries(data.discrepancies_by_type).map(([type, count]) => (
              <li key={type} className="flex justify-between border-b border-slate-100 pb-1">
                <span>{DISCREPANCY_LABELS[type as keyof typeof DISCREPANCY_LABELS] ?? type}</span>
                <span className="font-medium">{count}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {suppliers && suppliers.suppliers.length > 0 && (
        <div className="mt-8 border-t border-slate-200 pt-6">
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="font-medium text-slate-900">Supplier risk watchlist</h2>
            <span className="text-xs text-slate-500">Ranked by ITC at risk</span>
          </div>
          <div className="overflow-x-auto border border-slate-200 bg-white">
            <table className="w-full min-w-[620px] text-left text-sm">
              <thead className="bg-slate-100 text-xs uppercase text-slate-600">
                <tr>
                  <th className="px-4 py-3 font-medium">Supplier</th>
                  <th className="px-4 py-3 font-medium">GSTIN</th>
                  <th className="px-4 py-3 text-right font-medium">Flags</th>
                  <th className="px-4 py-3 text-right font-medium">High risk</th>
                  <th className="px-4 py-3 text-right font-medium">ITC at risk</th>
                </tr>
              </thead>
              <tbody>
                {suppliers.suppliers.map((supplier) => (
                  <tr key={supplier.supplier_gstin} className="border-t border-slate-100 text-slate-700">
                    <td className="px-4 py-3 font-medium text-slate-900">{supplier.supplier_name}</td>
                    <td className="px-4 py-3 font-mono text-xs">{supplier.supplier_gstin}</td>
                    <td className="px-4 py-3 text-right">{supplier.flagged_count}</td>
                    <td className="px-4 py-3 text-right">{supplier.high_risk_count}</td>
                    <td className="px-4 py-3 text-right">₹{supplier.itc_at_risk.toLocaleString("en-IN")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data.latest_run ? (
        <div className="mt-8">
          <Link
            href={`/runs/${data.latest_run.id}`}
            className="text-slate-900 underline underline-offset-2"
          >
            View latest reconciliation run ({data.latest_run.period || "no period"})
          </Link>
        </div>
      ) : (
        <p className="mt-8 text-slate-500">
          No reconciliation runs yet.{" "}
          <Link href="/upload" className="underline">
            Upload your files to get started.
          </Link>
        </p>
      )}
    </div>
  );
}

export default function HomePage() {
  return (
    <RequireAuth>
      <DashboardContent />
    </RequireAuth>
  );
}
