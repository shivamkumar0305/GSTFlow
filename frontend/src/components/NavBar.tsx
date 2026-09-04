"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

export default function NavBar() {
  const { business, logout } = useAuth();

  return (
    <nav className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-lg font-semibold text-slate-900">
          GSTFlow
        </Link>
        {business && (
          <div className="flex items-center gap-6 text-sm">
            <Link href="/" className="text-slate-600 hover:text-slate-900">
              Dashboard
            </Link>
            <Link href="/upload" className="text-slate-600 hover:text-slate-900">
              Upload
            </Link>
            <span className="text-slate-400">{business.name}</span>
            <button onClick={logout} className="text-slate-600 hover:text-red-600">
              Log out
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}
