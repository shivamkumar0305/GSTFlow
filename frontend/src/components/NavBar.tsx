"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function NavBar() {
  const { business, logout } = useAuth();
  const pathname = usePathname();

  return (
    <>
      <div className="utility-bar">
        <div className="utility-inner">
          <span className="utility-notice">GSTFlow student project · GST reconciliation workspace</span>
          <span>India · English</span>
        </div>
      </div>
      <div className="tricolor" aria-hidden="true"><span /><span /><span /></div>
      <header className="masthead">
        <div className="masthead-inner">
          <Link href="/" className="brand-link" aria-label="GSTFlow home">
            <span className="brand-mark" aria-hidden="true">GF</span>
            <span>
              <span className="brand-name">GSTFlow</span>
              <span className="brand-caption">Invoice reconciliation system</span>
            </span>
          </Link>
          <div className="masthead-meta">
            <strong>Purchase register ↔ GST statement</strong>
            Assisted review · Human decision required
          </div>
        </div>
      </header>
      <nav className="portal-nav" aria-label="Main navigation">
        <div className="portal-nav-inner">
          <div className="nav-links">
            {business ? (
              <>
                <Link href="/" aria-current={pathname === "/" ? "page" : undefined} className="nav-link">Dashboard</Link>
                <Link href="/upload" aria-current={pathname === "/upload" ? "page" : undefined} className="nav-link">Upload & reconcile</Link>
              </>
            ) : (
              <>
                <Link href="/login" aria-current={pathname === "/login" ? "page" : undefined} className="nav-link">Sign in</Link>
                <Link href="/register" aria-current={pathname === "/register" ? "page" : undefined} className="nav-link">Register business</Link>
              </>
            )}
          </div>
          {business && (
            <div className="nav-links">
              <span className="nav-business">{business.name}</span>
              <button onClick={logout} className="nav-action">Log out</button>
            </div>
          )}
        </div>
      </nav>
    </>
  );
}
