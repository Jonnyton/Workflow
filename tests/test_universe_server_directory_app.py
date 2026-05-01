from __future__ import annotations

from workflow.universe_server import create_streamable_http_app


def test_streamable_http_app_mounts_legacy_and_directory_surfaces() -> None:
    app = create_streamable_http_app()
    paths = {getattr(route, "path", None) for route in app.routes}

    assert "/mcp" in paths
    assert "/mcp-directory" in paths
    assert app.state.path == "/mcp,/mcp-directory"
    assert app.state.transport_type == "streamable-http"
