"""LLM-powered schema mapping — uses Claude/Gemini to suggest vendor-to-canonical mappings."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from taa.domain.entities.table import Table
from taa.infrastructure.schema_import.parser import ImportedTable
from taa.infrastructure.schema_import.mapping_suggester import SuggestedMapping


@dataclass(frozen=True)
class LLMMapperConfig:
    """Configuration for LLM-powered mapping."""

    provider: str = "anthropic"  # "anthropic" or "google"
    model: str = "claude-sonnet-4-20250514"
    api_key: str = ""
    max_tokens: int = 4096


class LLMSchemaMapper:
    """Uses LLM to suggest vendor-to-canonical schema mappings."""

    def __init__(self, config: LLMMapperConfig | None = None) -> None:
        self._config = config or LLMMapperConfig()

    def suggest_mappings(
        self,
        imported_tables: tuple[ImportedTable, ...],
        canonical_tables: tuple[Table, ...],
    ) -> tuple[SuggestedMapping, ...]:
        """Use LLM to suggest mappings between imported and canonical schemas."""
        api_key = self._config.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key and self._config.provider == "anthropic":
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable or api_key config required. "
                "Set it with: export ANTHROPIC_API_KEY=your-key"
            )

        prompt = self._build_prompt(imported_tables, canonical_tables)

        if self._config.provider == "anthropic":
            response_text = self._call_anthropic(api_key, prompt)
        elif self._config.provider == "google":
            google_key = self._config.api_key or os.environ.get("GOOGLE_API_KEY", "")
            response_text = self._call_google(google_key, prompt)
        else:
            raise ValueError(f"Unknown provider: {self._config.provider}")

        return self._parse_response(response_text)

    def _build_prompt(
        self,
        imported_tables: tuple[ImportedTable, ...],
        canonical_tables: tuple[Table, ...],
    ) -> str:
        # Build imported schema description
        imported_desc = []
        for table in imported_tables:
            cols = ", ".join(f"{c.name} ({c.data_type})" for c in table.columns)
            imported_desc.append(f"  {table.name}: {cols}")

        # Build canonical schema description
        canonical_desc = []
        for table in canonical_tables:
            cols = ", ".join(
                f"{c.name} ({c.bigquery_type.value})"
                for c in table.columns
            )
            canonical_desc.append(f"  {table.name}: {cols}")

        return f"""You are a telco BSS/OSS data engineer. Analyze these two schemas and suggest field-level mappings.

SOURCE SCHEMA (vendor BSS system):
{chr(10).join(imported_desc)}

TARGET SCHEMA (canonical data model):
{chr(10).join(canonical_desc)}

For each source field, suggest the best matching target field. Return ONLY a JSON array of objects with these fields:
- "vendor_table": source table name
- "vendor_field": source field name
- "canonical_table": target table name
- "canonical_field": target field name
- "confidence": float 0.0-1.0 (how confident you are in this mapping)
- "transformation": SQL transformation if needed (e.g., "CAST(x AS STRING)", "CASE WHEN x='A' THEN 'active'"), or empty string
- "reason": brief explanation

Return ONLY the JSON array, no other text. If a source field has no good match, omit it."""

    def _call_anthropic(self, api_key: str, prompt: str) -> str:
        """Call Anthropic Claude API."""
        import urllib.request
        import urllib.error

        request_body = json.dumps({
            "model": self._config.model,
            "max_tokens": self._config.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        })

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=request_body.encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data["content"][0]["text"]
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.readable() else ""
            raise RuntimeError(f"Anthropic API error {e.code}: {error_body}") from e

    def _call_google(self, api_key: str, prompt: str) -> str:
        """Call Google Gemini API."""
        import urllib.request
        import urllib.error

        request_body = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
        })

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=request_body.encode(),
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.readable() else ""
            raise RuntimeError(f"Google API error {e.code}: {error_body}") from e

    def _parse_response(self, text: str) -> tuple[SuggestedMapping, ...]:
        """Parse LLM response into SuggestedMapping objects."""
        # Extract JSON from response (handle markdown code blocks)
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])  # Strip code fences

        try:
            mappings_data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON array in the text
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                mappings_data = json.loads(text[start:end])
            else:
                return ()

        suggestions: list[SuggestedMapping] = []
        for m in mappings_data:
            suggestions.append(SuggestedMapping(
                vendor_table=m["vendor_table"],
                vendor_field=m["vendor_field"],
                canonical_table=m["canonical_table"],
                canonical_field=m["canonical_field"],
                confidence=float(m.get("confidence", 0.8)),
                match_reason=f"LLM: {m.get('reason', 'AI-suggested')}",
            ))
        return tuple(suggestions)
