const isDev = process.env.NODE_ENV === "development";

/** @type {import('next').NextConfig} */
const nextConfig = {
  trailingSlash: true,
  images: { unoptimized: true },
  // The design system ships ESM dist; let Next transpile it.
  transpilePackages: ["@tiny/design-system"],
  // Production: static export (matches the GH Pages deploy of the Svelte site).
  // Dev: no export, plus a /mcp proxy so `npm run dev` shows live data (vital
  // signs, goals, graph) like the old Svelte vite `/mcp-live` proxy — server-
  // side, so no CORS. The two never coexist, so there's no export-vs-rewrite warning.
  ...(isDev
    ? {
        skipTrailingSlashRedirect: true, // /mcp is POST — don't 308 to /mcp/
        async rewrites() {
          return [{ source: "/mcp", destination: "https://tinyassets.io/mcp" }];
        },
      }
    : { output: "export" }),
};

export default nextConfig;
