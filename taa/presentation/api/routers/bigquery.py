"""BigQuery export and artefact download endpoints."""

from __future__ import annotations

import io
import os
import tempfile
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from taa.infrastructure.config.container import Container
from taa.application.dtos.models import GenerationRequest
from taa.presentation.api.dependencies import get_container
from taa.presentation.api.schemas import ExportRequest, ExportResponse, ExportFileInfo

router = APIRouter()

# In-memory store for generated ZIP files (keyed by download_id)
_zip_store: dict[str, bytes] = {}


@router.post("/export", response_model=ExportResponse)
def export_pack(
    req: ExportRequest,
    container: Container = Depends(get_container),
) -> ExportResponse:
    """Generate full artefact pack and return a download link."""
    with tempfile.TemporaryDirectory() as tmpdir:
        gen_request = GenerationRequest(
            domains=req.domains,
            jurisdiction=req.jurisdiction,
            vendor=req.vendor,
            output_dir=Path(tmpdir),
            include_terraform=req.include_terraform,
            include_pipelines=req.include_pipelines,
            include_dags=req.include_dags,
            include_compliance=req.include_compliance,
        )
        result = container.generate_full_pack.execute(gen_request)

        # Collect all generated files into a ZIP
        buf = io.BytesIO()
        file_infos: list[ExportFileInfo] = []

        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(tmpdir):
                for fname in files:
                    full_path = os.path.join(root, fname)
                    arc_name = os.path.relpath(full_path, tmpdir)
                    file_size = os.path.getsize(full_path)
                    zf.write(full_path, arc_name)

                    ext = os.path.splitext(fname)[1].lstrip(".")
                    file_infos.append(ExportFileInfo(
                        name=arc_name,
                        size=file_size,
                        type=ext or "unknown",
                    ))

        download_id = str(uuid.uuid4())
        _zip_store[download_id] = buf.getvalue()

        # Keep store bounded (max 50 entries)
        if len(_zip_store) > 50:
            oldest = next(iter(_zip_store))
            del _zip_store[oldest]

        return ExportResponse(
            success=result.success,
            file_count=len(file_infos),
            files=file_infos,
            download_id=download_id,
        )


@router.get("/download/{download_id}")
def download_zip(download_id: str) -> StreamingResponse:
    """Download a previously generated artefact ZIP."""
    data = _zip_store.get(download_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Download not found or expired")

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=taa_artefacts_{download_id[:8]}.zip"},
    )
