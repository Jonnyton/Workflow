from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "static" / "play" / "scorched-tanks"


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def assert_condition(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    html = read_text("index.html")
    original = read_text("original.js")
    service_worker = read_text("service-worker.js")
    manifest = json.loads(read_text("manifest.webmanifest"))

    assert_condition(
        'id="install-button"' in html
        and 'id="install-button" class="button" type="button" disabled' not in html,
        "Install button must not be disabled while waiting for beforeinstallprompt.",
    )
    assert_condition(
        "Use the browser menu to install this app" in original,
        "Install fallback must tell users how to finish PWA installation.",
    )
    assert_condition(
        "installButton.disabled = false;" in original,
        "Install button must be re-enabled after native install prompt handling.",
    )
    assert_condition(
        manifest["display"] == "standalone"
        and manifest["start_url"] == "/play/scorched-tanks/"
        and manifest["scope"] == "/play/scorched-tanks/",
        "Manifest must remain installable as a scoped standalone PWA.",
    )
    assert_condition(
        '"./manifest.webmanifest?v=bug043"' in service_worker
        and '"./original.js?v=bug043"' in service_worker,
        "Service worker cache must include the current PWA install assets.",
    )


if __name__ == "__main__":
    main()
