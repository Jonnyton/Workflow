from __future__ import annotations

from starlette.testclient import TestClient

from workflow.universe_server import create_streamable_http_app


def test_streamable_http_app_mounts_legacy_and_directory_surfaces() -> None:
    app = create_streamable_http_app()
    paths = {getattr(route, "path", None) for route in app.routes}

    assert "/mcp" in paths
    assert "/mcp-directory" in paths
    assert app.state.path == "/mcp,/mcp-directory"
    assert app.state.transport_type == "streamable-http"


def test_mcp_get_with_html_accept_returns_discovery_html() -> None:
    app = create_streamable_http_app()

    with TestClient(app) as client:
        response = client.get("/mcp", headers={"accept": "text/html"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>Workflow Server</title>" in response.text


def test_mcp_directory_get_with_html_accept_returns_discovery_html() -> None:
    app = create_streamable_http_app()

    with TestClient(app) as client:
        response = client.get("/mcp-directory", headers={"accept": "text/html"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>Workflow Server</title>" in response.text
