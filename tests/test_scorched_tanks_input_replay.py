from __future__ import annotations

import json
from pathlib import Path

SCORCHED_ROOT = Path("WebSite/site/static/play/scorched-tanks")


def test_scorched_manifest_declares_native_input_replay_contract():
    manifest = json.loads((SCORCHED_ROOT / "compatibility.json").read_text())

    replay = manifest["input_replay"]
    assert replay["runner_request"] == "RUNNER-011"
    assert replay["strategy"] == "emulator-native deterministic playback only"
    assert replay["status"] == "NOT_CONFIGURED"
    assert replay["active_native_format"] is None
    assert "native input movie loader" in replay["blocker"]

    formats = {
        entry["format"]: entry
        for entry in replay["accepted_native_formats"]
    }
    assert formats["BSV"]["extensions"] == [".bsv"]
    assert formats["FS_UAE_REC"]["extensions"] == [".fs-uae-rec", ".rec"]
    assert formats["DOSBOX_MOVIE"]["role"].endswith("not input playback")


def test_scorched_original_proof_exposes_input_replay_status():
    script = (SCORCHED_ROOT / "original.js").read_text()

    assert 'runnerRequest: "RUNNER-011"' in script
    assert 'status: "not-configured"' in script
    assert 'strategy: "emulator-native"' in script
    assert 'acceptedNativeFormats: ["BSV", "FS_UAE_REC", "DOSBOX_MOVIE"]' in script
    assert "inputReplay: { ...INPUT_REPLAY_PROOF }" in script
