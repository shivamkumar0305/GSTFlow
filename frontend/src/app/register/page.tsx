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
    <div className="mx-auto flex max-w-sm flex-col gap-6 px-6 py-16">
      <h1 className="text-2xl font-semibold">Register your business</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm">
          Business name
          <input
            required
            value={form.business_name}
            onChange={(e) => update("business_name", e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          GSTIN
          <input
            required
            maxLength={15}
            value={form.gstin}
            onChange={(e) => update("gstin", e.target.value.toUpperCase())}
            className="rounded-md border border-slate-300 px-3 py-2 uppercase"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          PAN
          <input
            required
            maxLength={10}
            value={form.pan}
            onChange={(e) => update("pan", e.target.value.toUpperCase())}
            className="rounded-md border border-slate-300 px-3 py-2 uppercase"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Email
          <input
            type="email"
            required
            value={form.email}
            onChange={(e) => update("email", e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Password
          <input
            type="password"
            required
            minLength={8}
            value={form.password}
            onChange={(e) => update("password", e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2"
          />
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="rounded-md bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
        >
          {busy ? "Creating account..." : "Create account"}
        </button>
      </form>
      <p className="text-sm text-slate-600">
        Already have an account?{" "}
        <Link href="/login" className="text-slate-900 underline">
          Log in
        </Link>
      </p>
    </div>
  );
}
