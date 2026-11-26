import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import NavBar from "@/components/NavBar";

export const metadata: Metadata = {
  title: "GSTFlow",
  description: "GSTFlow student project for GST invoice reconciliation and exception review",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col text-slate-900">
        <AuthProvider>
          <NavBar />
          <main className="flex-1">{children}</main>
          <footer className="portal-footer">
            <div className="portal-footer-inner">
              <span>GSTFlow · Student project prototype</span>
              <span>Not connected to GSTN · Does not file returns or determine ITC eligibility</span>
            </div>
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
