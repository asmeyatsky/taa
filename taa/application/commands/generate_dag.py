"""Generate DAG command."""

from __future__ import annotations

from taa.application.dtos.models import GenerationRequest, GenerationResult
from taa.domain.entities.dag import DAG, DAGTask
from taa.domain.ports.generators import DAGGeneratorPort
from taa.domain.ports.infrastructure import OutputWriterPort
from taa.domain.value_objects.enums import TelcoDomain

DOMAIN_DAGS: dict[TelcoDomain, list[dict]] = {
    TelcoDomain.CDR_EVENT: [
        {
            "dag_id": "daily_cdr_processing",
            "schedule": "0 2 * * *",
            "tasks": [
                DAGTask(task_id="extract_cdr", operator="GCSToGCSOperator"),
                DAGTask(task_id="mediate_cdr", operator="DataflowOperator", upstream_tasks=("extract_cdr",)),
                DAGTask(task_id="load_bigquery", operator="GCSToBigQueryOperator", upstream_tasks=("mediate_cdr",)),
                DAGTask(task_id="quality_check", operator="BigQueryCheckOperator", upstream_tasks=("load_bigquery",)),
            ],
            "sla_seconds": 7200,
        },
    ],
    TelcoDomain.REVENUE_INVOICE: [
        {
            "dag_id": "monthly_billing_recon",
            "schedule": "0 6 1 * *",
            "tasks": [
                DAGTask(task_id="extract_invoices", operator="GCSToGCSOperator"),
                DAGTask(task_id="reconcile", operator="DataflowOperator", upstream_tasks=("extract_invoices",)),
                DAGTask(task_id="generate_report", operator="BigQueryOperator", upstream_tasks=("reconcile",)),
            ],
            "sla_seconds": 14400,
        },
    ],
    TelcoDomain.SUBSCRIBER: [
        {
            "dag_id": "weekly_churn_features",
            "schedule": "0 4 * * 1",
            "tasks": [
                DAGTask(task_id="extract_features", operator="BigQueryOperator"),
                DAGTask(task_id="compute_churn_score", operator="DataflowOperator", upstream_tasks=("extract_features",)),
                DAGTask(task_id="update_profiles", operator="BigQueryOperator", upstream_tasks=("compute_churn_score",)),
            ],
            "sla_seconds": 10800,
        },
    ],
    TelcoDomain.INTERCONNECT_ROAMING: [
        {
            "dag_id": "interconnect_settlement",
            "schedule": "0 3 * * *",
            "tasks": [
                DAGTask(task_id="ingest_tap", operator="GCSToGCSOperator"),
                DAGTask(task_id="process_rap", operator="DataflowOperator", upstream_tasks=("ingest_tap",)),
                DAGTask(task_id="settlement_calc", operator="BigQueryOperator", upstream_tasks=("process_rap",)),
            ],
            "sla_seconds": 7200,
        },
    ],
}


class GenerateDAGCommand:
    """Build DAG entities from templates, generate code, write output."""

    def __init__(
        self,
        dag_generator: DAGGeneratorPort,
        output_writer: OutputWriterPort,
    ) -> None:
        self._dag_generator = dag_generator
        self._output_writer = output_writer

    def execute(self, request: GenerationRequest) -> GenerationResult:
        files_generated: list[str] = []
        errors: list[str] = []

        for domain_name in request.domains:
            try:
                domain = TelcoDomain(domain_name)
                dag_defs = DOMAIN_DAGS.get(domain, [])

                for ddef in dag_defs:
                    dag = DAG(
                        dag_id=ddef["dag_id"],
                        schedule=ddef["schedule"],
                        tasks=tuple(ddef["tasks"]),
                        sla_seconds=ddef.get("sla_seconds", 3600),
                    )
                    code = self._dag_generator.generate(dag)
                    output_path = request.output_dir / "airflow" / f"{dag.dag_id}.py"
                    self._output_writer.write(output_path, code)
                    files_generated.append(str(output_path))
            except Exception as e:
                errors.append(f"Error generating DAG for {domain_name}: {e}")

        return GenerationResult(
            success=len(errors) == 0,
            files_generated=files_generated,
            errors=errors,
            summary=f"Generated {len(files_generated)} DAG(s)",
        )
