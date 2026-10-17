import type { NextConfig } from "next";
const apiOrigin = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
if (process.env.VERCEL === "1") {
  let origin: URL;
  try {
    origin = new URL(apiOrigin);
  } catch {
    throw new Error("Vercel requires API_INTERNAL_URL to be the public HTTPS backend origin.");
  }
  if (
    !process.env.API_INTERNAL_URL ||
    origin.protocol !== "https:" ||
    origin.username ||
    origin.password ||
    origin.search ||
    origin.hash ||
    origin.pathname !== "/" ||
    ["localhost", "0.0.0.0", "[::1]"].includes(origin.hostname) ||
    origin.hostname.startsWith("127.") ||
    origin.hostname.endsWith(".invalid") ||
    origin.hostname.endsWith(".local")
  ) {
    throw new Error("Vercel requires API_INTERNAL_URL to be the public HTTPS backend origin.");
  }
}
const config: NextConfig = {
  output: "standalone",
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            key: "Content-Security-Policy",
            value:
              "default-src 'self'; script-src 'self' 'unsafe-inline'" +
              (process.env.NODE_ENV === "production" ? "" : " 'unsafe-eval'") +
              "; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://media.api-sports.io https://crests.football-data.org; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
          },
        ],
      },
    ];
  },
};
export default config;
