"""Orchestrates generation of all artefact types for an export pack."""

from __future__ import annotations

import tempfile
import time
import threading
import uuid
from pathlib import Path
from typing import Any

from taa.application.dtos.models import GenerationRequest, GenerationResult
from taa.infrastructure.export.zip_builder import ZipBuilder


# ---------------------------------------------------------------------------
# Temporary export store with TTL-based cleanup
# ---------------------------------------------------------------------------

_DEFAULT_TTL_SECONDS: int = 600  # 10 minutes
_MAX_STORE_SIZE: int = 50


class _ExportEntry:
    """An entry in the export store."""

    __slots__ = ("data", "created_at")

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.created_at = time.monotonic()

    def is_expired(self, ttl: float) -> bool:
        return (time.monotonic() - self.created_at) > ttl


class ExportStore:
    """Thread-safe, TTL-bounded store for generated ZIP archives.

    Exports are kept in memory keyed by a UUID-based export id.
    Expired entries are pruned on every ``put`` and on explicit
    ``cleanup`` calls.
    """

    def __init__(self, ttl_seconds: int = _DEFAULT_TTL_SECONDS, max_size: int = _MAX_STORE_SIZE) -> None:
        self._store: dict[str, _ExportEntry] = {}
        self._lock = threading.Lock()
        self._ttl = float(ttl_seconds)
        self._max_size = max_size

    # -- public API --

    def put(self, data: bytes) -> str:
        """Store ZIP bytes and return a download id."""
        export_id = str(uuid.uuid4())
        with self._lock:
            self._evict_expired()
            # Hard cap: drop oldest if over limit.
            while len(self._store) >= self._max_size:
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]
            self._store[export_id] = _ExportEntry(data)
        return export_id

    def get(self, export_id: str) -> bytes | None:
        """Retrieve ZIP bytes by export id, or ``None`` if missing/expired."""
        with self._lock:
            entry = self._store.get(export_id)
            if entry is None:
                return None
            if entry.is_expired(self._ttl):
                del self._store[export_id]
                return None
            return entry.data

    def cleanup(self) -> int:
        """Evict all expired entries. Returns number of entries removed."""
        with self._lock:
            return self._evict_expired()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)

    # -- private --

    def _evict_expired(self) -> int:
        expired_keys = [k for k, v in self._store.items() if v.is_expired(self._ttl)]
        for k in expired_keys:
            del self._store[k]
        return len(expired_keys)


# Module-level singleton used by the router.
export_store = ExportStore()


class FileGenerator:
    """Orchestrates generation and ZIP packaging of all artefact types.

    Uses the application layer ``GenerateFullPackCommand`` (via the DI
    container) to produce files on disk, then delegates to
    :class:`ZipBuilder` to package them.
    """

    def __init__(self) -> None:
        self._zip_builder = ZipBuilder()

    def generate_and_package(
        self,
        *,
        generate_fn: Any,
        request: GenerationRequest,
    ) -> tuple[GenerationResult, bytes, list[dict[str, Any]]]:
        """Run generation into a temp directory, build a ZIP.

        Args:
            generate_fn: A callable accepting a ``GenerationRequest``
                         and returning a ``GenerationResult``.  Typically
                         ``container.generate_full_pack.execute``.
            request: The generation request (its ``output_dir`` will be
                     overridden to point at a temp directory).

        Returns:
            ``(result, zip_bytes, file_infos)``
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            patched = request.model_copy(update={"output_dir": tmp_path})

            result = generate_fn(patched)

            zip_bytes, file_infos = self._zip_builder.build_from_directory(
                tmp_path,
                domains=patched.domains,
                jurisdiction=patched.jurisdiction,
                vendor=patched.vendor,
                include_terraform=patched.include_terraform,
                include_pipelines=patched.include_pipelines,
                include_dags=patched.include_dags,
                include_compliance=patched.include_compliance,
            )

        return result, zip_bytes, file_infos
