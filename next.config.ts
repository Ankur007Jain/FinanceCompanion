import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  experimental: {
    serverActions: { allowedOrigins: ["localhost:3000", "localhost:3001"] },
    instrumentationHook: true,
  },
  // Treat next-auth as external on the server to avoid SSR localStorage issues
  // with Node.js 22+ experimental localStorage flag
  serverExternalPackages: ["next-auth"],
};

export default nextConfig;
