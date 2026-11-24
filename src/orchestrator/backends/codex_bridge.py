"""Small stdio-to-Unix-socket bridge for Codex's public launch_args_override."""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
from pathlib import Path


def _connect(path: Path, timeout_seconds: float = 5.0) -> socket.socket:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            connection.connect(str(path))
            return connection
        except (FileNotFoundError, ConnectionRefusedError, OSError):
            connection.close()
            time.sleep(0.02)
    raise ConnectionError("independent Codex owner did not accept the SDK bridge")


def _copy_input(connection: socket.socket) -> None:
    try:
        while chunk := os.read(sys.stdin.fileno(), 64 * 1024):
            connection.sendall(chunk)
    except (BrokenPipeError, OSError):
        pass
    finally:
        try:
            connection.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def _copy_output(connection: socket.socket) -> None:
    try:
        while chunk := connection.recv(64 * 1024):
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
    except (BrokenPipeError, OSError):
        pass
    finally:
        try:
            connection.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--socket", required=True)
    arguments = parser.parse_args()
    try:
        connection = _connect(Path(arguments.socket))
    except OSError:
        return 70
    upstream = threading.Thread(target=_copy_input, args=(connection,), daemon=True)
    upstream.start()
    _copy_output(connection)
    try:
        connection.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    connection.close()
    upstream.join(timeout=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
