"""BigQuery export and artefact download endpoints."""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from taa.infrastructure.config.container import Container
from taa.application.dtos.models import GenerationRequest
from taa.infrastructure.export.file_generator import FileGenerator, export_store
from taa.presentation.api.dependencies import get_container
from taa.presentation.api.schemas import ExportRequest, ExportResponse, ExportFileInfo

router = APIRouter()

_file_generator = FileGenerator()


@router.post("/export", response_model=ExportResponse)
def export_pack(
    req: ExportRequest,
    container: Container = Depends(get_container),
) -> ExportResponse:
    """Generate full artefact pack, store as ZIP, and return a download link."""
    gen_request = GenerationRequest(
        domains=req.domains,
        jurisdiction=req.jurisdiction,
        vendor=req.vendor,
        include_terraform=req.include_terraform,
        include_pipelines=req.include_pipelines,
        include_dags=req.include_dags,
        include_compliance=req.include_compliance,
    )

    result, zip_bytes, file_infos = _file_generator.generate_and_package(
        generate_fn=container.generate_full_pack.execute,
        request=gen_request,
    )

    download_id = export_store.put(zip_bytes)

    return ExportResponse(
        success=result.success,
        file_count=len(file_infos),
        files=[
            ExportFileInfo(
                name=fi["path"],
                size=fi["size"],
                type=fi["type"],
            )
            for fi in file_infos
        ],
        download_id=download_id,
    )


@router.get("/download/{download_id}")
def download_zip(download_id: str) -> StreamingResponse:
    """Download a previously generated artefact ZIP."""
    data = export_store.get(download_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Download not found or expired")

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=taa_artefacts_{download_id[:8]}.zip",
            "Content-Length": str(len(data)),
        },
    )
