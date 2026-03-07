"""Terraform generator."""

from __future__ import annotations

from taa.domain.entities.dataset import Dataset
from taa.infrastructure.template_renderer.jinja_renderer import JinjaRenderer


class TerraformGenerator:
    """Generates Terraform configuration files from Dataset entities."""

    def __init__(
        self,
        renderer: JinjaRenderer | None = None,
        project_id: str = "telco-analytics",
    ) -> None:
        self._renderer = renderer or JinjaRenderer()
        self._project_id = project_id

    def generate(self, datasets: tuple[Dataset, ...]) -> dict[str, str]:
        files: dict[str, str] = {}
        region = datasets[0].gcp_region if datasets else "me-central1"
        has_residency = any(
            d.jurisdiction and d.jurisdiction.data_residency_required
            for d in datasets
        )

        # Calculate KMS rotation (30 days in seconds)
        kms_rotation_seconds = 30 * 24 * 60 * 60

        context = {
            "datasets": datasets,
            "project_id": self._project_id,
            "region": region,
            "has_residency_requirement": has_residency,
            "kms_rotation_seconds": kms_rotation_seconds,
        }

        files["main.tf"] = self._renderer.render("terraform/main.tf.j2", context)
        files["bigquery_dataset.tf"] = self._renderer.render("terraform/bigquery_dataset.tf.j2", context)
        files["kms.tf"] = self._renderer.render("terraform/kms.tf.j2", context)
        files["iam.tf"] = self._renderer.render("terraform/iam.tf.j2", context)
        files["variables.tf"] = self._renderer.render("terraform/variables.tf.j2", context)
        files["gcs.tf"] = self._renderer.render("terraform/gcs.tf.j2", context)
        files["vpc_sc.tf"] = self._renderer.render("terraform/vpc_sc.tf.j2", context)

        return files
