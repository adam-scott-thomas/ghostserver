"""FastMCP entry point. Creates the server and mounts enabled adapters."""
from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from conduit.boot import boot


def create_server(config_path: Path | None = None) -> FastMCP:
    core = boot(config_path=config_path)
    config = core.get("config")

    main = FastMCP(
        name="Conduit",
        instructions=(
            "Local MCP server connecting to GitHub, Gmail, Google Calendar, "
            "Cloudflare, and AWS. All tokens stored locally via 1Password."
        ),
    )

    from conduit.adapters import discover

    for service_name, mod in discover():
        if config.is_enabled(service_name):
            main.mount(mod.server)

    return main


def main() -> None:
    server = create_server()
    server.run()


if __name__ == "__main__":
    main()
