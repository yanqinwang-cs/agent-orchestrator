"""Local-only server entry point for the Agent Lab JSON API."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from wsgiref.simple_server import make_server

from agent_lab.http_api import SQLiteApi
from agent_lab.persistence import SQLiteStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Agent Lab discovery API.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(os.environ.get("AGENT_LAB_DATABASE", "~/.agent-lab/agent-lab.sqlite3")),
    )
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    store = SQLiteStore(arguments.database.expanduser())
    application = SQLiteApi(store)
    address = ("127.0.0.1", arguments.port)
    with make_server(*address, application) as server:
        print(f"Agent Lab API listening on http://{address[0]}:{address[1]}")
        server.serve_forever()


if __name__ == "__main__":
    main()
