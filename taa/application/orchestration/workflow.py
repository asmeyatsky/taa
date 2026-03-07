"""Generation workflow orchestration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowStep:
    """A step in the generation workflow DAG."""

    name: str
    dependencies: tuple[str, ...] = ()


class DAGOrchestrator:
    """DAG-based orchestration for parallel workflow execution."""

    def __init__(self) -> None:
        self._steps: dict[str, WorkflowStep] = {}

    def add_step(self, step: WorkflowStep) -> None:
        self._steps[step.name] = step

    def get_execution_order(self) -> list[list[str]]:
        """Return steps grouped by execution level (parallelizable within each level)."""
        remaining = dict(self._steps)
        completed: set[str] = set()
        levels: list[list[str]] = []

        while remaining:
            ready = [
                name for name, step in remaining.items()
                if all(dep in completed for dep in step.dependencies)
            ]
            if not ready:
                raise ValueError("Circular dependency detected in workflow DAG")
            levels.append(sorted(ready))
            for name in ready:
                completed.add(name)
                del remaining[name]

        return levels


class FullGenerationWorkflow:
    """TAA-specific workflow DAG for full pack generation."""

    def build_orchestrator(self) -> DAGOrchestrator:
        orchestrator = DAGOrchestrator()
        orchestrator.add_step(WorkflowStep(name="schema_assembly"))
        orchestrator.add_step(WorkflowStep(name="pii_detection", dependencies=("schema_assembly",)))
        orchestrator.add_step(WorkflowStep(name="compliance_scan", dependencies=("schema_assembly",)))
        orchestrator.add_step(WorkflowStep(name="ddl_generation", dependencies=("schema_assembly", "pii_detection")))
        orchestrator.add_step(WorkflowStep(name="terraform_generation", dependencies=("ddl_generation",)))
        orchestrator.add_step(WorkflowStep(name="pipeline_generation", dependencies=("ddl_generation",)))
        orchestrator.add_step(WorkflowStep(name="dag_generation", dependencies=("pipeline_generation",)))
        return orchestrator
