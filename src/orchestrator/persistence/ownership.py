"""Single-process coordinator ownership using an OS lock and durable generation."""

from __future__ import annotations

import errno
import fcntl
import os
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from uuid import uuid4

from orchestrator.persistence.ledger import SQLiteLedger
from orchestrator.persistence.models import OwnerLease


class OwnershipUnavailable(RuntimeError):
    """Another process currently owns the coordinator lock."""


class CoordinatorOwnership:
    """Hold one non-blocking OS lock and persist each successful owner generation."""

    def __init__(self, ledger: SQLiteLedger, lock_path: Path | str) -> None:
        self.ledger = ledger
        self.lock_path = Path(lock_path).expanduser()
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._descriptor: int | None = None
        self._lease: OwnerLease | None = None

    @property
    def lease(self) -> OwnerLease | None:
        return self._lease

    def acquire(
        self, owner_id: str | None = None, acquired_at: datetime | None = None
    ) -> OwnerLease:
        if self._lease is not None:
            return self._lease
        identity = owner_id or str(uuid4())
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            os.close(descriptor)
            if error.errno in {errno.EACCES, errno.EAGAIN}:
                raise OwnershipUnavailable(f"coordinator lock is held: {self.lock_path}") from error
            raise
        try:
            lease = self.ledger._acquire_owner(identity, acquired_at or datetime.now(UTC))
        except BaseException:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
            raise
        self._descriptor = descriptor
        self._lease = lease
        return lease

    def release(self, released_at: datetime | None = None) -> None:
        if self._lease is None or self._descriptor is None:
            return
        descriptor = self._descriptor
        lease = self._lease
        self._descriptor = None
        self._lease = None
        try:
            self.ledger._release_owner(lease, released_at or datetime.now(UTC))
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def __enter__(self) -> OwnerLease:
        return self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()
