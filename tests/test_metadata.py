"""Regression tests for package metadata consistency (BR-SC-1, BR-LC-2)."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import mcp_nfe_br

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_version_slot_consistency() -> None:
    pyproject = tomllib.loads((_PACKAGE_ROOT / "pyproject.toml").read_text())
    assert mcp_nfe_br.__version__ == pyproject["project"]["version"], (
        f"__version__={mcp_nfe_br.__version__} drifted from "
        f"pyproject={pyproject['project']['version']}"
    )


def test_server_json_version_matches_pyproject() -> None:
    pyproject = tomllib.loads((_PACKAGE_ROOT / "pyproject.toml").read_text())
    server = json.loads((_PACKAGE_ROOT / "server.json").read_text())
    expected = pyproject["project"]["version"]
    assert server["version"] == expected, (
        f"server.json version={server['version']} drifted from pyproject={expected}"
    )
    pkg_version = server["packages"][0]["version"]
    assert pkg_version == expected, (
        f"server.json packages[0].version={pkg_version} drifted from pyproject={expected}"
    )


def test_server_json_env_vars_exist_in_source() -> None:
    """BR-LC-2: every env var declared in server.json must be referenced in src/ or core."""
    import mcp_einvoicing_core

    server = json.loads((_PACKAGE_ROOT / "server.json").read_text())

    # Collect text from this package's src/
    src_text = "\n".join(p.read_text() for p in (_PACKAGE_ROOT / "src").rglob("*.py"))

    # Also include mcp_einvoicing_core (LOG_LEVEL and similar platform vars live there)
    core_root = Path(mcp_einvoicing_core.__file__).parent
    src_text += "\n" + "\n".join(p.read_text() for p in core_root.rglob("*.py"))

    env_vars = [
        ev["name"]
        for pkg in server.get("packages", [])
        for ev in pkg.get("environmentVariables", [])
    ]
    missing = [name for name in env_vars if name not in src_text]
    assert not missing, (
        f"server.json declares env vars not referenced in src/ or core: {missing}"
    )
