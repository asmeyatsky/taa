"""BSS vendor and schema endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from taa.infrastructure.config.container import Container
from taa.presentation.api.dependencies import get_container
from taa.presentation.api.schemas import (
    SchemaUploadRequest,
    SchemaUploadResponse,
    MappingSuggestionItem,
)

router = APIRouter()


@router.get("/vendors")
def list_vendors(container: Container = Depends(get_container)) -> list[dict]:
    """List supported BSS platforms."""
    vendors = container.list_vendors.execute()
    return [v.model_dump() for v in vendors]


@router.post("/schema", response_model=SchemaUploadResponse)
def upload_schema(
    req: SchemaUploadRequest,
    container: Container = Depends(get_container),
) -> SchemaUploadResponse:
    """Upload BSS table sample; returns auto-detected vendor and mapping suggestions."""
    from taa.infrastructure.schema_import import (
        SchemaParser,
        VendorDetector,
        MappingSuggester,
        GapAnalyzer,
    )
    from taa.domain.value_objects.enums import TelcoDomain

    parser = SchemaParser()
    imported = parser.parse(req.content, fmt=req.format)

    detector = VendorDetector()
    detection = detector.detect(imported)

    canonical: list = []
    for domain in TelcoDomain:
        canonical.extend(container.domain_repo.load_tables(domain))

    suggester = MappingSuggester()
    suggestions = suggester.suggest(imported, tuple(canonical), detection.vendor)

    analyzer = GapAnalyzer()
    report = analyzer.analyze(
        imported, tuple(canonical), suggestions,
        vendor=detection.vendor, vendor_confidence=detection.confidence,
    )

    return SchemaUploadResponse(
        tables_found=len(imported),
        columns_found=sum(len(t.columns) for t in imported),
        detected_vendor=detection.vendor.value if detection.vendor else None,
        vendor_confidence=detection.confidence,
        suggestions=[
            MappingSuggestionItem(
                vendor_table=s.vendor_table,
                vendor_field=s.vendor_field,
                canonical_table=s.canonical_table,
                canonical_field=s.canonical_field,
                confidence=s.confidence,
                match_reason=s.match_reason,
            )
            for s in sorted(suggestions, key=lambda x: -x.confidence)[:50]
        ],
        mapping_coverage_pct=report.mapping_coverage_pct,
        import_coverage_pct=report.import_coverage_pct,
    )
