"""Service adapters. Each module exposes a `server` FastMCP instance and a `SERVICE` name."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType


def discover() -> list[tuple[str, "ModuleType"]]:
    """Return (service_name, module) for each adapter that defines SERVICE and server."""
    import importlib

    adapters = []
    for name in ["github", "gmail", "gcal", "cloudflare", "aws"]:
        try:
            mod = importlib.import_module(f"ghostserver.adapters.{name}")
            if hasattr(mod, "server") and hasattr(mod, "SERVICE"):
                adapters.append((mod.SERVICE, mod))
        except ImportError:
            pass
    return adapters
