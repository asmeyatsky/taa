"""Infrastructure generators."""

from taa.infrastructure.generators.bigquery_ddl import BigQueryDDLGenerator
from taa.infrastructure.generators.terraform import TerraformGenerator
from taa.infrastructure.generators.dataflow import DataflowPipelineGenerator
from taa.infrastructure.generators.airflow_dag import AirflowDAGGenerator
from taa.infrastructure.generators.compliance_report import ComplianceReportGenerator
from taa.infrastructure.generators.analytics import AnalyticsTemplateGenerator
from taa.infrastructure.generators.multicloud_ddl import (
    AWSRedshiftDDLGenerator,
    AWSCloudFormationGenerator,
    AzureSynapseDDLGenerator,
    AzureBicepGenerator,
)

__all__ = [
    "BigQueryDDLGenerator",
    "TerraformGenerator",
    "DataflowPipelineGenerator",
    "AirflowDAGGenerator",
    "ComplianceReportGenerator",
    "AnalyticsTemplateGenerator",
    "AWSRedshiftDDLGenerator",
    "AWSCloudFormationGenerator",
    "AzureSynapseDDLGenerator",
    "AzureBicepGenerator",
]
