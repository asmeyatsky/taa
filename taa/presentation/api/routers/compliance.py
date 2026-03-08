"""Compliance check and reporting endpoints."""

from __future__ import annotations

from pathlib import Path
import tempfile

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from taa.infrastructure.config.container import Container
from taa.application.dtos.models import GenerationRequest
from taa.presentation.api.dependencies import get_container
from taa.presentation.api.schemas import (
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    ComplianceFinding,
)

router = APIRouter()


@router.get("/jurisdictions")
def list_jurisdictions(container: Container = Depends(get_container)) -> list[dict]:
    """List all supported compliance jurisdictions."""
    jurisdictions = container.list_jurisdictions.execute()
    return [j.model_dump() for j in jurisdictions]


@router.post("/check", response_model=ComplianceCheckResponse)
def check_compliance(
    req: ComplianceCheckRequest,
    container: Container = Depends(get_container),
) -> ComplianceCheckResponse:
    """Run compliance assessment against a jurisdiction."""
    rules = container.compliance_rule_repo.load_rules(req.jurisdiction)

    # Get jurisdiction metadata
    jurisdictions = container.list_jurisdictions.execute()
    jur = next((j for j in jurisdictions if j.code == req.jurisdiction), None)
    framework = jur.framework if jur else req.jurisdiction

    findings = [
        ComplianceFinding(
            rule_id=r.rule_id,
            framework=r.framework,
            data_residency_required=r.data_residency_required,
            encryption_required=r.encryption_required,
        )
        for r in rules
    ]

    return ComplianceCheckResponse(
        jurisdiction=req.jurisdiction,
        framework=framework,
        finding_count=len(findings),
        findings=findings,
    )


@router.get("/report")
def get_compliance_report(
    domains: str,
    jurisdiction: str = "SA",
    container: Container = Depends(get_container),
) -> PlainTextResponse:
    """Generate and return a compliance report as markdown."""
    with tempfile.TemporaryDirectory() as tmpdir:
        request = GenerationRequest(
            domains=domains.split(","),
            jurisdiction=jurisdiction,
            output_dir=Path(tmpdir),
        )
        container.generate_compliance.execute(request)

        # Read back the generated markdown
        compliance_dir = Path(tmpdir) / "compliance"
        if compliance_dir.exists():
            parts = []
            for f in sorted(compliance_dir.iterdir()):
                if f.suffix == ".md":
                    parts.append(f.read_text())
            if parts:
                return PlainTextResponse("\n\n---\n\n".join(parts), media_type="text/markdown")

        return PlainTextResponse("No compliance report generated.", media_type="text/plain")
