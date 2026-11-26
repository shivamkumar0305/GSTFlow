"use client";

import { useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <p className="page-eyebrow">Secure access</p>
      <h1>Sign in to GSTFlow</h1>
      <p className="auth-intro">Access your business reconciliation workspace. This student project does not connect to GSTN.</p>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="field-label flex flex-col gap-2">
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="portal-input"
          />
        </label>
        <label className="field-label flex flex-col gap-2">
          Password
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="portal-input"
          />
        </label>
        {error && <p className="status-banner error">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="primary-button disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p className="text-sm text-slate-600">
        No account?{" "}
        <Link href="/register" className="font-semibold text-[#173e66] underline">
          Register your business
        </Link>
      </p>
    </div>
  );
}
