import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Vercel packages Next.js itself. Standalone output is only needed by our
  // Docker deployment and currently conflicts with Vercel's Next.js adapter.
  ...(process.env.VERCEL ? {} : { output: "standalone" as const }),
  async rewrites() {
    const apiOrigin = process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }];
  },
};

export default nextConfig;
