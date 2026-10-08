"""Published metadata and translation consistency."""

import json
from pathlib import Path


def test_version_and_minimum():
    manifest = json.loads(
        Path("custom_components/alerts_energy_outages/manifest.json").read_text()
    )
    hacs = json.loads(Path("hacs.json").read_text())
    assert manifest["domain"] == "alerts_energy_outages"
    assert manifest["version"] == "2.2.0"
    assert hacs["homeassistant"] == "2024.6.0"
