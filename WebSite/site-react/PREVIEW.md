# Previewing & approving the React site

Three ways to see changes before they go live. **The live site (tinyassets.io)
is unaffected by all of these** until the host runs the gated cutover
(`docs/runbooks/2026-06-24-site-react-cutover.md`).

## 1. Local hot-reload (fastest, like the old `vite dev`)

```bash
cd WebSite/site-react
npm install        # first time
npm run dev        # → http://localhost:3000
```

Live data (vital signs, goals, graph) works: dev proxies `/mcp` →
`https://tinyassets.io/mcp` server-side (no CORS), the same role the old Svelte
`/mcp-live` proxy played.

## 2. Production-exact local preview

```bash
cd WebSite/site-react
npm run preview    # next build + serves the real static export at http://localhost:4322
```

This is byte-for-byte what GitHub Pages would publish. Live `/mcp` data does NOT
load here (no same-origin endpoint on localhost) — use #1 for live data, #3 for a
live-data hosted check.

## 3. Hosted preview link (shareable, review on any device)

Open or push to a **pull request** that touches `WebSite/site-react/**` (or run
the `preview-site-react.yml` workflow manually). It builds the site and deploys to
a **separate Cloudflare Pages project** (`tiny-site-react-preview`), then comments
the `https://…pages.dev` URL on the PR. That project is independent of
tinyassets.io — safe to deploy on every change. The hosted build points at the
live `/mcp`, so widgets show real data when CORS permits (otherwise they degrade to
"reading…/asleep", same as production behavior).

> One-time host setup: the `CLOUDFLARE_API_TOKEN` secret needs the
> **Cloudflare Pages: Edit** permission added (it currently has Workers Routes
> scope). After that, the preview URL appears automatically on every site PR.

## The approval loop (default: hosted preview)

1. A change lands on a branch / PR (made by you or by an agent).
2. `preview-site-react.yml` posts the hosted preview URL on the PR.
3. You review on the link; request tweaks or approve.
4. On approval → merge to `main`. **Merging does not auto-publish** — the React
   site only goes live when the host runs the cutover (`deploy-site-react.yml`,
   `confirm: deploy`). Until cutover, `main` just holds the approved React source
   while tinyassets.io stays on Svelte.
