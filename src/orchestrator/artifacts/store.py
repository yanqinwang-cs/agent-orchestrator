"""Atomic, content-addressed publication of run artifacts outside SQLite."""

from __future__ import annotations

import os
import re
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from uuid import uuid4

from orchestrator.domain.models import Artifact
from orchestrator.persistence.ledger import ImmutableSpecificationConflict, SQLiteLedger
from orchestrator.persistence.models import ArtifactManifest, ArtifactPublication


class ArtifactPathError(ValueError):
    """An artifact identity or managed path is unsafe."""


class ArtifactIntegrityError(RuntimeError):
    """Stored artifact bytes do not match their manifest."""


class ArtifactStore:
    """Stream artifact bytes to managed paths and publish manifests after atomic rename."""

    def __init__(self, data_dir: Path | str, ledger: SQLiteLedger, chunk_size: int = 64 * 1024):
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        self.root = Path(data_dir).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger = ledger
        self.chunk_size = chunk_size

    def publish(
        self,
        publication: ArtifactPublication,
        source: BinaryIO | bytes | bytearray,
    ) -> ArtifactManifest:
        """Write a complete file, atomically publish it, then commit its manifest."""

        self._validate_identity(publication.run_id, "run ID")
        self._validate_identity(publication.attempt_id, "attempt ID")
        attempt = self.ledger.get_attempt(publication.attempt_id)
        if attempt.spec.run_id != publication.run_id:
            raise ArtifactPathError("attempt does not belong to the requested run")

        directory = self._artifact_directory(publication.run_id, publication.attempt_id)
        temporary = directory / f".partial-{uuid4().hex}"
        stream: BinaryIO = BytesIO(source) if isinstance(source, (bytes, bytearray)) else source
        digest = sha256()
        size = 0
        try:
            with temporary.open("xb") as target:
                while chunk := stream.read(self.chunk_size):
                    if not isinstance(chunk, bytes):
                        raise TypeError("artifact source must yield bytes")
                    target.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                target.flush()
                os.fsync(target.fileno())

            content_hash = digest.hexdigest()
            relative_path = PurePosixPath(
                "runs",
                publication.run_id,
                "attempts",
                publication.attempt_id,
                "artifacts",
                content_hash,
            ).as_posix()
            artifact = Artifact(
                id=publication.artifact_id,
                attempt_id=publication.attempt_id,
                input_revision=publication.input_revision,
                workspace_revision=publication.workspace_revision,
                schema_id=publication.schema_id,
                relative_path=relative_path,
                content_hash=content_hash,
            )
            existing = self.ledger.get_artifact_manifest(publication.artifact_id)
            if existing is not None:
                temporary.unlink()
                if existing.artifact != artifact or existing.size_bytes != size:
                    raise ImmutableSpecificationConflict(
                        f"artifact ID {publication.artifact_id} already has different content"
                    )
                self._read_manifest_file(existing)
                return existing

            destination = self._resolve_managed_path(relative_path)
            published_here = False
            if destination.exists():
                self._verify_file(destination, content_hash, size)
                temporary.unlink()
            else:
                os.replace(temporary, destination)
                published_here = True
                self._sync_directory(directory)

            try:
                return self.ledger.record_artifact_manifest(publication, artifact, size)
            except BaseException:
                if published_here:
                    try:
                        manifest = self.ledger.get_artifact_manifest(publication.artifact_id)
                    except BaseException:
                        manifest = None
                    if manifest is None:
                        destination.unlink(missing_ok=True)
                raise
        finally:
            temporary.unlink(missing_ok=True)

    def read(self, artifact_id: str) -> bytes:
        """Read a managed artifact and verify its persisted size and content hash."""

        manifest = self.ledger.get_artifact_manifest(artifact_id)
        if manifest is None:
            raise KeyError(f"unknown artifact {artifact_id}")
        return self._read_manifest_file(manifest)

    def _read_manifest_file(self, manifest: ArtifactManifest) -> bytes:
        path = self._resolve_managed_path(manifest.artifact.relative_path)
        content = path.read_bytes()
        self._verify_content(content, manifest.artifact.content_hash, manifest.size_bytes)
        return content

    def _artifact_directory(self, run_id: str, attempt_id: str) -> Path:
        directory = self.root / "runs" / run_id / "attempts" / attempt_id / "artifacts"
        directory.mkdir(parents=True, exist_ok=True)
        resolved = directory.resolve(strict=True)
        if not resolved.is_relative_to(self.root):
            raise ArtifactPathError(
                "artifact directory resolves outside the configured data folder"
            )
        return resolved

    def _resolve_managed_path(self, relative_path: str) -> Path:
        relative = PurePosixPath(relative_path)
        if (
            relative.is_absolute()
            or "\\" in relative_path
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise ArtifactPathError("artifact manifest contains an unmanaged relative path")
        candidate = self.root.joinpath(*relative.parts)
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(self.root):
            raise ArtifactPathError("artifact path resolves outside the configured data folder")
        return resolved

    @staticmethod
    def _verify_file(path: Path, expected_hash: str, expected_size: int) -> None:
        digest = sha256()
        size = 0
        with path.open("rb") as source:
            while chunk := source.read(64 * 1024):
                digest.update(chunk)
                size += len(chunk)
        if size != expected_size or digest.hexdigest() != expected_hash:
            raise ArtifactIntegrityError(f"content-addressed file is corrupt: {path}")

    @staticmethod
    def _verify_content(content: bytes, expected_hash: str, expected_size: int) -> None:
        if len(content) != expected_size or sha256(content).hexdigest() != expected_hash:
            raise ArtifactIntegrityError("artifact bytes do not match the published manifest")

    @staticmethod
    def _sync_directory(directory: Path) -> None:
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _validate_identity(value: str, name: str) -> None:
        if value in {".", ".."} or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value) is None:
            raise ArtifactPathError(f"{name} is not a managed path segment")
