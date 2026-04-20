from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import emergency_dns_flip as dns_flip  # noqa: E402


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, path, *, params=None, payload=None):
        self.calls.append({
            "method": method,
            "path": path,
            "params": params,
            "payload": payload,
        })
        if not self.responses:
            return {}
        return self.responses.pop(0)


def test_upsert_dns_record_creates_when_no_record_exists():
    client = FakeClient([{"result": []}, {"result": {"id": "new-record"}}])

    result = dns_flip.upsert_dns_record(
        client,
        zone_id="zone123",
        record_type="CNAME",
        name="mcp.tinyassets.io",
        content="fallback.example.net",
        ttl=1,
        proxied=True,
        comment="emergency flip",
        dry_run=False,
    )

    assert result.action == "created"
    assert client.calls[0]["method"] == "GET"
    assert client.calls[0]["path"] == "/zones/zone123/dns_records"
    assert client.calls[0]["params"] == {"type": "CNAME", "name": "mcp.tinyassets.io"}
    assert client.calls[1]["method"] == "POST"
    assert client.calls[1]["payload"] == {
        "type": "CNAME",
        "name": "mcp.tinyassets.io",
        "content": "fallback.example.net",
        "ttl": 1,
        "proxied": True,
        "comment": "emergency flip",
    }


def test_upsert_dns_record_patches_single_existing_record():
    client = FakeClient([
        {"result": [{"id": "record123"}]},
        {"result": {"id": "record123"}},
    ])

    result = dns_flip.upsert_dns_record(
        client,
        zone_id="zone123",
        record_type="CNAME",
        name="mcp.tinyassets.io",
        content="new-target.example.net",
        ttl=1,
        proxied=False,
        comment=None,
        dry_run=False,
    )

    assert result.action == "updated"
    assert client.calls[1]["method"] == "PATCH"
    assert client.calls[1]["path"] == "/zones/zone123/dns_records/record123"
    assert client.calls[1]["payload"]["content"] == "new-target.example.net"
    assert client.calls[1]["payload"]["proxied"] is False
    assert "comment" not in client.calls[1]["payload"]


def test_upsert_dns_record_dry_run_does_not_mutate():
    client = FakeClient([{"result": []}])

    result = dns_flip.upsert_dns_record(
        client,
        zone_id="zone123",
        record_type="A",
        name="api.tinyassets.io",
        content="203.0.113.10",
        ttl=300,
        proxied=None,
        comment=None,
        dry_run=True,
    )

    assert result.action == "would_create"
    assert [call["method"] for call in client.calls] == ["GET"]


def test_duplicate_dns_record_match_fails_closed():
    client = FakeClient([{"result": [{"id": "one"}, {"id": "two"}]}])

    with pytest.raises(dns_flip.CloudflareApiError, match="matched 2"):
        dns_flip.upsert_dns_record(
            client,
            zone_id="zone123",
            record_type="CNAME",
            name="mcp.tinyassets.io",
            content="fallback.example.net",
            ttl=1,
            proxied=True,
            comment=None,
            dry_run=False,
        )

    assert [call["method"] for call in client.calls] == ["GET"]


def test_delete_worker_route_deletes_exact_pattern_match():
    client = FakeClient([
        {"result": [
            {"id": "route-1", "pattern": "tinyassets.io/mcp*", "script": "workflow-mcp-router"},
            {"id": "route-2", "pattern": "tinyassets.io/catalog*", "script": "catalog"},
        ]},
        {"result": {"id": "route-1"}},
    ])

    result = dns_flip.delete_worker_route(
        client,
        zone_id="zone123",
        pattern="tinyassets.io/mcp*",
        dry_run=False,
    )

    assert result.action == "deleted"
    assert client.calls[1]["method"] == "DELETE"
    assert client.calls[1]["path"] == "/zones/zone123/workers/routes/route-1"
