"""DAG and DAGTask entities."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DAGTask:
    """A task within an Airflow DAG."""

    task_id: str
    operator: str
    upstream_tasks: tuple[str, ...] = ()
    params: dict[str, str] | None = None


@dataclass(frozen=True)
class DAG:
    """An Airflow DAG definition."""

    dag_id: str
    schedule: str
    tasks: tuple[DAGTask, ...] = ()
    sla_seconds: int = 3600
    retries: int = 2
    description: str = ""

    def task_ids(self) -> tuple[str, ...]:
        return tuple(t.task_id for t in self.tasks)

    def get_task(self, task_id: str) -> DAGTask | None:
        for t in self.tasks:
            if t.task_id == task_id:
                return t
        return None
