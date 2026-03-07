"""Tests for application DTOs."""

from pathlib import Path

from taa.application.dtos.models import (
    GenerationRequest, GenerationResult, DomainInfo,
    VendorInfo, JurisdictionInfo, MappingResult,
)


class TestGenerationRequest:
    def test_defaults(self):
        r = GenerationRequest()
        assert r.jurisdiction == "SA"
        assert r.output_dir == Path("./output")

    def test_custom(self):
        r = GenerationRequest(domains=["subscriber"], jurisdiction="AE")
        assert r.domains == ["subscriber"]
        assert r.jurisdiction == "AE"


class TestGenerationResult:
    def test_success(self):
        r = GenerationResult(success=True, files_generated=["a.sql", "b.sql"])
        assert r.file_count == 2

    def test_failure(self):
        r = GenerationResult(success=False, errors=["something failed"])
        assert not r.success
        assert len(r.errors) == 1


class TestMappingResult:
    def test_basic(self):
        r = MappingResult(vendor="amdocs", domain="subscriber",
                          total_fields=10, mapped_fields=8, coverage_pct=80.0)
        assert r.coverage_pct == 80.0
