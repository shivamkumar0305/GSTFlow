"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export default function RegisterPage() {
  const { register } = useAuth();
  const [form, setForm] = useState({
    email: "",
    password: "",
    business_name: "",
    gstin: "",
    pan: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function update<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await register(form);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <p className="page-eyebrow">New workspace</p>
      <h1>Register your business</h1>
      <p className="auth-intro">Create a project workspace to upload and compare invoice files.</p>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="field-label flex flex-col gap-2">
          Business name
          <input
            required
            value={form.business_name}
            onChange={(e) => update("business_name", e.target.value)}
            className="portal-input"
          />
        </label>
        <label className="field-label flex flex-col gap-2">
          GSTIN
          <input
            required
            maxLength={15}
            value={form.gstin}
            onChange={(e) => update("gstin", e.target.value.toUpperCase())}
            className="portal-input uppercase"
          />
        </label>
        <label className="field-label flex flex-col gap-2">
          PAN
          <input
            required
            maxLength={10}
            value={form.pan}
            onChange={(e) => update("pan", e.target.value.toUpperCase())}
            className="portal-input uppercase"
          />
        </label>
        <label className="field-label flex flex-col gap-2">
          Email
          <input
            type="email"
            required
            value={form.email}
            onChange={(e) => update("email", e.target.value)}
            className="portal-input"
          />
        </label>
        <label className="field-label flex flex-col gap-2">
          Password
          <input
            type="password"
            required
            minLength={8}
            value={form.password}
            onChange={(e) => update("password", e.target.value)}
            className="portal-input"
          />
        </label>
        {error && <p className="status-banner error">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="primary-button disabled:opacity-50"
        >
          {busy ? "Creating account…" : "Create business account"}
        </button>
      </form>
      <p className="text-sm text-slate-600">
        Already have an account?{" "}
        <Link href="/login" className="font-semibold text-[#173e66] underline">
          Log in
        </Link>
      </p>
    </div>
  );
}
