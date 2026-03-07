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
                DAGTask(
                    task_id="extract_cdr",
                    operator="GCSToGCSOperator",
                    params={
                        "source_bucket": '"telco-raw-cdr-landing"',
                        "source_object": '"voice_cdr/{{ ds_nodash }}/*.csv"',
                        "destination_bucket": '"telco-cdr-staging"',
                        "destination_object": '"voice_cdr/{{ ds_nodash }}/"',
                    },
                ),
                DAGTask(
                    task_id="mediate_cdr",
                    operator="DataflowStartFlexTemplateOperator",
                    upstream_tasks=("extract_cdr",),
                    params={
                        "task_id": '"mediate_cdr"',
                        "container_spec_gcs_path": '"gs://telco-dataflow-templates/cdr-mediation/latest/flex-template.json"',
                        "parameters": (
                            '{"input_path": "gs://telco-cdr-staging/voice_cdr/{{ ds_nodash }}/", '
                            '"output_table": "telco_project.cdr_event_ds.voice_cdr", '
                            '"error_table": "telco_project.cdr_event_ds.voice_cdr_errors", '
                            '"dedup_window_minutes": "60"}'
                        ),
                    },
                ),
                DAGTask(
                    task_id="load_bigquery",
                    operator="GCSToBigQueryOperator",
                    upstream_tasks=("mediate_cdr",),
                    params={
                        "source_objects": '["voice_cdr/{{ ds_nodash }}/mediated_*.avro"]',
                        "source_format": '"AVRO"',
                        "destination_project_dataset_table": '"telco_project.cdr_event_ds.voice_cdr"',
                        "write_disposition": '"WRITE_APPEND"',
                        "time_partitioning": '{"type": "DAY", "field": "event_timestamp"}',
                        "cluster_fields": '["subscriber_id", "call_type"]',
                    },
                ),
                DAGTask(
                    task_id="quality_check",
                    operator="BigQueryCheckOperator",
                    upstream_tasks=("load_bigquery",),
                    params={
                        "sql": (
                            '"""'
                            "SELECT "
                            "COUNT(*) AS total_records, "
                            "COUNTIF(subscriber_id IS NULL) AS null_subscriber, "
                            "COUNTIF(event_timestamp IS NULL) AS null_timestamp, "
                            "COUNTIF(duration_seconds < 0) AS negative_duration "
                            "FROM `telco_project.cdr_event_ds.voice_cdr` "
                            "WHERE DATE(event_timestamp) = '{{ ds }}' "
                            "HAVING null_subscriber = 0 AND null_timestamp = 0 AND negative_duration = 0"
                            '"""'
                        ),
                    },
                ),
            ],
            "sla_seconds": 7200,
        },
    ],
    TelcoDomain.REVENUE_INVOICE: [
        {
            "dag_id": "monthly_billing_recon",
            "schedule": "0 6 1 * *",
            "tasks": [
                DAGTask(
                    task_id="extract_invoices",
                    operator="GCSToGCSOperator",
                    params={
                        "source_bucket": '"telco-billing-exports"',
                        "source_object": '"invoices/{{ macros.ds_format(ds, \'%Y-%m-%d\', \'%Y%m\') }}/*.json"',
                        "destination_bucket": '"telco-billing-staging"',
                        "destination_object": '"invoices/{{ macros.ds_format(ds, \'%Y-%m-%d\', \'%Y%m\') }}/"',
                    },
                ),
                DAGTask(
                    task_id="reconcile",
                    operator="BigQueryInsertJobOperator",
                    upstream_tasks=("extract_invoices",),
                    params={
                        "configuration": (
                            '{"query": {"query": """'
                            "CREATE OR REPLACE TABLE `telco_project.revenue_invoice_ds.billing_reconciliation` AS "
                            "WITH invoice_totals AS ( "
                            "SELECT account_id, bill_cycle_date, "
                            "SUM(amount_due) AS invoiced_amount, "
                            "COUNT(DISTINCT invoice_id) AS invoice_count "
                            "FROM `telco_project.revenue_invoice_ds.invoice` "
                            "WHERE bill_cycle_date >= DATE_TRUNC(DATE_SUB('{{ ds }}', INTERVAL 1 MONTH), MONTH) "
                            "AND bill_cycle_date < DATE_TRUNC('{{ ds }}', MONTH) "
                            "GROUP BY account_id, bill_cycle_date), "
                            "payment_totals AS ( "
                            "SELECT i.account_id, SUM(p.payment_amount) AS paid_amount "
                            "FROM `telco_project.revenue_invoice_ds.payment` p "
                            "JOIN `telco_project.revenue_invoice_ds.invoice` i ON p.invoice_id = i.invoice_id "
                            "WHERE i.bill_cycle_date >= DATE_TRUNC(DATE_SUB('{{ ds }}', INTERVAL 1 MONTH), MONTH) "
                            "GROUP BY i.account_id) "
                            "SELECT inv.account_id, inv.invoiced_amount, "
                            "COALESCE(pay.paid_amount, 0) AS paid_amount, "
                            "inv.invoiced_amount - COALESCE(pay.paid_amount, 0) AS outstanding_balance "
                            "FROM invoice_totals inv "
                            "LEFT JOIN payment_totals pay ON inv.account_id = pay.account_id"
                            '""", "useLegacySql": false}}'
                        ),
                    },
                ),
                DAGTask(
                    task_id="generate_report",
                    operator="BigQueryInsertJobOperator",
                    upstream_tasks=("reconcile",),
                    params={
                        "configuration": (
                            '{"query": {"query": """'
                            "SELECT "
                            "COUNT(*) AS total_accounts, "
                            "SUM(invoiced_amount) AS total_invoiced, "
                            "SUM(paid_amount) AS total_paid, "
                            "SUM(outstanding_balance) AS total_outstanding, "
                            "COUNTIF(outstanding_balance > 0) AS accounts_with_balance "
                            "FROM `telco_project.revenue_invoice_ds.billing_reconciliation`"
                            '""", "useLegacySql": false}}'
                        ),
                    },
                ),
            ],
            "sla_seconds": 14400,
        },
    ],
    TelcoDomain.SUBSCRIBER: [
        {
            "dag_id": "weekly_churn_features",
            "schedule": "0 4 * * 1",
            "tasks": [
                DAGTask(
                    task_id="extract_features",
                    operator="BigQueryInsertJobOperator",
                    params={
                        "configuration": (
                            '{"query": {"query": """'
                            "CREATE OR REPLACE TABLE `telco_project.subscriber_ds.churn_features` AS "
                            "SELECT sp.subscriber_id, sp.activation_date, sp.status, "
                            "DATE_DIFF(CURRENT_DATE(), sp.activation_date, DAY) AS tenure_days, "
                            "COALESCE(voice.call_count_30d, 0) AS call_count_30d, "
                            "COALESCE(voice.total_duration_30d, 0) AS total_duration_30d, "
                            "COALESCE(data_usage.total_bytes_30d, 0) AS data_bytes_30d, "
                            "COALESCE(inv.avg_monthly_charge, 0) AS avg_monthly_charge, "
                            "COALESCE(inv.late_payment_count, 0) AS late_payment_count "
                            "FROM `telco_project.subscriber_ds.subscriber_profile` sp "
                            "LEFT JOIN (SELECT subscriber_id, "
                            "COUNT(*) AS call_count_30d, "
                            "SUM(duration_seconds) AS total_duration_30d "
                            "FROM `telco_project.cdr_event_ds.voice_cdr` "
                            "WHERE event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY) "
                            "GROUP BY subscriber_id) voice ON sp.subscriber_id = voice.subscriber_id "
                            "LEFT JOIN (SELECT subscriber_id, "
                            "SUM(bytes_transferred) AS total_bytes_30d "
                            "FROM `telco_project.cdr_event_ds.data_cdr` "
                            "WHERE event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY) "
                            "GROUP BY subscriber_id) data_usage ON sp.subscriber_id = data_usage.subscriber_id "
                            "LEFT JOIN (SELECT subscriber_id, "
                            "AVG(amount_due) AS avg_monthly_charge, "
                            "COUNTIF(payment_status = 'LATE') AS late_payment_count "
                            "FROM `telco_project.revenue_invoice_ds.invoice` "
                            "WHERE bill_cycle_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 6 MONTH) "
                            "GROUP BY subscriber_id) inv ON sp.subscriber_id = inv.subscriber_id "
                            "WHERE sp.status IN ('ACTIVE', 'SUSPENDED')"
                            '""", "useLegacySql": false}}'
                        ),
                    },
                ),
                DAGTask(
                    task_id="compute_churn_score",
                    operator="DataflowStartFlexTemplateOperator",
                    upstream_tasks=("extract_features",),
                    params={
                        "container_spec_gcs_path": '"gs://telco-dataflow-templates/churn-scoring/latest/flex-template.json"',
                        "parameters": (
                            '{"input_table": "telco_project.subscriber_ds.churn_features", '
                            '"output_table": "telco_project.subscriber_ds.churn_scores", '
                            '"model_path": "gs://telco-ml-models/churn/latest/model", '
                            '"score_threshold": "0.7"}'
                        ),
                    },
                ),
                DAGTask(
                    task_id="update_profiles",
                    operator="BigQueryInsertJobOperator",
                    upstream_tasks=("compute_churn_score",),
                    params={
                        "configuration": (
                            '{"query": {"query": """'
                            "MERGE `telco_project.subscriber_ds.subscriber_profile` AS target "
                            "USING `telco_project.subscriber_ds.churn_scores` AS source "
                            "ON target.subscriber_id = source.subscriber_id "
                            "WHEN MATCHED THEN UPDATE SET "
                            "target.churn_risk_score = source.churn_score, "
                            "target.churn_risk_segment = source.risk_segment, "
                            "target.last_scored_date = CURRENT_DATE()"
                            '""", "useLegacySql": false}}'
                        ),
                    },
                ),
            ],
            "sla_seconds": 10800,
        },
    ],
    TelcoDomain.INTERCONNECT_ROAMING: [
        {
            "dag_id": "interconnect_settlement",
            "schedule": "0 3 * * *",
            "tasks": [
                DAGTask(
                    task_id="ingest_tap",
                    operator="GCSToGCSOperator",
                    params={
                        "source_bucket": '"telco-interconnect-incoming"',
                        "source_object": '"tap_files/{{ ds_nodash }}/TAP3*.asn1"',
                        "destination_bucket": '"telco-interconnect-staging"',
                        "destination_object": '"tap_files/{{ ds_nodash }}/"',
                    },
                ),
                DAGTask(
                    task_id="process_rap",
                    operator="DataflowStartFlexTemplateOperator",
                    upstream_tasks=("ingest_tap",),
                    params={
                        "container_spec_gcs_path": '"gs://telco-dataflow-templates/rap-processing/latest/flex-template.json"',
                        "parameters": (
                            '{"input_path": "gs://telco-interconnect-staging/tap_files/{{ ds_nodash }}/", '
                            '"output_table": "telco_project.interconnect_roaming_ds.interconnect_cdr", '
                            '"rap_output_path": "gs://telco-interconnect-outgoing/rap_files/{{ ds_nodash }}/", '
                            '"partner_config": "gs://telco-config/interconnect/partner_rates.json"}'
                        ),
                    },
                ),
                DAGTask(
                    task_id="settlement_calc",
                    operator="BigQueryInsertJobOperator",
                    upstream_tasks=("process_rap",),
                    params={
                        "configuration": (
                            '{"query": {"query": """'
                            "CREATE OR REPLACE TABLE "
                            "`telco_project.interconnect_roaming_ds.daily_settlement` AS "
                            "SELECT partner_operator, direction, "
                            "COUNT(*) AS record_count, "
                            "SUM(rated_amount_sdr) AS total_sdr, "
                            "SUM(rated_amount_local) AS total_local_currency, "
                            "SUM(CASE WHEN call_type = 'VOICE' THEN duration_seconds ELSE 0 END) AS total_voice_seconds, "
                            "SUM(CASE WHEN call_type = 'DATA' THEN volume_bytes ELSE 0 END) AS total_data_bytes, "
                            "SUM(CASE WHEN call_type = 'SMS' THEN 1 ELSE 0 END) AS total_sms_count "
                            "FROM `telco_project.interconnect_roaming_ds.interconnect_cdr` "
                            "WHERE DATE(event_timestamp) = '{{ ds }}' "
                            "GROUP BY partner_operator, direction"
                            '""", "useLegacySql": false}}'
                        ),
                    },
                ),
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
