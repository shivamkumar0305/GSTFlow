"use client";

import { useRef, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import type { InvoiceBatch, NeedsPasswordResponse, UploadResponse } from "@/lib/types";

type Props = {
  title: string;
  description: string;
  uploadPath: string;
  period: string;
  onDone: (batch: InvoiceBatch) => void;
};

type Phase = "idle" | "uploading" | "needs_password" | "processing" | "done" | "failed";

export default function FileUploadBox({ title, description, uploadPath, period, onDone }: Props) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [filename, setFilename] = useState<string>("");
  const [uploadToken, setUploadToken] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [batch, setBatch] = useState<InvoiceBatch | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function pollBatch(batchId: number) {
    const check = async () => {
      try {
        const b = await apiFetch<InvoiceBatch>(`/api/uploads/${batchId}/`);
        setBatch(b);
        if (b.status === "processing") {
          pollTimer.current = setTimeout(check, 1200);
        } else if (b.status === "done") {
          setPhase("done");
          onDone(b);
        } else {
          setPhase("failed");
          setError(b.error_message || "Processing failed.");
        }
      } catch {
        setPhase("failed");
        setError("Could not check upload status.");
      }
    };
    check();
  }

  async function submit(file: File | null, existingToken: string | null, pwd: string) {
    setError(null);
    const form = new FormData();
    if (file) form.append("file", file);
    if (existingToken) form.append("upload_token", existingToken);
    if (pwd) form.append("password", pwd);
    if (period) form.append("period", period);

    setPhase(file ? "uploading" : "processing");
    try {
      const res = await apiFetch<UploadResponse>(uploadPath, {
        method: "POST",
        body: form,
        isFormData: true,
      });
      setUploadToken(res.upload_token);
      setPhase("processing");
      pollBatch(res.batch_id);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        const data = err.data as NeedsPasswordResponse;
        setUploadToken(data.upload_token);
        setFilename(data.filename);
        setPhase("needs_password");
        return;
      }
      if (err instanceof ApiError && err.status === 429) {
        setError(err.message);
        setPhase("failed");
        return;
      }
      setError(err instanceof ApiError ? err.message : "Upload failed.");
      setPhase("failed");
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setFilename(file.name);
    submit(file, null, "");
  }

  function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    submit(null, uploadToken, password);
  }

  function reset() {
    if (pollTimer.current) clearTimeout(pollTimer.current);
    setPhase("idle");
    setUploadToken(null);
    setPassword("");
    setError(null);
    setBatch(null);
    setFilename("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5">
      <h3 className="font-medium">{title}</h3>
      <p className="mt-1 text-sm text-slate-500">{description}</p>

      {phase === "idle" && (
        <label className="mt-4 block cursor-pointer rounded-md border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500 hover:border-slate-400">
          Click to choose a CSV / XLSX / JSON file
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls,.json"
            className="hidden"
            onChange={handleFileChange}
          />
        </label>
      )}

      {(phase === "uploading" || phase === "processing") && (
        <p className="mt-4 text-sm text-slate-500">
          {filename} — {phase === "uploading" ? "uploading..." : "processing..."}
        </p>
      )}

      {phase === "needs_password" && (
        <form onSubmit={handlePasswordSubmit} className="mt-4 flex flex-col gap-2">
          <p className="text-sm text-amber-700">
            {filename} is password-protected. Enter the password to continue.
          </p>
          <div className="flex gap-2">
            <input
              type="password"
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="File password"
            />
            <button
              type="submit"
              className="rounded-md bg-slate-900 px-3 py-2 text-sm text-white"
            >
              Unlock
            </button>
          </div>
        </form>
      )}

      {phase === "done" && batch && (
        <div className="mt-4 flex items-center justify-between text-sm">
          <p className="text-green-700">
            {batch.original_filename} — {batch.row_count} rows loaded
          </p>
          <button onClick={reset} className="text-slate-500 underline">
            Replace
          </button>
        </div>
      )}

      {phase === "failed" && (
        <div className="mt-4 flex flex-col gap-2">
          <p className="text-sm text-red-600">{error}</p>
          <button onClick={reset} className="self-start text-sm text-slate-500 underline">
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
