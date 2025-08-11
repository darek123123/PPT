from __future__ import annotations

"""Core re-exports for a GUI-agnostic API.

This package provides a stable, import-friendly surface that wraps the
existing iop_flow modules without changing physics or behavior.

It also exposes a tiny presets loader based on importlib.resources.
"""

# ruff: noqa: E402 - Re-export pattern after docstring
from importlib import resources
from pathlib import Path
from typing import Any, Dict

# Re-export dataclasses and IO helpers
from iop_flow.schemas import (  # noqa: F401
    AirConditions,
    Engine,
    Geometry,
    LiftPoint,
    FlowSeries,
    CSAProfile,
    Session,
)
from iop_flow.io_json import read_session, write_session  # noqa: F401

# Re-export computation entry points and utilities
from iop_flow.api import run_all, run_compare  # noqa: F401
from iop_flow import formulas  # noqa: F401
from iop_flow import hp  # noqa: F401
from iop_flow import engine_link  # noqa: F401


def load_preset_json(name: str) -> Dict[str, Any]:
    """Load a builtin preset JSON from iop_flow_core.presets.

    Example: load_preset_json("k20a2")
    """
    pkg = __package__ + ".presets"
    candidate = f"{name}.json" if not name.lower().endswith(".json") else name
    # resources.is_resource is deprecated in 3.11; emulate by trying to open
    try:
        with resources.files(pkg).joinpath(candidate).open("r", encoding="utf-8") as f:  # type: ignore[attr-defined]
            import json

            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Preset '{candidate}' not found in {pkg}")


def get_preset_path(name: str) -> Path:
    """Return filesystem path to a builtin preset (for debugging/docs)."""
    pkg = __package__ + ".presets"
    candidate = f"{name}.json" if not name.lower().endswith(".json") else name
    return resources.files(pkg).joinpath(candidate)  # type: ignore[attr-defined]
