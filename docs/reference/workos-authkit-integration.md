# WorkOS AuthKit ↔ MCP Resource Server — implementation recipe

Pointer-loaded reference (ADR-002) for the founder-identity build. Design + decision
live in `docs/design-notes/2026-06-26-founder-and-universe-identity.md` §3.0; this doc
is the *how* for slice 1. Synthesized from WorkOS's own 2026 docs (sources at bottom).

> **Status:** research synthesis (Claude, 2026-06-26). The four **VERIFY-flags** below must
> be confirmed against a live token + AuthKit AS metadata before shipping. Slice-1
> implementation gets opposite-provider (Codex) review per AGENTS.md.

## Architecture
**AuthKit = the OAuth 2.1 Authorization Server. Our MCP server = the Resource Server.**
The RS has exactly two auth jobs: (1) publish Protected Resource Metadata, (2) validate
the incoming bearer JWT. AuthKit owns login, consent, token issuance, and client
registration. We host **no** authorization-server endpoints.

## Token validation — PyJWT + JWKS, NOT the sealed-session SDK
- The workos-python session helpers (`load_sealed_session().authenticate()`) are the
  **web-app client** pattern (cookies/sealed sessions) — wrong for an RS validating an
  incoming `Authorization: Bearer`. Misusing them throws `InvalidToken`. **Don't.**
- For the RS: **PyJWT + `PyJWKClient`** (handles `kid` matching + key rotation + caching).
  Use the SDK for exactly one thing so the URL isn't hardcoded:
  `WorkOSClient(...).user_management.get_jwks_url(client_id)`.
- **JWKS URL (confirmed):** `https://api.workos.com/sso/jwks/<WORKOS_CLIENT_ID>` (per client_id).
- Pin `algorithms=["RS256"]` (algorithm-substitution defense). Validate `iss` **and** `aud`.

## Token claims (AuthKit Sessions doc)
| Claim | Use |
|---|---|
| `sub` | **stable WorkOS user id → our `founder` key.** Docs say use `sub`, not email (email is mutable/unverified). |
| `sid` | session id (sign-out) |
| `iss` | `https://api.workos.com/` **or** your AuthKit domain — VERIFY (flag 1) |
| `org_id` / `role` / `permissions` | only present when an org is selected at sign-in; social-login users w/o org won't have them |
| `exp` / `iat` | standard |
- **Email is NOT in the access token by default.** Either add it as a **custom claim**
  (Dashboard JWT/sessions config — avoids a per-request API call) or look it up server-side
  with `user_management.get_user(sub).email` (needs the API key). Prefer the custom claim.

## MCP discovery / OAuth 2.1 RS plumbing
- **PRM (RFC 9728)** — our server serves `/.well-known/oauth-protected-resource`:
  ```json
  { "resource": "https://tinyassets.io/mcp",
    "authorization_servers": ["https://<authkit_domain>"],
    "bearer_methods_supported": ["header"] }
  ```
- **AS metadata (RFC 8414)** — AuthKit hosts it at
  `https://<authkit_domain>/.well-known/oauth-authorization-server` (advertises
  `authorization_endpoint`, `token_endpoint`, `introspection_endpoint`, `issuer`, `jwks_uri`).
- **Audience binding (RFC 8707)** — register our MCP URL as a **Resource Indicator** in the
  Dashboard; tokens then carry `aud` = that URL. Validate `aud == WORKOS_MCP_RESOURCE`.
- **Client identity** — AuthKit-for-MCP defaults to **CIMD** (2025-11-25 spec) with **DCR**
  for legacy clients. Enable under Dashboard → Connect → Configuration. We manage neither.
- Canonical connector-side guidance: the WorkOS **"Model Context Protocol – AuthKit"** doc.

## The write-gate lives in the dispatcher, not by HTTP verb
All MCP tool calls are POST, so "is this a write?" can't be inferred from the HTTP method.
The middleware only **parses + validates the token → principal**; the **enforcement**
(does this action's `required_scope` match the principal's grants?) happens in the action
dispatcher, keyed by the **scope taxonomy** (`required_scope(action)` — built separately:
reads→open, ordinary writes→write, `create_universe`→costly). Anonymous = no principal =
reads allowed, writes 401.

## Minimal middleware (token-parse only; enforcement in dispatcher)
```python
import os, jwt
from jwt import PyJWKClient
from workos import WorkOSClient

_workos = WorkOSClient(api_key=os.environ.get("WORKOS_API_KEY", ""),
                       client_id=os.environ["WORKOS_CLIENT_ID"])
_jwks = PyJWKClient(_workos.user_management.get_jwks_url(os.environ["WORKOS_CLIENT_ID"]))
_RESOURCE = os.environ["WORKOS_MCP_RESOURCE"]           # https://tinyassets.io/mcp
_ISSUER   = f'https://{os.environ["WORKOS_AUTHKIT_DOMAIN"]}'   # VERIFY (flag 1) vs AS metadata

def validate_bearer(token: str) -> dict:
    key = _jwks.get_signing_key_from_jwt(token)
    c = jwt.decode(token, key.key, algorithms=["RS256"],
                   audience=_RESOURCE, issuer=_ISSUER,
                   options={"require": ["exp", "sub"]})
    return {"founder": c["sub"], "email": c.get("email"),
            "scopes": c.get("permissions", []), "role": c.get("role"),
            "org_id": c.get("org_id")}
```
On a protected action with no/invalid principal, return **401** with
`WWW-Authenticate: Bearer error="invalid_token", resource_metadata="<PRM_URL>"` so the
client can discover AuthKit.

## Env / secrets (RS needs very little)
| Var | Value / where | Needed for |
|---|---|---|
| `WORKOS_CLIENT_ID` | `client_…` (Dashboard → API Keys) | JWKS URL + app id |
| `WORKOS_AUTHKIT_DOMAIN` | e.g. `your-app.authkit.app` or custom `auth.tinyassets.io` | `iss` + PRM + AS discovery |
| `WORKOS_MCP_RESOURCE` | `https://tinyassets.io/mcp` (= registered Resource Indicator) | `aud` + PRM `resource` |
| `WORKOS_API_KEY` | `sk_…` (Dashboard → API Keys) | **only** if doing `get_user()` email lookups; keep out of RS if email is a custom claim |
`WORKOS_REDIRECT_URI` / `WORKOS_COOKIE_PASSWORD` are web-app-client concerns — the RS does
not need them. Vault these via `scripts/load_secrets.sh` (add keys to `secrets_keys.txt`).

## Dashboard config checklist
- [ ] Connect → Configuration: CIMD on (DCR stays on for legacy).
- [ ] Register **Resource Indicator** = our MCP URL.
- [ ] Authentication → OAuth providers: enable **Google** + **GitHub**.
  - **Staging: WorkOS provides default Google + GitHub creds — NO own OAuth apps needed** (WorkOS branding on consent; staging-only).
  - **Production: create our own Google Cloud OAuth client + GitHub OAuth App**, paste Client ID/Secret, set WorkOS's redirect URI as the authorized callback.
- [ ] (Optional) add `email` as a custom access-token claim.
- [ ] Serve PRM at `/.well-known/oauth-protected-resource`.
- [ ] **VERIFY** against live AS metadata: exact `issuer` + `jwks_uri`, then validate accordingly.

## VERIFY-flags (confirm against a real token/metadata before shipping)
1. **Exact `iss`** for our AuthKit-domain config (`https://api.workos.com/` vs the AuthKit domain) — read from AS metadata, don't hardcode.
2. **`email` in token** — authoritative claim list omits it; treat as custom-claim-only; decode a real token to confirm.
3. **No one-call SDK RS-validator** — SDK is sealed-session-oriented; `get_jwks_url()` + PyJWT is the path. Re-check the SDK changelog in case a newer RS helper shipped.
4. **`aud` literal format** for MCP (full URL vs registered identifier) — confirm once the Resource Indicator is registered.

## Sources
WorkOS docs: AuthKit MCP, AuthKit Sessions, Session tokens/JWKS API ref, Connect/OAuth,
Social Login, Google/GitHub OAuth integrations; WorkOS blog: JWT-in-Python, JWT-validation
guide, FastAPI+AuthKit, "add OAuth to your MCP server", "MCP authorization in 5 OAuth specs";
workos-python SDK + issue #493 (RS token validation).
