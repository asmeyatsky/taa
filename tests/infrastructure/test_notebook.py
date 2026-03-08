"""Tests for Vertex AI notebook generator."""

from __future__ import annotations

import json

import pytest

from taa.infrastructure.generators.notebook import NotebookGenerator


@pytest.fixture()
def generator() -> NotebookGenerator:
    return NotebookGenerator(project_id="test-project")


class TestNotebookGenerator:
    def test_list_templates(self, generator):
        templates = generator.list_templates()
        assert "churn_prediction" in templates
        assert "revenue_leakage" in templates
        assert "subscriber_ltv" in templates
        assert len(templates) == 3

    def test_generate_churn_prediction(self, generator):
        content = generator.generate("churn_prediction")
        nb = json.loads(content)
        assert nb["nbformat"] == 4
        assert len(nb["cells"]) > 0
        assert nb["metadata"]["kernelspec"]["language"] == "python"

    def test_generate_revenue_leakage(self, generator):
        content = generator.generate("revenue_leakage")
        nb = json.loads(content)
        assert nb["nbformat"] == 4
        assert any("Revenue Leakage" in "".join(c["source"]) for c in nb["cells"])

    def test_generate_subscriber_ltv(self, generator):
        content = generator.generate("subscriber_ltv")
        nb = json.loads(content)
        assert nb["nbformat"] == 4
        assert any("Lifetime Value" in "".join(c["source"]) for c in nb["cells"])

    def test_unknown_template_raises(self, generator):
        with pytest.raises(ValueError, match="Unknown notebook template"):
            generator.generate("nonexistent")

    def test_project_id_in_output(self, generator):
        content = generator.generate("churn_prediction")
        assert "test-project" in content

    def test_custom_dataset(self, generator):
        content = generator.generate("churn_prediction", dataset_name="my_dataset")
        assert "my_dataset" in content

    def test_generate_all(self, generator):
        all_nbs = generator.generate_all()
        assert len(all_nbs) == 3
        assert "churn_prediction.ipynb" in all_nbs
        assert "revenue_leakage.ipynb" in all_nbs
        assert "subscriber_ltv.ipynb" in all_nbs

    def test_all_notebooks_valid_json(self, generator):
        for name, content in generator.generate_all().items():
            nb = json.loads(content)
            assert nb["nbformat"] == 4, f"{name} has invalid nbformat"
            assert len(nb["cells"]) > 0, f"{name} has no cells"

    def test_cells_have_correct_types(self, generator):
        content = generator.generate("churn_prediction")
        nb = json.loads(content)
        for cell in nb["cells"]:
            assert cell["cell_type"] in ("code", "markdown")
            assert "source" in cell

    def test_code_cells_have_outputs_field(self, generator):
        content = generator.generate("churn_prediction")
        nb = json.loads(content)
        for cell in nb["cells"]:
            if cell["cell_type"] == "code":
                assert "outputs" in cell
                assert "execution_count" in cell
