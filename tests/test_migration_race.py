import sqlite3

import pytest

from orchestrator.persistence import SQLiteLedger
from orchestrator.persistence.migrations import CURRENT_SCHEMA_VERSION, apply_migrations


class _RaceProxy:
    """Let a rival connection finish migrating just before this one takes its lock."""

    def __init__(self, inner: sqlite3.Connection, rival: sqlite3.Connection) -> None:
        self.inner = inner
        self.rival = rival
        self.fired = False

    def execute(self, sql, *args):
        if sql.startswith("BEGIN") and not self.fired:
            self.fired = True
            apply_migrations(self.rival)
        return self.inner.execute(sql, *args)

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def commit(self):
        return self.inner.commit()


def test_migration_loser_of_a_race_rereads_the_version_under_the_lock(tmp_path) -> None:
    path = tmp_path / "race.sqlite3"
    rival = sqlite3.connect(path, isolation_level=None)
    loser = sqlite3.connect(path, isolation_level=None, timeout=5)

    assert apply_migrations(_RaceProxy(loser, rival)) == CURRENT_SCHEMA_VERSION  # type: ignore[arg-type]

    count = loser.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert count == CURRENT_SCHEMA_VERSION


def test_ledger_closes_its_connection_when_pragma_setup_fails(tmp_path, monkeypatch) -> None:
    opened: list[sqlite3.Connection] = []
    real_connect = sqlite3.connect

    class _Failing:
        def __init__(self, connection: sqlite3.Connection) -> None:
            self.connection = connection
            self.closed = False

        def execute(self, sql, *args):
            if sql.startswith("PRAGMA synchronous"):
                raise sqlite3.OperationalError("disk I/O error")
            return self.connection.execute(sql, *args)

        def close(self):
            self.closed = True
            self.connection.close()

        def __setattr__(self, name, value):
            if name == "row_factory":
                self.connection.row_factory = value
            else:
                object.__setattr__(self, name, value)

    def connect(*args, **kwargs):
        wrapped = _Failing(real_connect(*args, **kwargs))
        opened.append(wrapped)  # type: ignore[arg-type]
        return wrapped

    monkeypatch.setattr(sqlite3, "connect", connect)
    with pytest.raises(sqlite3.OperationalError):
        SQLiteLedger(tmp_path / "x.sqlite3")
    assert opened[0].closed  # type: ignore[attr-defined]
