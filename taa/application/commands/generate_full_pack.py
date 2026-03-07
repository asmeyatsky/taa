"""Generate Full Pack command - orchestrates all generation commands."""

from __future__ import annotations

from taa.application.dtos.models import GenerationRequest, GenerationResult
from taa.application.commands.generate_ddl import GenerateDDLCommand
from taa.application.commands.generate_terraform import GenerateTerraformCommand
from taa.application.commands.generate_pipeline import GeneratePipelineCommand
from taa.application.commands.generate_dag import GenerateDAGCommand
from taa.application.commands.generate_compliance import GenerateComplianceReportCommand


class GenerateFullPackCommand:
    """Orchestrate all generation commands for a complete output pack."""

    def __init__(
        self,
        ddl_cmd: GenerateDDLCommand,
        terraform_cmd: GenerateTerraformCommand,
        pipeline_cmd: GeneratePipelineCommand,
        dag_cmd: GenerateDAGCommand,
        compliance_cmd: GenerateComplianceReportCommand,
    ) -> None:
        self._ddl_cmd = ddl_cmd
        self._terraform_cmd = terraform_cmd
        self._pipeline_cmd = pipeline_cmd
        self._dag_cmd = dag_cmd
        self._compliance_cmd = compliance_cmd

    def execute(self, request: GenerationRequest) -> GenerationResult:
        all_files: list[str] = []
        all_errors: list[str] = []
        all_warnings: list[str] = []

        # Execute each command
        commands = [
            ("DDL", self._ddl_cmd),
            ("Terraform", self._terraform_cmd),
            ("Pipeline", self._pipeline_cmd),
            ("DAG", self._dag_cmd),
            ("Compliance", self._compliance_cmd),
        ]

        for name, cmd in commands:
            if name == "Terraform" and not request.include_terraform:
                continue
            if name == "Pipeline" and not request.include_pipelines:
                continue
            if name == "DAG" and not request.include_dags:
                continue
            if name == "Compliance" and not request.include_compliance:
                continue

            result = cmd.execute(request)
            all_files.extend(result.files_generated)
            all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)

        return GenerationResult(
            success=len(all_errors) == 0,
            files_generated=all_files,
            errors=all_errors,
            warnings=all_warnings,
            summary=f"Full pack: generated {len(all_files)} file(s)",
        )
