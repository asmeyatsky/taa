"""Claude API-powered schema mapper using the Anthropic SDK with structured tool_use output."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from taa.domain.entities.table import Table
from taa.infrastructure.schema_import.parser import ImportedTable

logger = logging.getLogger(__name__)

# ---- Tool definition for structured output via tool_use ----

_MAPPING_TOOL = {
    "name": "submit_mapping_suggestions",
    "description": (
        "Submit the mapping suggestions between vendor BSS schema columns "
        "and the canonical TAA data model columns."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "mappings": {
                "type": "array",
                "description": "List of column-level mapping suggestions.",
                "items": {
                    "type": "object",
                    "properties": {
                        "vendor_table": {
                            "type": "string",
                            "description": "Source vendor table name.",
                        },
                        "vendor_field": {
                            "type": "string",
                            "description": "Source vendor column name.",
                        },
                        "canonical_table": {
                            "type": "string",
                            "description": "Target canonical table name.",
                        },
                        "canonical_field": {
                            "type": "string",
                            "description": "Target canonical column name.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score from 0.0 to 1.0.",
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Brief explanation of why this mapping was chosen.",
                        },
                        "transformation": {
                            "type": "string",
                            "description": (
                                "SQL expression to transform the source value, "
                                "or empty string if no transformation is needed."
                            ),
                        },
                    },
                    "required": [
                        "vendor_table",
                        "vendor_field",
                        "canonical_table",
                        "canonical_field",
                        "confidence",
                        "reasoning",
                    ],
                },
            },
        },
        "required": ["mappings"],
    },
}


@dataclass(frozen=True)
class AIMappingSuggestion:
    """A single AI-generated mapping suggestion with confidence and reasoning."""

    vendor_table: str
    vendor_field: str
    canonical_table: str
    canonical_field: str
    confidence: float
    reasoning: str
    transformation: str = ""


@dataclass(frozen=True)
class AIMappingResult:
    """Result of an AI-powered schema mapping request."""

    suggestions: tuple[AIMappingSuggestion, ...] = ()
    model_used: str = ""
    message: str = ""
    available: bool = True


class ClaudeSchemaMapper:
    """Uses the Anthropic Python SDK to suggest vendor-to-canonical schema mappings.

    Falls back gracefully when ANTHROPIC_API_KEY is not set, returning an empty
    result with an explanatory message instead of raising.
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 4096

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model or self.DEFAULT_MODEL

    # ---- public API ----

    def suggest_mappings(
        self,
        imported_tables: tuple[ImportedTable, ...],
        canonical_tables: tuple[Table, ...],
    ) -> AIMappingResult:
        """Suggest mappings using Claude.

        Returns an ``AIMappingResult`` that always succeeds. When the API key is
        missing or the call fails, the result contains an empty suggestion list
        together with an informational *message*.
        """
        resolved_key = self._api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not resolved_key:
            return AIMappingResult(
                suggestions=(),
                model_used="",
                message=(
                    "ANTHROPIC_API_KEY is not configured. "
                    "Set the environment variable to enable AI-powered mapping suggestions."
                ),
                available=False,
            )

        try:
            return self._call_claude(resolved_key, imported_tables, canonical_tables)
        except Exception:
            logger.exception("Claude API call failed")
            return AIMappingResult(
                suggestions=(),
                model_used=self._model,
                message="Claude API call failed. Falling back to rule-based suggestions only.",
                available=False,
            )

    # ---- internals ----

    def _build_system_prompt(self) -> str:
        return (
            "You are an expert telco BSS/OSS data engineer specialising in schema mapping. "
            "You will be given a SOURCE schema (from a vendor BSS system) and a TARGET schema "
            "(the canonical TAA data model). Your job is to suggest the best column-level "
            "mappings from source to target.\n\n"
            "Guidelines:\n"
            "- Match columns based on semantic meaning, not just name similarity.\n"
            "- Consider telco-specific domain knowledge (MSISDN, IMSI, CDR, etc.).\n"
            "- Provide a confidence score between 0.0 and 1.0 for each mapping.\n"
            "- If a source column has no reasonable target, omit it.\n"
            "- If a SQL transformation is needed (e.g. type cast, enum mapping), "
            "describe it in the transformation field.\n"
            "- Be concise in your reasoning."
        )

    def _build_user_prompt(
        self,
        imported_tables: tuple[ImportedTable, ...],
        canonical_tables: tuple[Table, ...],
    ) -> str:
        imported_desc: list[str] = []
        for table in imported_tables:
            cols = ", ".join(f"{c.name} ({c.data_type})" for c in table.columns)
            imported_desc.append(f"  {table.name}: [{cols}]")

        canonical_desc: list[str] = []
        for table in canonical_tables:
            cols = ", ".join(
                f"{c.name} ({c.bigquery_type.value})" for c in table.columns
            )
            canonical_desc.append(f"  {table.name}: [{cols}]")

        return (
            "Analyze the following schemas and submit your mapping suggestions "
            "using the submit_mapping_suggestions tool.\n\n"
            "SOURCE SCHEMA (vendor BSS system):\n"
            f"{chr(10).join(imported_desc)}\n\n"
            "TARGET SCHEMA (canonical TAA data model):\n"
            f"{chr(10).join(canonical_desc)}"
        )

    def _call_claude(
        self,
        api_key: str,
        imported_tables: tuple[ImportedTable, ...],
        canonical_tables: tuple[Table, ...],
    ) -> AIMappingResult:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model=self._model,
            max_tokens=self.MAX_TOKENS,
            system=self._build_system_prompt(),
            tools=[_MAPPING_TOOL],
            tool_choice={"type": "tool", "name": "submit_mapping_suggestions"},
            messages=[
                {
                    "role": "user",
                    "content": self._build_user_prompt(imported_tables, canonical_tables),
                },
            ],
        )

        return self._parse_tool_response(response)

    def _parse_tool_response(self, response: object) -> AIMappingResult:
        """Extract ``AIMappingSuggestion`` objects from the tool_use content block."""
        suggestions: list[AIMappingSuggestion] = []

        for block in response.content:  # type: ignore[attr-defined]
            if block.type != "tool_use":
                continue
            if block.name != "submit_mapping_suggestions":
                continue

            raw_input = block.input
            if isinstance(raw_input, str):
                raw_input = json.loads(raw_input)

            for m in raw_input.get("mappings", []):
                suggestions.append(
                    AIMappingSuggestion(
                        vendor_table=m["vendor_table"],
                        vendor_field=m["vendor_field"],
                        canonical_table=m["canonical_table"],
                        canonical_field=m["canonical_field"],
                        confidence=float(m.get("confidence", 0.8)),
                        reasoning=m.get("reasoning", "AI-suggested mapping"),
                        transformation=m.get("transformation", ""),
                    )
                )

        model_used = getattr(response, "model", self._model)  # type: ignore[attr-defined]
        return AIMappingResult(
            suggestions=tuple(suggestions),
            model_used=model_used,
            message="",
            available=True,
        )
