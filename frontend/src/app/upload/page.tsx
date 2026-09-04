"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import RequireAuth from "@/components/RequireAuth";
import FileUploadBox from "@/components/FileUploadBox";
import { apiFetch, ApiError } from "@/lib/api";
import type { InvoiceBatch, ReconciliationRun } from "@/lib/types";

function currentPeriod() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  return `${month}-${now.getFullYear()}`;
}

function UploadContent() {
  const router = useRouter();
  const [period, setPeriod] = useState(currentPeriod());
  const [booksBatch, setBooksBatch] = useState<InvoiceBatch | null>(null);
  const [statementBatch, setStatementBatch] = useState<InvoiceBatch | null>(null);
  const [reconciling, setReconciling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const bothReady = booksBatch?.status === "done" && statementBatch?.status === "done";

  async function runReconciliation() {
    setError(null);
    setReconciling(true);
    try {
      const run = await apiFetch<ReconciliationRun>("/api/reconcile/", {
        method: "POST",
        body: { period },
      });
      router.push(`/runs/${run.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start reconciliation.");
      setReconciling(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-2xl font-semibold">Upload & Reconcile</h1>
      <p className="mt-1 text-sm text-slate-500">
        Upload your purchase register and the GSTR-2A/2B statement you downloaded from the GST
        portal for the same period. Matching is deterministic and rule-based — nothing here is
        decided by an AI model.
      </p>

      <label className="mt-6 flex max-w-xs flex-col gap-1 text-sm">
        Period (MM-YYYY)
        <input
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="rounded-md border border-slate-300 px-3 py-2"
          placeholder="04-2026"
        />
      </label>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <FileUploadBox
          title="Purchase Register"
          description="Your own purchase invoice records (CSV or XLSX)."
          uploadPath="/api/uploads/purchase-register/"
          period={period}
          onDone={setBooksBatch}
        />
        <FileUploadBox
          title="GSTR-2A / 2B Statement"
          description="Downloaded from the GST portal (XLSX or JSON, may be password-protected)."
          uploadPath="/api/uploads/gstr2a/"
          period={period}
          onDone={setStatementBatch}
        />
      </div>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      <button
        onClick={runReconciliation}
        disabled={!bothReady || reconciling}
        className="mt-8 rounded-md bg-slate-900 px-5 py-2.5 text-sm text-white disabled:opacity-40"
      >
        {reconciling ? "Starting reconciliation..." : "Run Reconciliation"}
      </button>
    </div>
  );
}

export default function UploadPage() {
  return (
    <RequireAuth>
      <UploadContent />
    </RequireAuth>
  );
}
