"""Tests for orchestration workflow."""

from taa.application.orchestration.workflow import DAGOrchestrator, WorkflowStep, FullGenerationWorkflow
import pytest


class TestDAGOrchestrator:
    def test_simple_linear(self):
        o = DAGOrchestrator()
        o.add_step(WorkflowStep(name="a"))
        o.add_step(WorkflowStep(name="b", dependencies=("a",)))
        o.add_step(WorkflowStep(name="c", dependencies=("b",)))
        levels = o.get_execution_order()
        assert levels == [["a"], ["b"], ["c"]]

    def test_parallel_steps(self):
        o = DAGOrchestrator()
        o.add_step(WorkflowStep(name="a"))
        o.add_step(WorkflowStep(name="b"))
        o.add_step(WorkflowStep(name="c", dependencies=("a", "b")))
        levels = o.get_execution_order()
        assert levels[0] == ["a", "b"]
        assert levels[1] == ["c"]

    def test_circular_dependency(self):
        o = DAGOrchestrator()
        o.add_step(WorkflowStep(name="a", dependencies=("b",)))
        o.add_step(WorkflowStep(name="b", dependencies=("a",)))
        with pytest.raises(ValueError, match="Circular dependency"):
            o.get_execution_order()


class TestFullGenerationWorkflow:
    def test_build_orchestrator(self):
        wf = FullGenerationWorkflow()
        o = wf.build_orchestrator()
        levels = o.get_execution_order()
        # schema_assembly must be first
        assert "schema_assembly" in levels[0]
        # dag_generation must be last
        assert "dag_generation" in levels[-1]
