"""Tests for CLI commands using Click test runner."""

from click.testing import CliRunner
from taa.presentation.cli.app import cli


class TestCLI:
    def setup_method(self):
        self.runner = CliRunner()

    def test_version(self):
        result = self.runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_domain_list(self):
        result = self.runner.invoke(cli, ["domain", "list"])
        assert result.exit_code == 0
        assert "subscriber" in result.output

    def test_domain_show(self):
        result = self.runner.invoke(cli, ["domain", "show", "subscriber"])
        assert result.exit_code == 0
        assert "subscriber_profile" in result.output

    def test_vendor_list(self):
        result = self.runner.invoke(cli, ["vendor", "list"])
        assert result.exit_code == 0
        assert "amdocs" in result.output

    def test_vendor_map(self):
        result = self.runner.invoke(cli, ["vendor", "map", "amdocs", "subscriber"])
        assert result.exit_code == 0
        assert "Coverage" in result.output

    def test_jurisdiction_list(self):
        result = self.runner.invoke(cli, ["jurisdiction", "list"])
        assert result.exit_code == 0
        assert "SA" in result.output
        assert "Saudi Arabia" in result.output

    def test_generate_ddl(self):
        result = self.runner.invoke(cli, ["generate", "ddl", "-d", "subscriber", "-j", "SA", "-o", "/tmp/taa_test_cli"])
        assert result.exit_code == 0
        assert "Success" in result.output

    def test_generate_terraform(self):
        result = self.runner.invoke(cli, ["generate", "terraform", "-d", "subscriber", "-j", "SA", "-o", "/tmp/taa_test_cli"])
        assert result.exit_code == 0
        assert "Success" in result.output

    def test_generate_pipeline(self):
        result = self.runner.invoke(cli, ["generate", "pipeline", "-d", "cdr_event", "-o", "/tmp/taa_test_cli"])
        assert result.exit_code == 0
        assert "Success" in result.output

    def test_generate_dag(self):
        result = self.runner.invoke(cli, ["generate", "dag", "-d", "cdr_event", "-o", "/tmp/taa_test_cli"])
        assert result.exit_code == 0
        assert "Success" in result.output

    def test_generate_compliance(self):
        result = self.runner.invoke(cli, ["generate", "compliance", "-d", "subscriber", "-j", "SA", "-o", "/tmp/taa_test_cli"])
        assert result.exit_code == 0
        assert "Success" in result.output

    def test_generate_pack(self):
        result = self.runner.invoke(cli, ["generate", "pack", "-d", "subscriber", "-j", "SA", "-o", "/tmp/taa_test_cli"])
        assert result.exit_code == 0
        assert "Success" in result.output

    def test_generate_pack_with_vendor(self):
        result = self.runner.invoke(cli, ["generate", "pack", "-d", "subscriber,cdr_event", "-j", "SA", "-v", "amdocs", "-o", "/tmp/taa_test_cli"])
        assert result.exit_code == 0
        assert "Success" in result.output

    def test_generate_pipeline_with_vendor(self):
        result = self.runner.invoke(cli, ["generate", "pipeline", "-d", "subscriber", "-v", "amdocs", "-o", "/tmp/taa_test_cli"])
        assert result.exit_code == 0
        assert "Success" in result.output
