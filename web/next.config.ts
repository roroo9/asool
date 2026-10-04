import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  devIndicators: false,
  async rewrites() {
    // The browser only ever talks to the web app; /api/* is forwarded to FastAPI.
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
