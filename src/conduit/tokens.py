"""Token storage backed by 1Password CLI. Google OAuth refresh via httpx."""
from __future__ import annotations

import subprocess
import time

import httpx

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class TokenStore:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[str, float]] = {}  # ref -> (token, cached_at)
        self._cache_ttl: float = 300.0  # 5 min cache for op reads

    def get(self, op_ref: str) -> str:
        now = time.time()
        if op_ref in self._cache:
            token, cached_at = self._cache[op_ref]
            if now - cached_at < self._cache_ttl:
                return token

        result = subprocess.run(
            ["op", "read", op_ref],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"1Password read failed: {result.stderr.strip()}")

        token = result.stdout.strip()
        self._cache[op_ref] = (token, now)
        return token

    def refresh_google(
        self, client_id: str, client_secret: str, refresh_token: str,
    ) -> str:
        resp = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["access_token"]

    def clear_cache(self) -> None:
        self._cache.clear()
