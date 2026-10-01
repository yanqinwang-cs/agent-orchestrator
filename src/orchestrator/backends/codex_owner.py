"""Attempt-scoped process owner used behind the pinned SDK's public launch override.

The owner is a detached local helper process. It starts the pinned app-server with an
allowlisted environment, proxies the SDK stdio stream, and writes a settlement receipt
only after it has waited for the exact child and observed the SDK bridge disconnect.
"""

from __future__ import annotations

import json
import os
import select
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

_SOCKET_ROOT = Path("/tmp")
_OWNER_PREFIX = "orchestrator-codex"
_MAX_MESSAGE = 16 * 1024


class OwnerError(RuntimeError):
    """The independent process owner could not prove the requested state."""


@dataclass(slots=True)
class ProcessOwner:
    owner_id: str
    generation: str
    owner_dir: Path
    control_path: Path
    data_path: Path
    status_path: Path
    _process: subprocess.Popen[bytes]
    _control: socket.socket
    _control_file: Any
    _request_lock: threading.Lock = field(default_factory=threading.Lock)

    @classmethod
    def launch(
        cls,
        *,
        owner_id: str,
        generation: str,
        codex_home: Path,
        cwd: Path,
        codex_bin: Path,
        environment: dict[str, str],
        shutdown_grace_seconds: float,
        startup_timeout_seconds: float = 5.0,
    ) -> ProcessOwner:
        owner_dir = (codex_home / "orchestrator" / "owners" / owner_id).resolve()
        owner_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
        os.chmod(owner_dir, 0o700)
        socket_dir = _socket_directory()
        control_path = socket_dir / f"{owner_id[:24]}-c.sock"
        data_path = socket_dir / f"{owner_id[:24]}-d.sock"
        status_path = socket_dir / f"{owner_id[:24]}-s.sock"
        spec_path = owner_dir / "launch.json"
        launch_spec = {
            "owner_id": owner_id,
            "generation": generation,
            "owner_dir": str(owner_dir),
            "control_path": str(control_path),
            "data_path": str(data_path),
            "status_path": str(status_path),
            "cwd": str(cwd),
            "parent_pid": os.getpid(),
            "command": [str(codex_bin), "app-server", "--listen", "stdio://"],
            "environment": environment,
            "shutdown_grace_seconds": shutdown_grace_seconds,
        }
        descriptor = os.open(spec_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(launch_spec, output, sort_keys=True)
            output.flush()
            os.fsync(output.fileno())

        owner_environment = {
            "HOME": environment["HOME"],
            "CODEX_HOME": environment["CODEX_HOME"],
            "PATH": environment["PATH"],
            "TMPDIR": environment["TMPDIR"],
            "LANG": "C.UTF-8",
        }
        process = subprocess.Popen(
            [sys.executable, "-m", "orchestrator.backends.codex_owner", "--serve", str(spec_path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(cwd),
            env=owner_environment,
            close_fds=True,
            start_new_session=True,
        )
        deadline = time.monotonic() + startup_timeout_seconds
        control: socket.socket | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise OwnerError("independent process owner exited before readiness")
            try:
                control = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                control.settimeout(max(0.05, deadline - time.monotonic()))
                control.connect(str(control_path))
                break
            except (FileNotFoundError, ConnectionRefusedError, TimeoutError, OSError):
                if control is not None:
                    control.close()
                control = None
                time.sleep(0.02)
        if control is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise OwnerError("independent process owner did not become ready")
        control.settimeout(max(startup_timeout_seconds, shutdown_grace_seconds + 1.0))
        control_file = control.makefile("rwb", buffering=0)
        owner = cls(
            owner_id=owner_id,
            generation=generation,
            owner_dir=owner_dir,
            control_path=control_path,
            data_path=data_path,
            status_path=status_path,
            _process=process,
            _control=control,
            _control_file=control_file,
        )
        hello = owner._request({"op": "hello", "owner_id": owner_id, "generation": generation})
        if (
            hello.get("state") != "running"
            or hello.get("owner_id") != owner_id
            or hello.get("generation") != generation
            or hello.get("process_group_verified") is not True
            or hello.get("process_group_id") != hello.get("child_pid")
        ):
            owner._close_control()
            raise OwnerError("process owner did not verify its exact process identity")
        return owner

    def bridge_command(self) -> tuple[str, ...]:
        """Return the SDK public launch override that proxies app-server stdio."""
        return (
            sys.executable,
            "-m",
            "orchestrator.backends.codex_bridge",
            "--socket",
            str(self.data_path),
        )

    def status(self) -> dict[str, Any]:
        try:
            return self._request(
                {"op": "status", "owner_id": self.owner_id, "generation": self.generation}
            )
        except (OSError, OwnerError, ValueError):
            receipt = self._durable_receipt()
            if receipt is None:
                raise
            return receipt

    def terminate_child(self) -> dict[str, Any]:
        return self._request(
            {"op": "terminate", "owner_id": self.owner_id, "generation": self.generation}
        )

    def settled(self, timeout_seconds: float) -> dict[str, Any] | None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                receipt = self.status()
            except (OSError, OwnerError, ValueError):
                return None
            if receipt.get("settled") is True and receipt.get("generation") == self.generation:
                return receipt
            time.sleep(0.025)
        return None

    def stop(self) -> dict[str, Any]:
        response: dict[str, Any] | None
        try:
            try:
                response = self._request(
                    {"op": "stop", "owner_id": self.owner_id, "generation": self.generation}
                )
            except (OSError, OwnerError, ValueError):
                response = self._durable_receipt()
                if response is None or response.get("generation") != self.generation:
                    return {"settled": False, "detail": "owner receipt is unavailable"}
        finally:
            self._close_control()
        try:
            self._process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            return {"settled": False, "detail": "owner process did not exit after receipt"}
        return response

    def wait(self, timeout_seconds: float) -> bool:
        try:
            self._process.wait(timeout=timeout_seconds)
            return True
        except subprocess.TimeoutExpired:
            return False

    def _durable_receipt(self) -> dict[str, Any] | None:
        home = self.owner_dir.parents[2]
        receipt = inspect_receipt(home, self.owner_id)
        if receipt is None or receipt.get("generation") != self.generation:
            return None
        return receipt

    def _request(self, message: dict[str, Any]) -> dict[str, Any]:
        with self._request_lock:
            encoded = json.dumps(message, separators=(",", ":")).encode() + b"\n"
            self._control_file.write(encoded)
            response = self._control_file.readline(_MAX_MESSAGE + 1)
            if not response or len(response) > _MAX_MESSAGE:
                raise OwnerError("process owner control channel ended without a bounded receipt")
            value = json.loads(response)
            if not isinstance(value, dict) or value.get("ok") is not True:
                raise OwnerError("process owner rejected the exact owner command")
            if value.get("owner_id") != self.owner_id or value.get("generation") != self.generation:
                raise OwnerError("process owner response has a conflicting identity")
            return value

    def _close_control(self) -> None:
        with self._request_lock:
            try:
                self._control_file.close()
            except OSError:
                pass
            try:
                self._control.close()
            except OSError:
                pass


def _socket_directory() -> Path:
    directory = _SOCKET_ROOT / f"{_OWNER_PREFIX}-{os.getuid()}"
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) & 0o077
    ):
        raise OwnerError("process-owner socket directory is not private to the current user")
    return directory


def inspect_receipt(codex_home: Path, owner_id: str) -> dict[str, Any] | None:
    """Read an immutable owner-written receipt; never infer settlement from a missing socket."""
    receipt_path = codex_home / "orchestrator" / "owners" / owner_id / "receipt.json"
    try:
        raw = receipt_path.read_bytes()
        receipt = json.loads(raw)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if (
        not isinstance(receipt, dict)
        or receipt.get("owner_id") != owner_id
        or receipt.get("settled") is not True
        or receipt.get("child_reaped") is not True
        or receipt.get("process_group_empty") is not True
        or receipt.get("bridge_disconnected") is not True
        or receipt.get("receipt_sha256")
        != sha256(
            json.dumps(
                {key: value for key, value in receipt.items() if key != "receipt_sha256"},
                sort_keys=True,
            ).encode()
        ).hexdigest()
    ):
        return None
    return receipt


def query_owner_status(
    owner_id: str, generation: str, timeout_seconds: float = 0.25
) -> dict[str, Any] | None:
    """Query a live exact owner over its private status socket without reattaching to Codex."""
    path = _socket_directory() / f"{owner_id[:24]}-s.sock"
    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.settimeout(timeout_seconds)
    try:
        connection.connect(str(path))
        connection.sendall(
            json.dumps(
                {"op": "status", "owner_id": owner_id, "generation": generation},
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )
        raw = b""
        while b"\n" not in raw and len(raw) <= _MAX_MESSAGE:
            chunk = connection.recv(4096)
            if not chunk:
                break
            raw += chunk
        if not raw or len(raw) > _MAX_MESSAGE:
            return None
        response = json.loads(raw.split(b"\n", 1)[0])
        if (
            not isinstance(response, dict)
            or response.get("ok") is not True
            or response.get("owner_id") != owner_id
            or response.get("generation") != generation
        ):
            return None
        return response
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    finally:
        connection.close()


def _write_receipt(owner_dir: Path, receipt: dict[str, Any]) -> None:
    unsigned = dict(receipt)
    unsigned["receipt_sha256"] = sha256(json.dumps(unsigned, sort_keys=True).encode()).hexdigest()
    target = owner_dir / "receipt.json"
    temporary = owner_dir / ".receipt.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(unsigned, output, sort_keys=True)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, target)


def _read_control(reader: Any) -> dict[str, Any] | None:
    raw = reader.readline(_MAX_MESSAGE + 1)
    if not raw:
        return None
    if len(raw) > _MAX_MESSAGE:
        return {"op": "invalid"}
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"op": "invalid"}
    return value if isinstance(value, dict) else {"op": "invalid"}


def _serve(spec_path: Path) -> int:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    owner_id = spec["owner_id"]
    generation = spec["generation"]
    owner_dir = Path(spec["owner_dir"])
    control_path = Path(spec["control_path"])
    data_path = Path(spec["data_path"])
    status_path = Path(spec["status_path"])
    for stale_path in (control_path, data_path, status_path):
        stale_path.unlink(missing_ok=True)
    control_listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    data_listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    status_listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    control_listener.bind(str(control_path))
    data_listener.bind(str(data_path))
    status_listener.bind(str(status_path))
    os.chmod(control_path, 0o600)
    os.chmod(data_path, 0o600)
    os.chmod(status_path, 0o600)
    control_listener.listen(1)
    data_listener.listen(1)
    status_listener.listen(4)
    control_listener.settimeout(0.2)
    data_listener.settimeout(0.2)
    status_listener.settimeout(0.2)

    child = subprocess.Popen(
        spec["command"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=spec["cwd"],
        env=spec["environment"],
        close_fds=True,
        start_new_session=True,
    )
    lock = threading.RLock()
    settle_lock = threading.Lock()
    bridge_closed = threading.Event()
    child_reaped = threading.Event()
    process_group_empty = threading.Event()
    stop_owner = threading.Event()
    shutdown: dict[str, Any] = {"requested": False, "reason": None}

    def status_loop() -> None:
        while not stop_owner.is_set():
            try:
                connection, _ = status_listener.accept()
            except TimeoutError:
                continue
            with connection:
                try:
                    reader = connection.makefile("rb")
                    raw = reader.readline(_MAX_MESSAGE + 1)
                    request = json.loads(raw) if raw and len(raw) <= _MAX_MESSAGE else {}
                    if (
                        not isinstance(request, dict)
                        or request.get("owner_id") != owner_id
                        or request.get("generation") != generation
                        or request.get("op") != "status"
                    ):
                        response: dict[str, Any] = {"ok": False}
                    else:
                        reaped = child_reaped.is_set() or child.poll() is not None
                        group_empty = process_group_empty.is_set()
                        response = {
                            "ok": True,
                            "state": (
                                "settled"
                                if reaped and group_empty and bridge_closed.is_set()
                                else "running"
                            ),
                            "owner_id": owner_id,
                            "generation": generation,
                            "child_pid": child.pid,
                            "child_returncode": child.returncode if reaped else None,
                            "child_reaped": reaped,
                            "process_group_id": child.pid,
                            "process_group_empty": group_empty,
                            "bridge_connected": not bridge_closed.is_set(),
                            "settled": reaped and group_empty and bridge_closed.is_set(),
                        }
                    connection.sendall(json.dumps(response, separators=(",", ":")).encode() + b"\n")
                except (OSError, ValueError, json.JSONDecodeError):
                    continue

    threading.Thread(target=status_loop, name="codex-owner-status", daemon=True).start()

    def process_group_exists() -> bool:
        try:
            os.killpg(child.pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def settle_child(reason: str) -> bool:
        with settle_lock:
            if child_reaped.is_set() and process_group_empty.is_set():
                return True
            with lock:
                if not shutdown["requested"]:
                    shutdown["requested"] = True
                    shutdown["reason"] = reason
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                process_group_empty.set()
            grace_deadline = time.monotonic() + max(0.1, float(spec["shutdown_grace_seconds"]))
            if child.poll() is None:
                try:
                    child.wait(timeout=max(0.001, grace_deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    pass
            if child.poll() is not None:
                child.wait()
                child_reaped.set()

            while process_group_exists() and time.monotonic() < grace_deadline:
                time.sleep(0.025)
            if process_group_exists():
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                kill_deadline = time.monotonic() + 1.0
                while process_group_exists() and time.monotonic() < kill_deadline:
                    time.sleep(0.025)
            if child.poll() is not None and not child_reaped.is_set():
                child.wait()
                child_reaped.set()
            if not process_group_exists():
                process_group_empty.set()
            return child_reaped.is_set() and process_group_empty.is_set()

    def watch_service_parent() -> None:
        while not stop_owner.wait(0.05):
            if os.getppid() != int(spec["parent_pid"]):
                settle_child("service_parent_disconnected")
                stop_owner.set()
                return

    threading.Thread(
        target=watch_service_parent,
        name="codex-owner-parent-watch",
        daemon=True,
    ).start()

    stderr_hash = sha256()

    def drain_stderr() -> None:
        if child.stderr is None:
            return
        while chunk := os.read(child.stderr.fileno(), 4096):
            stderr_hash.update(chunk)

    threading.Thread(target=drain_stderr, name="codex-owner-stderr", daemon=True).start()
    control_connection: socket.socket | None = None
    bridge_connection: socket.socket | None = None
    try:
        while control_connection is None:
            if child.poll() is not None:
                settled = settle_child("app_server_exited_before_owner_handshake")
                bridge_closed.set()
                if settled:
                    _write_receipt(
                        owner_dir,
                        {
                            "owner_id": owner_id,
                            "generation": generation,
                            "settled": True,
                            "child_returncode": child.returncode,
                            "child_reaped": True,
                            "process_group_id": child.pid,
                            "process_group_empty": True,
                            "bridge_disconnected": True,
                            "settled_reason": "app_server_exited_before_owner_handshake",
                        },
                    )
                return 0
            try:
                control_connection, _ = control_listener.accept()
            except TimeoutError:
                continue
        control_file = control_connection.makefile("rwb", buffering=0)
        reader = control_file

        def respond(payload: dict[str, Any]) -> None:
            control_file.write(
                json.dumps({"ok": True, **payload}, separators=(",", ":")).encode() + b"\n"
            )

        def control_loop() -> None:
            while not stop_owner.is_set():
                try:
                    readable, _, _ = select.select([control_connection], [], [], 0.2)
                    if not readable:
                        continue
                    request = _read_control(reader)
                except (OSError, ValueError):
                    continue
                if request is None:
                    settle_child("control_owner_disconnected")
                    stop_owner.set()
                    return
                if request.get("owner_id") != owner_id or request.get("generation") != generation:
                    respond({"error": "owner_identity_mismatch"})
                    continue
                op = request.get("op")
                if op == "hello":
                    try:
                        process_group_id = os.getpgid(child.pid)
                    except ProcessLookupError:
                        process_group_id = None
                    respond(
                        {
                            "state": "running",
                            "owner_id": owner_id,
                            "generation": generation,
                            "child_pid": child.pid,
                            "process_group_id": process_group_id,
                            "process_group_verified": process_group_id == child.pid,
                        }
                    )
                elif op == "status":
                    reaped = child_reaped.is_set() or child.poll() is not None
                    connected = not bridge_closed.is_set()
                    group_empty = process_group_empty.is_set()
                    settled = reaped and group_empty and not connected
                    respond(
                        {
                            "state": "settled" if settled else "running",
                            "owner_id": owner_id,
                            "generation": generation,
                            "child_pid": child.pid,
                            "child_returncode": child.returncode if reaped else None,
                            "child_reaped": reaped,
                            "process_group_id": child.pid,
                            "process_group_empty": group_empty,
                            "bridge_connected": connected,
                            "settled": settled,
                        }
                    )
                elif op == "terminate":
                    settle_child("requested_close")
                    respond(
                        {
                            "owner_id": owner_id,
                            "generation": generation,
                            "child_returncode": child.returncode,
                            "child_reaped": child_reaped.is_set(),
                            "process_group_id": child.pid,
                            "process_group_empty": process_group_empty.is_set(),
                            "bridge_connected": not bridge_closed.is_set(),
                        }
                    )
                elif op == "stop":
                    if (
                        not child_reaped.is_set()
                        or not process_group_empty.is_set()
                        or not bridge_closed.is_set()
                    ):
                        respond({"error": "owner_not_settled"})
                        continue
                    receipt = {
                        "owner_id": owner_id,
                        "generation": generation,
                        "settled": True,
                        "child_returncode": child.returncode,
                        "child_pid": child.pid,
                        "child_reaped": True,
                        "process_group_id": child.pid,
                        "process_group_empty": True,
                        "bridge_disconnected": True,
                        "settled_reason": shutdown["reason"] or "app_server_exited",
                        "stderr_sha256": stderr_hash.hexdigest(),
                    }
                    _write_receipt(owner_dir, receipt)
                    respond(receipt)
                    stop_owner.set()
                    return
                else:
                    respond({"error": "unsupported_owner_operation"})

        control_thread = threading.Thread(
            target=control_loop, name="codex-owner-control", daemon=True
        )
        control_thread.start()
        while bridge_connection is None and not stop_owner.is_set():
            if child.poll() is not None:
                settle_child("app_server_exited")
                break
            try:
                bridge_connection, _ = data_listener.accept()
            except TimeoutError:
                continue
        if bridge_connection is not None:
            child_stdin = child.stdin
            child_stdout = child.stdout
            if child_stdin is None or child_stdout is None:
                raise OwnerError("Codex app-server stdio pipes were not created")
            child_stdin_fd = child_stdin.fileno()
            child_stdout_fd = child_stdout.fileno()
            bridge_connection.settimeout(None)

            def socket_to_child() -> None:
                try:
                    while chunk := bridge_connection.recv(64 * 1024):
                        os.write(child_stdin_fd, chunk)
                except (BrokenPipeError, OSError):
                    pass
                finally:
                    try:
                        child_stdin.close()
                    except OSError:
                        pass

            def child_to_socket() -> None:
                try:
                    while chunk := os.read(child_stdout_fd, 64 * 1024):
                        bridge_connection.sendall(chunk)
                except (BrokenPipeError, OSError):
                    pass
                finally:
                    try:
                        bridge_connection.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass

            upstream = threading.Thread(
                target=socket_to_child, name="codex-owner-input", daemon=True
            )
            downstream = threading.Thread(
                target=child_to_socket, name="codex-owner-output", daemon=True
            )
            upstream.start()
            downstream.start()

            def observe_bridge_disconnect() -> None:
                upstream.join()
                downstream.join()
                bridge_closed.set()

            threading.Thread(
                target=observe_bridge_disconnect,
                name="codex-owner-bridge-settlement",
                daemon=True,
            ).start()
            while child.poll() is None and not stop_owner.wait(0.025):
                pass
            if child.poll() is not None:
                settle_child("app_server_exited")
            if not bridge_closed.wait(float(spec["shutdown_grace_seconds"]) + 5.0):
                try:
                    bridge_connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                bridge_connection.close()
                bridge_closed.wait(1.0)
        settle_child("owner_stopping")
        if control_connection is not None:
            control_connection.shutdown(socket.SHUT_RDWR)
            control_connection.close()
        return 0
    finally:
        settle_child("owner_finalizer")
        if bridge_connection is not None:
            bridge_connection.close()
        else:
            bridge_closed.set()
        if control_connection is not None:
            control_connection.close()
        if child_reaped.is_set() and process_group_empty.is_set() and bridge_closed.is_set():
            existing = inspect_receipt(Path(spec["environment"]["CODEX_HOME"]), owner_id)
            if existing is None:
                _write_receipt(
                    owner_dir,
                    {
                        "owner_id": owner_id,
                        "generation": generation,
                        "settled": True,
                        "child_returncode": child.returncode,
                        "child_pid": child.pid,
                        "child_reaped": True,
                        "process_group_id": child.pid,
                        "process_group_empty": True,
                        "bridge_disconnected": True,
                        "settled_reason": shutdown["reason"] or "owner_disconnected",
                        "stderr_sha256": stderr_hash.hexdigest(),
                    },
                )
        control_listener.close()
        data_listener.close()
        status_listener.close()
        control_path.unlink(missing_ok=True)
        data_path.unlink(missing_ok=True)
        status_path.unlink(missing_ok=True)


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != "--serve":
        return 64
    return _serve(Path(sys.argv[2]))


if __name__ == "__main__":
    raise SystemExit(main())
