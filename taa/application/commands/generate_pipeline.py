"""Generate Pipeline command."""

from __future__ import annotations

from taa.application.dtos.models import GenerationRequest, GenerationResult
from taa.domain.entities.pipeline import Pipeline
from taa.domain.ports.generators import PipelineGeneratorPort
from taa.domain.ports.infrastructure import OutputWriterPort
from taa.domain.value_objects.enums import TelcoDomain, PipelineType, PipelineMode, BSSVendor

DOMAIN_PIPELINES: dict[TelcoDomain, list[dict]] = {
    TelcoDomain.CDR_EVENT: [
        {"name": "cdr_mediation", "type": PipelineType.CDR_MEDIATION, "mode": PipelineMode.STREAMING},
        {"name": "cdr_batch_ingestion", "type": PipelineType.BATCH_INGESTION, "mode": PipelineMode.BATCH},
    ],
    TelcoDomain.SUBSCRIBER: [
        {"name": "subscriber_ingestion", "type": PipelineType.BATCH_INGESTION, "mode": PipelineMode.BATCH},
        {"name": "subscriber_cdc", "type": PipelineType.CDC, "mode": PipelineMode.STREAMING},
    ],
    TelcoDomain.REVENUE_INVOICE: [
        {"name": "billing_ingestion", "type": PipelineType.BATCH_INGESTION, "mode": PipelineMode.BATCH},
        {"name": "revenue_assurance", "type": PipelineType.REVENUE_ASSURANCE, "mode": PipelineMode.BATCH},
    ],
    TelcoDomain.INTERCONNECT_ROAMING: [
        {"name": "tap_rap_processing", "type": PipelineType.TAP_RAP, "mode": PipelineMode.BATCH},
    ],
    TelcoDomain.PRODUCT_CATALOGUE: [
        {"name": "product_sync", "type": PipelineType.CDC, "mode": PipelineMode.BATCH},
    ],
    TelcoDomain.NETWORK_INVENTORY: [
        {"name": "network_inventory_ingestion", "type": PipelineType.BATCH_INGESTION, "mode": PipelineMode.BATCH},
    ],
    TelcoDomain.USAGE_ANALYTICS: [
        {"name": "usage_aggregation", "type": PipelineType.BATCH_INGESTION, "mode": PipelineMode.BATCH},
    ],
}


class GeneratePipelineCommand:
    """Build Pipeline entities per domain, generate code, write output."""

    def __init__(
        self,
        pipeline_generator: PipelineGeneratorPort,
        output_writer: OutputWriterPort,
    ) -> None:
        self._pipeline_generator = pipeline_generator
        self._output_writer = output_writer

    def execute(self, request: GenerationRequest) -> GenerationResult:
        files_generated: list[str] = []
        errors: list[str] = []
        vendor = BSSVendor(request.vendor) if request.vendor else None

        for domain_name in request.domains:
            try:
                domain = TelcoDomain(domain_name)
                pipeline_defs = DOMAIN_PIPELINES.get(domain, [])

                for pdef in pipeline_defs:
                    pipeline = Pipeline(
                        name=pdef["name"],
                        pipeline_type=pdef["type"],
                        source_vendor=vendor,
                        mode=pdef["mode"],
                        telco_domain=domain,
                    )
                    code = self._pipeline_generator.generate(pipeline)
                    output_path = request.output_dir / "dataflow" / f"{pipeline.name}.py"
                    self._output_writer.write(output_path, code)
                    files_generated.append(str(output_path))
            except Exception as e:
                errors.append(f"Error generating pipeline for {domain_name}: {e}")

        return GenerationResult(
            success=len(errors) == 0,
            files_generated=files_generated,
            errors=errors,
            summary=f"Generated {len(files_generated)} pipeline(s)",
        )
