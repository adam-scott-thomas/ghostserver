"""One-time Google OAuth2 setup. Run: python -m ghostserver.google_auth"""
from __future__ import annotations

import json
import subprocess
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = "http://localhost:8914/callback"
CALLBACK_PORT = 8914


def _op_read(ref: str) -> str:
    result = subprocess.run(
        ["op", "read", ref],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"1Password read failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _op_write(ref: str, value: str) -> None:
    """Write a secret back to 1Password. ref format: op://Vault/Item/Field"""
    parts = ref.lstrip("op://").split("/")
    if len(parts) != 3:
        raise ValueError(f"Expected op://Vault/Item/Field format, got: {ref}")
    vault, item, field = parts

    result = subprocess.run(
        ["op", "item", "edit", item, f"{field}={value}", f"--vault={vault}"],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(f"1Password write failed: {result.stderr.strip()}")


def _load_google_config():
    """Load ghostserver config and return the GoogleConfig section."""
    from ghostserver.config import load_config
    config_path = Path(__file__).parent.parent.parent / "ghostserver.toml"
    config = load_config(config_path)
    return config.google


def _build_auth_url(client_id: str, scopes: list[str]) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def _exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }).encode()

    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _run_callback_server() -> str:
    """Start a local HTTP server, capture the auth code, and return it."""
    captured: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            if "code" in params:
                captured["code"] = params["code"][0]
                body = b"<html><body><h2>Authorization successful!</h2><p>You may close this window.</p></body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
            else:
                error = params.get("error", ["unknown"])[0]
                body = f"<html><body><h2>Authorization failed: {error}</h2></body></html>".encode()
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, format, *args):
            pass  # suppress default access log

    httpd = HTTPServer(("localhost", CALLBACK_PORT), Handler)
    httpd.handle_request()  # handle exactly one request then stop

    if "code" not in captured:
        raise RuntimeError("No authorization code received from Google.")
    return captured["code"]


def main() -> None:
    print("=== Ghostserver — Google OAuth2 Setup ===\n")

    # Load config
    print("Loading ghostserver config...")
    google = _load_google_config()

    if not google.client_id_ref or not google.client_secret_ref or not google.refresh_token_ref:
        raise RuntimeError(
            "google.client_id_ref, client_secret_ref, and refresh_token_ref must all be "
            "set in ghostserver.toml before running this setup."
        )

    scopes = google.scopes or [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/calendar",
    ]

    # Read credentials from 1Password
    print(f"Reading client_id from 1Password ({google.client_id_ref})...")
    client_id = _op_read(google.client_id_ref)

    print(f"Reading client_secret from 1Password ({google.client_secret_ref})...")
    client_secret = _op_read(google.client_secret_ref)

    # Build consent URL and open browser
    auth_url = _build_auth_url(client_id, scopes)
    print(f"\nOpening browser to Google consent screen...")
    print(f"URL: {auth_url}\n")
    webbrowser.open(auth_url)

    # Wait for redirect
    print(f"Waiting for OAuth callback on port {CALLBACK_PORT}...")
    code = _run_callback_server()
    print("Authorization code received.")

    # Exchange code for tokens
    print("Exchanging code for tokens...")
    tokens = _exchange_code(client_id, client_secret, code)

    if "refresh_token" not in tokens:
        raise RuntimeError(
            "No refresh_token in response. If you already authorized this app, "
            "revoke access at https://myaccount.google.com/permissions and try again."
        )

    refresh_token = tokens["refresh_token"]

    # Store refresh token in 1Password
    print(f"Storing refresh token in 1Password ({google.refresh_token_ref})...")
    _op_write(google.refresh_token_ref, refresh_token)

    print("\nSetup complete! Refresh token stored successfully.")
    print(f"Access token (temporary): {tokens.get('access_token', '')[:20]}...")


if __name__ == "__main__":
    main()
