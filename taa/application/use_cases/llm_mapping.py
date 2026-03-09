"""Use case: AI-powered schema mapping via Claude API."""

from __future__ import annotations

from taa.domain.entities.table import Table
from taa.domain.ports.repositories import DomainModelRepositoryPort
from taa.domain.value_objects.enums import TelcoDomain
from taa.infrastructure.llm.claude_mapper import (
    AIMappingResult,
    ClaudeSchemaMapper,
)
from taa.infrastructure.schema_import.parser import ImportedTable, SchemaParser


class LLMMappingUseCase:
    """Orchestrates AI-powered schema mapping.

    1. Parses the uploaded BSS schema content.
    2. Loads the full canonical TAA data model from the domain repository.
    3. Calls the Claude mapper to generate mapping suggestions.
    4. Returns the structured result.
    """

    def __init__(
        self,
        domain_repo: DomainModelRepositoryPort,
        mapper: ClaudeSchemaMapper | None = None,
    ) -> None:
        self._domain_repo = domain_repo
        self._mapper = mapper or ClaudeSchemaMapper()

    def execute(
        self,
        schema_content: str,
        fmt: str = "auto",
    ) -> AIMappingResult:
        """Run the AI mapping pipeline.

        Parameters
        ----------
        schema_content:
            Raw DDL or CSV text representing the vendor BSS schema.
        fmt:
            Format hint (``"auto"``, ``"ddl"``, or ``"csv"``).

        Returns
        -------
        AIMappingResult
            Contains the AI suggestions, model info, and availability status.
        """
        # 1. Parse uploaded schema
        parser = SchemaParser()
        imported_tables: tuple[ImportedTable, ...] = parser.parse(schema_content, fmt=fmt)

        # 2. Load all canonical tables across domains
        canonical: list[Table] = []
        for domain in TelcoDomain:
            canonical.extend(self._domain_repo.load_tables(domain))

        # 3. Call AI mapper
        return self._mapper.suggest_mappings(imported_tables, tuple(canonical))
