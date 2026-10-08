"""Validate repository metadata, translations, Python and YAML syntax."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "alerts_energy_outages"


class ExampleLoader(yaml.SafeLoader):
    """Parse the example's include tag without reading external configuration."""


ExampleLoader.add_constructor(
    "!include_dir_named", lambda loader, node: loader.construct_scalar(node)
)


def keys(value: object, prefix: str = "") -> set[str]:
    """Collect nested translation keys."""
    result = {prefix}
    if isinstance(value, dict):
        for key, child in value.items():
            result.update(keys(child, f"{prefix}/{key}"))
    return result


def main() -> None:
    """Check tracked project paths without crawling virtual environments."""
    for path in INTEGRATION.glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for path in [*INTEGRATION.rglob("*.json"), ROOT / "hacs.json"]:
        json.loads(path.read_text(encoding="utf-8"))
    source = json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))
    for path in (INTEGRATION / "translations").glob("*.json"):
        assert keys(json.loads(path.read_text(encoding="utf-8"))) == keys(source), path
    for directory in ("includes", "automations", ".github"):
        for pattern in ("*.yaml", "*.yml"):
            for path in (ROOT / directory).rglob(pattern):
                yaml.safe_load(path.read_text(encoding="utf-8"))
    yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    yaml.load(
        (ROOT / "configuration.yaml.example").read_text(encoding="utf-8"),
        Loader=ExampleLoader,
    )
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == INTEGRATION.name
    assert manifest["config_flow"] is True
    print("Python, JSON, YAML, translations and metadata checks passed")


if __name__ == "__main__":
    main()
