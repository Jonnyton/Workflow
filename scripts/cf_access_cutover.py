"""CF Access cutover — Option 1 of the single-entry runbook.

Two auth schemes supported:
  - Bearer (CLOUDFLARE_API_TOKEN with Account:Access:Edit + Workers Scripts:Edit)
  - Global Key (CLOUDFLARE_EMAIL + CLOUDFLARE_GLOBAL_KEY) — unscoped full access

Steps:
  1. POST /accounts/{acct}/access/service_tokens  (mint workflow-mcp-worker)
  2. POST /accounts/{acct}/access/apps            (self-hosted app for mcp.tinyassets.io)
  3. POST /accounts/{acct}/access/apps/{uuid}/policies  (Service Auth = token)
  4. PUT  /accounts/{acct}/workers/scripts/{script}/secrets  (two secrets)
  5. Three-check verification.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from emergency_dns_flip import CloudflareApiError, CloudflareClient  # noqa: E402

SERVICE_TOKEN_NAME = "workflow-mcp-worker"
APP_DOMAIN = "mcp.tinyassets.io"
APP_NAME = "workflow-mcp-worker-gate"
POLICY_NAME = "worker-only"


class _GlobalKeyClient(CloudflareClient):
    """Variant of CloudflareClient using X-Auth-Email + X-Auth-Key."""

    def __init__(self, email: str, global_key: str) -> None:
        if not email or not global_key:
            raise CloudflareApiError("CLOUDFLARE_EMAIL + CLOUDFLARE_GLOBAL_KEY required")
        # Skip parent __init__'s token requirement; we use different headers.
        self.token = None  # type: ignore[assignment]
        self.base_url = "https://api.cloudflare.com/client/v4"
        self._email = email
        self._key = global_key

    def request(self, method, path, *, params=None, payload=None):
        import urllib.parse

        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{self.base_url}{path}{query}"
        headers = {
            "X-Auth-Email": self._email,
            "X-Auth-Key": self._key,
            "Accept": "application/json",
            "User-Agent": "workflow-cf-cutover/1.0",
        }
        data = None
        if payload is not None:
            data = json.dumps(payload, sort_keys=True).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise CloudflareApiError(
                f"Cloudflare HTTP {exc.code} for {method} {path}: {body}"
            ) from exc
        try:
            decoded = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise CloudflareApiError(
                f"Cloudflare returned non-JSON body: {body[:200]!r}"
            ) from exc
        if isinstance(decoded, dict) and decoded.get("success") is False:
            raise CloudflareApiError(
                f"Cloudflare API rejected {method} {path}: {decoded.get('errors')}"
            )
        return decoded


def _make_client() -> CloudflareClient:
    bearer = os.environ.get("CLOUDFLARE_API_TOKEN")
    email = os.environ.get("CLOUDFLARE_EMAIL")
    gkey = os.environ.get("CLOUDFLARE_GLOBAL_KEY")
    if email and gkey:
        print("auth: X-Auth-Email + X-Auth-Key (Global API Key)")
        return _GlobalKeyClient(email, gkey)
    if bearer:
        print("auth: Bearer token")
        return CloudflareClient(bearer)
    raise CloudflareApiError(
        "Set CLOUDFLARE_EMAIL + CLOUDFLARE_GLOBAL_KEY, or CLOUDFLARE_API_TOKEN."
    )


def _resolve_account_id(client: CloudflareClient, zone_id: str) -> str:
    resp = client.request("GET", f"/zones/{zone_id}")
    return resp["result"]["account"]["id"]


def _find_or_create_service_token(
    client: CloudflareClient, account_id: str, *, apply: bool
) -> dict:
    existing = client.request(
        "GET", f"/accounts/{account_id}/access/service_tokens"
    ).get("result") or []
    for t in existing:
        if t.get("name") == SERVICE_TOKEN_NAME:
            print(f"service-token: found existing id={t['id']} (reusing)")
            return t
    if not apply:
        print(
            f"service-token: would CREATE '{SERVICE_TOKEN_NAME}' (dry-run)"
        )
        return {"dry_run": True}
    resp = client.request(
        "POST",
        f"/accounts/{account_id}/access/service_tokens",
        payload={"name": SERVICE_TOKEN_NAME, "duration": "8760h"},
    )
    r = resp["result"]
    print(f"service-token: CREATED id={r['id']} client_id={r['client_id']}")
    return r


def _find_or_create_app(
    client: CloudflareClient, account_id: str, *, apply: bool
) -> dict:
    existing = client.request(
        "GET", f"/accounts/{account_id}/access/apps"
    ).get("result") or []
    for a in existing:
        if a.get("domain") == APP_DOMAIN:
            print(f"access-app: found existing uuid={a['uid']} (reusing)")
            return a
    payload = {
        "name": APP_NAME,
        "domain": APP_DOMAIN,
        "type": "self_hosted",
        "session_duration": "24h",
        "auto_redirect_to_identity": False,
        "allowed_idps": [],
    }
    if not apply:
        print(f"access-app: would CREATE domain={APP_DOMAIN} (dry-run)")
        return {"dry_run": True}
    resp = client.request(
        "POST", f"/accounts/{account_id}/access/apps", payload=payload
    )
    r = resp["result"]
    print(f"access-app: CREATED uuid={r['uid']} domain={r['domain']}")
    return r


def _ensure_policy(
    client: CloudflareClient,
    account_id: str,
    app_uuid: str,
    service_token_id: str,
    *,
    apply: bool,
) -> dict:
    existing = client.request(
        "GET", f"/accounts/{account_id}/access/apps/{app_uuid}/policies"
    ).get("result") or []
    for p in existing:
        if p.get("name") == POLICY_NAME:
            print(f"policy: found existing id={p['id']} (reusing)")
            return p
    payload = {
        "name": POLICY_NAME,
        "decision": "non_identity",
        "include": [{"service_token": {"token_id": service_token_id}}],
        "require": [],
        "exclude": [],
        "precedence": 1,
    }
    if not apply:
        print(f"policy: would CREATE '{POLICY_NAME}' (dry-run)")
        return {"dry_run": True}
    resp = client.request(
        "POST",
        f"/accounts/{account_id}/access/apps/{app_uuid}/policies",
        payload=payload,
    )
    r = resp["result"]
    print(f"policy: CREATED id={r['id']}")
    return r


def _put_worker_secret(
    client: CloudflareClient,
    account_id: str,
    script_name: str,
    name: str,
    value: str,
    *,
    apply: bool,
) -> None:
    if not apply:
        print(f"worker-secret: would PUT {name} on {script_name} (dry-run)")
        return
    client.request(
        "PUT",
        f"/accounts/{account_id}/workers/scripts/{script_name}/secrets",
        payload={"name": name, "text": value, "type": "secret_text"},
    )
    print(f"worker-secret: set {name} on {script_name}")


def three_check(canonical: str, internal: str) -> None:
    print("\n=== three-check ===")
    req = urllib.request.Request(
        canonical,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        data=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "clientInfo": {"name": "cutover-probe", "version": "1"},
                    "capabilities": {},
                },
            }
        ).encode(),
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode()
            print(
                f"(a) canonical {canonical}: {resp.status} "
                f"{'GREEN' if 'serverInfo' in body else 'UNEXPECTED'}"
            )
    except Exception as e:
        print(f"(a) canonical {canonical}: FAILED {e}")

    try:
        req = urllib.request.Request(internal, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(
                f"(b) internal {internal}: status={resp.status} "
                f"({'UNEXPECTED: still reachable' if resp.status < 400 else 'OK'})"
            )
    except urllib.error.HTTPError as e:
        print(
            f"(b) internal {internal}: {e.code} "
            f"({'OK: gated' if e.code in (401, 403) else 'UNEXPECTED'})"
        )
    except Exception as e:
        print(f"(b) internal {internal}: {e}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--worker", required=True, help="Cloudflare Worker script name")
    p.add_argument("--apply", action="store_true", help="actually mutate (default: dry-run)")
    p.add_argument("--skip-verify", action="store_true")
    args = p.parse_args()

    zone_id = os.environ.get("CLOUDFLARE_ZONE_ID")
    if not zone_id:
        print("CLOUDFLARE_ZONE_ID required", file=sys.stderr)
        return 2

    try:
        client = _make_client()
        account_id = _resolve_account_id(client, zone_id)
        print(f"account: {account_id}")

        token_obj = _find_or_create_service_token(client, account_id, apply=args.apply)
        app_obj = _find_or_create_app(client, account_id, apply=args.apply)
        if args.apply and "uid" in app_obj and "id" in token_obj:
            _ensure_policy(
                client,
                account_id,
                app_obj["uid"],
                token_obj["id"],
                apply=args.apply,
            )
            if "client_id" in token_obj and "client_secret" in token_obj:
                _put_worker_secret(
                    client,
                    account_id,
                    args.worker,
                    "CF_ACCESS_CLIENT_ID",
                    token_obj["client_id"],
                    apply=args.apply,
                )
                _put_worker_secret(
                    client,
                    account_id,
                    args.worker,
                    "CF_ACCESS_CLIENT_SECRET",
                    token_obj["client_secret"],
                    apply=args.apply,
                )
            else:
                print(
                    "worker-secrets: skipped — reused existing service token; "
                    "secret not recoverable. Rotate token if Worker doesn't "
                    "already have both secrets set."
                )
    except CloudflareApiError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.apply and not args.skip_verify:
        three_check("https://tinyassets.io/mcp", f"https://{APP_DOMAIN}/mcp")

    return 0


if __name__ == "__main__":
    sys.exit(main())
