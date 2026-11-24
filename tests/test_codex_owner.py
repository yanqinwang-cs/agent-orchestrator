from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

from orchestrator.backends.codex_owner import ProcessOwner, inspect_receipt, query_owner_status


def _environment(home: Path, temp_dir: Path) -> dict[str, str]:
    return {
        "HOME": str(home),
        "CODEX_HOME": str(home),
        "PATH": os.pathsep.join(("/usr/bin", "/bin")),
        "TMPDIR": str(temp_dir),
        "LANG": "C.UTF-8",
    }


def _write_fake_codex(path: Path, child_pid_path: Path) -> None:
    child_code = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"
    source = "\n".join(
        (
            "#!/usr/bin/env python3",
            "import subprocess, sys",
            "from pathlib import Path",
            "sys.stdin.buffer.read(1)",
            f"child = subprocess.Popen([sys.executable, '-c', {child_code!r}])",
            f"Path({str(child_pid_path)!r}).write_text(str(child.pid), encoding='utf-8')",
            "",
        )
    )
    path.write_text(source, encoding="utf-8")
    path.chmod(0o700)


def _launch_owner(tmp_path: Path, owner_id: str) -> tuple[ProcessOwner, Path, Path]:
    home = tmp_path / "codex-home"
    cwd = tmp_path / "server-cwd"
    home.mkdir()
    cwd.mkdir()
    child_pid_path = tmp_path / "descendant.pid"
    executable = tmp_path / "fake-codex"
    _write_fake_codex(executable, child_pid_path)
    owner = ProcessOwner.launch(
        owner_id=owner_id,
        generation=owner_id,
        codex_home=home,
        cwd=cwd,
        codex_bin=executable,
        environment=_environment(home, tmp_path),
        shutdown_grace_seconds=0.2,
        startup_timeout_seconds=4,
    )
    return owner, home, child_pid_path


def test_owner_settlement_includes_same_group_child_after_app_server_exit(tmp_path) -> None:

    owner_id = str(uuid4())
    owner, home, child_pid_path = _launch_owner(tmp_path, owner_id)
    assert query_owner_status(owner_id, owner_id)["generation"] == owner_id
    assert query_owner_status(owner_id, "wrong-generation") is None
    bridge = subprocess.Popen(
        owner.bridge_command(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_environment(home, tmp_path),
        cwd=tmp_path,
    )
    assert bridge.stdin is not None
    bridge.stdin.write(b"x")
    bridge.stdin.flush()
    bridge.stdin.close()
    assert bridge.wait(timeout=6) == 0

    deadline = time.monotonic() + 3
    while not child_pid_path.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert child_pid_path.exists()
    receipt = owner.settled(3)
    assert receipt is not None, {
        "owner_exit_code": owner._process.poll(),
        "durable_receipt": inspect_receipt(home, owner_id),
    }
    assert receipt["child_reaped"] is True
    assert receipt["process_group_empty"] is True
    assert receipt.get("bridge_connected") is False or receipt["bridge_disconnected"] is True

    stopped = owner.stop()
    assert stopped["settled"] is True
    assert owner.wait(2)
    durable = inspect_receipt(home, owner_id)
    assert durable is not None
    assert durable["generation"] == owner_id
    assert durable["process_group_id"] == durable["child_pid"]
    assert query_owner_status(owner_id, "wrong-generation") is None


def test_independent_owner_settles_when_service_parent_exits(tmp_path) -> None:
    owner_id = str(uuid4())
    home = tmp_path / "parent-loss-home"
    cwd = tmp_path / "parent-loss-cwd"
    executable = tmp_path / "parent-loss-codex"
    marker = tmp_path / "owner-launched.json"
    home.mkdir()
    cwd.mkdir()
    _write_fake_codex(executable, tmp_path / "unused-descendant.pid")
    environment = _environment(home, tmp_path)
    service_code = "\n".join(
        (
            "import json, os",
            "from pathlib import Path",
            "from orchestrator.backends.codex_owner import ProcessOwner",
            "owner = ProcessOwner.launch(",
            f"    owner_id={owner_id!r}, generation={owner_id!r},",
            f"    codex_home=Path({str(home)!r}), cwd=Path({str(cwd)!r}),",
            f"    codex_bin=Path({str(executable)!r}), environment={environment!r},",
            "    shutdown_grace_seconds=0.2, startup_timeout_seconds=4,",
            ")",
            f"Path({str(marker)!r}).write_text(json.dumps({{'owner_id': owner.owner_id}}))",
            "os._exit(0)",
            "",
        )
    )
    service = subprocess.Popen(
        [sys.executable, "-c", service_code],
        cwd=Path(__file__).resolve().parents[1],
        env=os.environ.copy(),
    )
    assert service.wait(timeout=6) == 0
    assert json.loads(marker.read_text(encoding="utf-8"))["owner_id"] == owner_id

    deadline = time.monotonic() + 6
    receipt = None
    while time.monotonic() < deadline:
        receipt = inspect_receipt(home, owner_id)
        if receipt is not None:
            break
        time.sleep(0.05)
    assert receipt is not None
    assert receipt["generation"] == owner_id
    assert receipt["settled_reason"] in {
        "control_owner_disconnected",
        "service_parent_disconnected",
    }
    assert receipt["child_reaped"] is True
    assert receipt["process_group_empty"] is True
