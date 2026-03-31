"""Capability gating: enabled check + time-windowed rate limiting."""
from __future__ import annotations

import time

from spine import Core


class ServiceDisabled(Exception):
    pass


class RateLimitExceeded(Exception):
    pass


_windows: dict[str, list[float]] = {}


def check_gate(service: str) -> None:
    core = Core.instance()
    config = core.get("config")

    if not config.is_enabled(service):
        raise ServiceDisabled(f"Service '{service}' is disabled in config")

    limit, window = config.rate_for(service)
    now = time.time()
    timestamps = _windows.setdefault(service, [])
    timestamps[:] = [t for t in timestamps if now - t < window]

    if len(timestamps) >= limit:
        raise RateLimitExceeded(
            f"Service '{service}' rate limit exceeded: {limit} calls per {window}s"
        )
    timestamps.append(now)


def reset_counters() -> None:
    _windows.clear()
