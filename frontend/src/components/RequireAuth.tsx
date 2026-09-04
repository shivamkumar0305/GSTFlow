"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const { business, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !business) {
      router.replace("/login");
    }
  }, [loading, business, router]);

  if (loading) {
    return <div className="p-8 text-slate-500">Loading...</div>;
  }
  if (!business) return null;

  return <>{children}</>;
}
