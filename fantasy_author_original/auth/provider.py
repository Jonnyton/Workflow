"""Auth providers — pluggable authentication backends.

Two concrete providers:
  - DevAuthProvider: no auth, all requests are "anonymous" (dev/tunnel mode)
  - OAuthProvider: OAuth 2.1 + PKCE with Dynamic Client Registration

The provider is selected at server startup based on UNIVERSE_SERVER_AUTH.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import sqlite3
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("universe_server.auth")


# ═══════════════════════════════════════════════════════════════════════════
# Identity
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class Identity:
    """Resolved user identity from an authenticated request."""

    user_id: str
    username: str
    display_name: str = ""
    is_host: bool = False
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def can(self, capability: str) -> bool:
        """Check if this identity has a specific capability."""
        if self.is_host:
            return True  # Host can do everything
        return capability in self.capabilities

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ANONYMOUS = Identity(
    user_id="anonymous",
    username="anonymous",
    display_name="Anonymous",
    is_host=False,
    capabilities=["read", "submit_request", "list"],
)

HOST = Identity(
    user_id="host",
    username="host",
    display_name="Host",
    is_host=True,
    capabilities=[],  # Host has all capabilities implicitly
)


# ═══════════════════════════════════════════════════════════════════════════
# Abstract Provider
# ═══════════════════════════════════════════════════════════════════════════


class AuthProvider(ABC):
    """Abstract authentication provider."""

    @abstractmethod
    def resolve_token(self, token: str) -> Identity | None:
        """Resolve a Bearer token to an Identity, or None if invalid."""
        ...

    @abstractmethod
    def is_auth_required(self) -> bool:
        """Whether this provider requires authentication."""
        ...

    @abstractmethod
    def register_client(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Dynamic Client Registration (RFC 7591).

        Accepts client metadata, returns client credentials including
        client_id. MCP clients call this to self-register.
        """
        ...

    @abstractmethod
    def create_authorization(
        self,
        client_id: str,
        redirect_uri: str,
        scope: str,
        state: str,
        code_challenge: str,
        code_challenge_method: str,
    ) -> str:
        """Create an authorization code for the OAuth flow.

        Returns the authorization code. In a full implementation this
        would redirect to a consent page; for now it auto-approves.
        """
        ...

    @abstractmethod
    def exchange_code(
        self,
        code: str,
        client_id: str,
        redirect_uri: str,
        code_verifier: str,
    ) -> dict[str, Any] | None:
        """Exchange an authorization code for tokens.

        Returns token response dict or None if invalid.
        """
        ...


# ═══════════════════════════════════════════════════════════════════════════
# Dev Provider — no auth
# ═══════════════════════════════════════════════════════════════════════════


class DevAuthProvider(AuthProvider):
    """No-auth provider for development. Everyone is anonymous."""

    def resolve_token(self, token: str) -> Identity | None:
        # In dev mode, any token (or no token) is anonymous
        return ANONYMOUS

    def is_auth_required(self) -> bool:
        return False

    def register_client(self, metadata: dict[str, Any]) -> dict[str, Any]:
        # Auto-register with a dummy client_id
        return {
            "client_id": f"dev_{secrets.token_hex(8)}",
            "client_name": metadata.get("client_name", "dev-client"),
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        }

    def create_authorization(
        self, client_id: str, redirect_uri: str, scope: str,
        state: str, code_challenge: str, code_challenge_method: str,
    ) -> str:
        return f"dev_code_{secrets.token_hex(16)}"

    def exchange_code(
        self, code: str, client_id: str, redirect_uri: str,
        code_verifier: str,
    ) -> dict[str, Any] | None:
        return {
            "access_token": f"dev_token_{secrets.token_hex(16)}",
            "token_type": "Bearer",
            "expires_in": 86400,
            "scope": "read write",
        }


# ═══════════════════════════════════════════════════════════════════════════
# OAuth Provider — production auth
# ═══════════════════════════════════════════════════════════════════════════


class OAuthProvider(AuthProvider):
    """OAuth 2.1 + PKCE provider with SQLite-backed state.

    Implements:
      - Dynamic Client Registration (RFC 7591)
      - Authorization Code + PKCE (RFC 7636)
      - Token issuance and validation
      - Refresh tokens

    Storage is SQLite for V1 (matches the author_server pattern).
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            base = os.environ.get("UNIVERSE_SERVER_BASE", "output")
            db_path = Path(base) / ".auth.db"
        self._db_path = Path(db_path)
        self._initialize_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_db(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS oauth_clients (
                client_id       TEXT PRIMARY KEY,
                client_name     TEXT NOT NULL DEFAULT '',
                redirect_uris   TEXT NOT NULL DEFAULT '[]',
                grant_types     TEXT NOT NULL DEFAULT '["authorization_code"]',
                response_types  TEXT NOT NULL DEFAULT '["code"]',
                token_endpoint_auth_method TEXT NOT NULL DEFAULT 'none',
                created_at      TEXT NOT NULL,
                metadata_json   TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS authorization_codes (
                code            TEXT PRIMARY KEY,
                client_id       TEXT NOT NULL,
                redirect_uri    TEXT NOT NULL,
                scope           TEXT NOT NULL DEFAULT '',
                code_challenge  TEXT NOT NULL,
                code_challenge_method TEXT NOT NULL DEFAULT 'S256',
                user_id         TEXT NOT NULL DEFAULT 'anonymous',
                created_at      REAL NOT NULL,
                used            INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (client_id) REFERENCES oauth_clients(client_id)
            );

            CREATE TABLE IF NOT EXISTS access_tokens (
                token_hash      TEXT PRIMARY KEY,
                client_id       TEXT NOT NULL,
                user_id         TEXT NOT NULL,
                scope           TEXT NOT NULL DEFAULT '',
                expires_at      REAL NOT NULL,
                created_at      REAL NOT NULL,
                revoked         INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (client_id) REFERENCES oauth_clients(client_id)
            );

            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token_hash      TEXT PRIMARY KEY,
                client_id       TEXT NOT NULL,
                user_id         TEXT NOT NULL,
                scope           TEXT NOT NULL DEFAULT '',
                expires_at      REAL NOT NULL,
                created_at      REAL NOT NULL,
                revoked         INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (client_id) REFERENCES oauth_clients(client_id)
            );
        """)
        conn.commit()
        conn.close()
        logger.info("OAuth database initialized at %s", self._db_path)

    # --- Token resolution ---

    def resolve_token(self, token: str) -> Identity | None:
        if not token:
            return None

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT user_id, scope, expires_at, revoked "
                "FROM access_tokens WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()

            if not row:
                return None
            if row["revoked"]:
                return None
            if row["expires_at"] < time.time():
                return None

            # Resolve user identity
            user_id = row["user_id"]
            scope = row["scope"]
            capabilities = scope.split() if scope else ["read"]

            # Check if this is the host (first registered user or
            # explicitly configured)
            host_user = os.environ.get("UNIVERSE_SERVER_HOST_USER", "")
            is_host = user_id == host_user if host_user else False

            return Identity(
                user_id=user_id,
                username=user_id,
                display_name=user_id,
                is_host=is_host,
                capabilities=capabilities,
            )
        finally:
            conn.close()

    def is_auth_required(self) -> bool:
        return True

    # --- Dynamic Client Registration (RFC 7591) ---

    def register_client(self, metadata: dict[str, Any]) -> dict[str, Any]:
        client_id = f"mcp_{secrets.token_hex(16)}"
        now = datetime.now(timezone.utc).isoformat()

        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO oauth_clients "
                "(client_id, client_name, redirect_uris, grant_types, "
                " response_types, token_endpoint_auth_method, created_at, "
                " metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    client_id,
                    metadata.get("client_name", ""),
                    json.dumps(metadata.get("redirect_uris", [])),
                    json.dumps(metadata.get("grant_types", ["authorization_code"])),
                    json.dumps(metadata.get("response_types", ["code"])),
                    metadata.get("token_endpoint_auth_method", "none"),
                    now,
                    json.dumps(metadata),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        logger.info("Registered OAuth client: %s (%s)", client_id, metadata.get("client_name", ""))

        return {
            "client_id": client_id,
            "client_name": metadata.get("client_name", ""),
            "grant_types": metadata.get("grant_types", ["authorization_code"]),
            "response_types": metadata.get("response_types", ["code"]),
            "token_endpoint_auth_method": "none",
        }

    # --- Authorization ---

    def create_authorization(
        self, client_id: str, redirect_uri: str, scope: str,
        state: str, code_challenge: str, code_challenge_method: str,
    ) -> str:
        # Verify client exists
        conn = self._connect()
        try:
            client = conn.execute(
                "SELECT client_id FROM oauth_clients WHERE client_id = ?",
                (client_id,),
            ).fetchone()
            if not client:
                raise ValueError(f"Unknown client: {client_id}")

            code = secrets.token_urlsafe(48)
            conn.execute(
                "INSERT INTO authorization_codes "
                "(code, client_id, redirect_uri, scope, code_challenge, "
                " code_challenge_method, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    code, client_id, redirect_uri, scope or "read write",
                    code_challenge, code_challenge_method or "S256",
                    time.time(),
                ),
            )
            conn.commit()
            return code
        finally:
            conn.close()

    # --- Token exchange ---

    def exchange_code(
        self, code: str, client_id: str, redirect_uri: str,
        code_verifier: str,
    ) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM authorization_codes "
                "WHERE code = ? AND client_id = ? AND used = 0",
                (code, client_id),
            ).fetchone()

            if not row:
                return None

            # Check expiry (codes valid for 10 minutes)
            if time.time() - row["created_at"] > 600:
                return None

            # Verify PKCE
            if not self._verify_pkce(
                code_verifier, row["code_challenge"], row["code_challenge_method"],
            ):
                logger.warning("PKCE verification failed for client %s", client_id)
                return None

            # Mark code as used
            conn.execute(
                "UPDATE authorization_codes SET used = 1 WHERE code = ?",
                (code,),
            )

            # Issue tokens
            access_token = secrets.token_urlsafe(48)
            refresh_token = secrets.token_urlsafe(48)
            now = time.time()
            scope = row["scope"]

            access_hash = hashlib.sha256(access_token.encode()).hexdigest()
            refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

            conn.execute(
                "INSERT INTO access_tokens "
                "(token_hash, client_id, user_id, scope, expires_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (access_hash, client_id, row["user_id"], scope, now + 3600, now),
            )
            conn.execute(
                "INSERT INTO refresh_tokens "
                "(token_hash, client_id, user_id, scope, expires_at, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (refresh_hash, client_id, row["user_id"], scope, now + 86400 * 30, now),
            )
            conn.commit()

            return {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": refresh_token,
                "scope": scope,
            }
        finally:
            conn.close()

    @staticmethod
    def _verify_pkce(
        verifier: str, challenge: str, method: str,
    ) -> bool:
        """Verify PKCE code_verifier against stored challenge."""
        if method == "S256":
            computed = (
                hashlib.sha256(verifier.encode("ascii"))
                .digest()
            )
            import base64
            expected = base64.urlsafe_b64encode(computed).rstrip(b"=").decode("ascii")
            return expected == challenge
        elif method == "plain":
            return verifier == challenge
        return False


# ═══════════════════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════════════════


def create_provider() -> AuthProvider:
    """Create the appropriate auth provider based on configuration."""
    auth_mode = os.environ.get("UNIVERSE_SERVER_AUTH", "false").lower()
    if auth_mode in ("true", "1", "yes", "oauth"):
        logger.info("OAuth auth provider enabled")
        return OAuthProvider()
    else:
        logger.info("Dev auth provider (no auth)")
        return DevAuthProvider()
