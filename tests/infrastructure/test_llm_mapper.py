"""Tests for the Claude API-powered schema mapper."""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from taa.domain.entities.column import Column
from taa.domain.entities.table import Table
from taa.domain.value_objects.enums import BigQueryType, TelcoDomain
from taa.infrastructure.llm.claude_mapper import (
    AIMappingResult,
    AIMappingSuggestion,
    ClaudeSchemaMapper,
)
from taa.infrastructure.schema_import.parser import ImportedColumn, ImportedTable


# ---- Fixtures ----

@pytest.fixture
def imported_tables() -> tuple[ImportedTable, ...]:
    return (
        ImportedTable(
            name="CM_SUBSCRIBER",
            columns=(
                ImportedColumn(name="SUBSCRIBER_ID", data_type="VARCHAR"),
                ImportedColumn(name="MSISDN", data_type="VARCHAR"),
                ImportedColumn(name="STATUS", data_type="CHAR"),
                ImportedColumn(name="ACTIVATION_DT", data_type="DATE"),
            ),
        ),
    )


@pytest.fixture
def canonical_tables() -> tuple[Table, ...]:
    return (
        Table(
            name="subscriber_profile",
            telco_domain=TelcoDomain.SUBSCRIBER,
            columns=(
                Column(name="subscriber_id", bigquery_type=BigQueryType.STRING),
                Column(name="msisdn", bigquery_type=BigQueryType.STRING),
                Column(name="status", bigquery_type=BigQueryType.STRING),
                Column(name="activation_date", bigquery_type=BigQueryType.DATE),
            ),
        ),
    )


def _make_tool_use_response(mappings: list[dict], model: str = "claude-sonnet-4-20250514"):
    """Build a mock Anthropic response object with a tool_use content block."""
    tool_block = SimpleNamespace(
        type="tool_use",
        name="submit_mapping_suggestions",
        input={"mappings": mappings},
    )
    return SimpleNamespace(
        content=[tool_block],
        model=model,
    )


_SAMPLE_MAPPINGS = [
    {
        "vendor_table": "CM_SUBSCRIBER",
        "vendor_field": "SUBSCRIBER_ID",
        "canonical_table": "subscriber_profile",
        "canonical_field": "subscriber_id",
        "confidence": 0.98,
        "reasoning": "Direct ID field match in subscriber context.",
        "transformation": "",
    },
    {
        "vendor_table": "CM_SUBSCRIBER",
        "vendor_field": "MSISDN",
        "canonical_table": "subscriber_profile",
        "canonical_field": "msisdn",
        "confidence": 0.99,
        "reasoning": "MSISDN is a standard telco identifier.",
        "transformation": "",
    },
    {
        "vendor_table": "CM_SUBSCRIBER",
        "vendor_field": "STATUS",
        "canonical_table": "subscriber_profile",
        "canonical_field": "status",
        "confidence": 0.90,
        "reasoning": "Status field semantic match.",
        "transformation": "CASE WHEN STATUS='A' THEN 'active' WHEN STATUS='S' THEN 'suspended' END",
    },
    {
        "vendor_table": "CM_SUBSCRIBER",
        "vendor_field": "ACTIVATION_DT",
        "canonical_table": "subscriber_profile",
        "canonical_field": "activation_date",
        "confidence": 0.95,
        "reasoning": "DT is a common abbreviation for date in BSS systems.",
        "transformation": "CAST(ACTIVATION_DT AS DATE)",
    },
]


@pytest.fixture
def mock_anthropic_module():
    """Inject a mock ``anthropic`` module into sys.modules so the local import
    inside ``_call_claude`` picks it up, then restore afterwards."""
    mock_module = MagicMock()
    mock_client = MagicMock()
    mock_module.Anthropic.return_value = mock_client
    original = sys.modules.get("anthropic")
    sys.modules["anthropic"] = mock_module
    yield mock_module, mock_client
    if original is not None:
        sys.modules["anthropic"] = original
    else:
        sys.modules.pop("anthropic", None)


# ---- Tests: graceful fallback when no API key ----

class TestClaudeSchemaMapperNoKey:
    def test_returns_unavailable_when_no_key(self, imported_tables, canonical_tables):
        """When ANTHROPIC_API_KEY is absent the mapper returns a non-available result."""
        old = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            mapper = ClaudeSchemaMapper(api_key="")
            result = mapper.suggest_mappings(imported_tables, canonical_tables)

            assert result.available is False
            assert result.suggestions == ()
            assert "ANTHROPIC_API_KEY" in result.message
        finally:
            if old is not None:
                os.environ["ANTHROPIC_API_KEY"] = old

    def test_returns_unavailable_when_env_key_empty(self, imported_tables, canonical_tables):
        """Empty env var is treated the same as unset."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}, clear=False):
            mapper = ClaudeSchemaMapper()
            result = mapper.suggest_mappings(imported_tables, canonical_tables)
            assert result.available is False


# ---- Tests: successful mapping with mocked API ----

class TestClaudeSchemaMapperMocked:
    def test_successful_mapping(
        self, imported_tables, canonical_tables, mock_anthropic_module,
    ):
        """With a valid key, the mapper returns structured suggestions from tool_use."""
        _, mock_client = mock_anthropic_module
        mock_client.messages.create.return_value = _make_tool_use_response(_SAMPLE_MAPPINGS)

        mapper = ClaudeSchemaMapper(api_key="test-key-123")
        result = mapper.suggest_mappings(imported_tables, canonical_tables)

        assert result.available is True
        assert result.message == ""
        assert result.model_used == "claude-sonnet-4-20250514"
        assert len(result.suggestions) == 4

        # Check first suggestion detail
        sub_id = result.suggestions[0]
        assert sub_id.vendor_table == "CM_SUBSCRIBER"
        assert sub_id.vendor_field == "SUBSCRIBER_ID"
        assert sub_id.canonical_table == "subscriber_profile"
        assert sub_id.canonical_field == "subscriber_id"
        assert sub_id.confidence == 0.98
        assert "ID field" in sub_id.reasoning

        # Check transformation is captured
        status = result.suggestions[2]
        assert "CASE WHEN" in status.transformation

    def test_api_call_parameters(
        self, imported_tables, canonical_tables, mock_anthropic_module,
    ):
        """Verify correct SDK call parameters (model, tools, tool_choice)."""
        mock_module, mock_client = mock_anthropic_module
        mock_client.messages.create.return_value = _make_tool_use_response([])

        mapper = ClaudeSchemaMapper(api_key="test-key", model="claude-sonnet-4-20250514")
        mapper.suggest_mappings(imported_tables, canonical_tables)

        # Verify Anthropic client was created with the right key
        mock_module.Anthropic.assert_called_once_with(api_key="test-key")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["max_tokens"] == 4096
        assert len(call_kwargs["tools"]) == 1
        assert call_kwargs["tools"][0]["name"] == "submit_mapping_suggestions"
        assert call_kwargs["tool_choice"] == {
            "type": "tool",
            "name": "submit_mapping_suggestions",
        }

        # System prompt should mention telco
        assert "telco" in call_kwargs["system"].lower()

        # User message should contain both schemas
        user_msg = call_kwargs["messages"][0]["content"]
        assert "CM_SUBSCRIBER" in user_msg
        assert "subscriber_profile" in user_msg

    def test_empty_response(
        self, imported_tables, canonical_tables, mock_anthropic_module,
    ):
        """An empty mappings array is handled gracefully."""
        _, mock_client = mock_anthropic_module
        mock_client.messages.create.return_value = _make_tool_use_response([])

        mapper = ClaudeSchemaMapper(api_key="test-key")
        result = mapper.suggest_mappings(imported_tables, canonical_tables)

        assert result.available is True
        assert result.suggestions == ()

    def test_api_exception_falls_back_gracefully(
        self, imported_tables, canonical_tables, mock_anthropic_module,
    ):
        """When the Anthropic SDK raises, the mapper returns a fallback result."""
        _, mock_client = mock_anthropic_module
        mock_client.messages.create.side_effect = RuntimeError("API unavailable")

        mapper = ClaudeSchemaMapper(api_key="test-key")
        result = mapper.suggest_mappings(imported_tables, canonical_tables)

        assert result.available is False
        assert result.suggestions == ()
        assert "failed" in result.message.lower()


# ---- Tests: response parsing ----

class TestResponseParsing:
    def test_parse_tool_use_block(self):
        """Directly test _parse_tool_response with a tool_use block."""
        mapper = ClaudeSchemaMapper(api_key="x")
        response = _make_tool_use_response([
            {
                "vendor_table": "T1",
                "vendor_field": "F1",
                "canonical_table": "T2",
                "canonical_field": "F2",
                "confidence": 0.85,
                "reasoning": "test reason",
            },
        ])

        result = mapper._parse_tool_response(response)
        assert len(result.suggestions) == 1
        assert result.suggestions[0].vendor_field == "F1"
        assert result.suggestions[0].confidence == 0.85
        assert result.suggestions[0].reasoning == "test reason"
        assert result.suggestions[0].transformation == ""

    def test_parse_tool_use_with_string_input(self):
        """Handle the case where block.input is a JSON string instead of dict."""
        mapper = ClaudeSchemaMapper(api_key="x")
        mappings_data = {
            "mappings": [
                {
                    "vendor_table": "SRC",
                    "vendor_field": "col_a",
                    "canonical_table": "TGT",
                    "canonical_field": "col_b",
                    "confidence": 0.7,
                    "reasoning": "approximate",
                    "transformation": "UPPER(col_a)",
                },
            ],
        }
        tool_block = SimpleNamespace(
            type="tool_use",
            name="submit_mapping_suggestions",
            input=json.dumps(mappings_data),
        )
        response = SimpleNamespace(content=[tool_block], model="test-model")

        result = mapper._parse_tool_response(response)
        assert len(result.suggestions) == 1
        assert result.suggestions[0].transformation == "UPPER(col_a)"

    def test_parse_ignores_non_tool_blocks(self):
        """Text blocks in the response are ignored."""
        mapper = ClaudeSchemaMapper(api_key="x")
        text_block = SimpleNamespace(type="text", text="Some reasoning text")
        tool_block = SimpleNamespace(
            type="tool_use",
            name="submit_mapping_suggestions",
            input={"mappings": [
                {
                    "vendor_table": "A",
                    "vendor_field": "B",
                    "canonical_table": "C",
                    "canonical_field": "D",
                    "confidence": 0.5,
                    "reasoning": "guess",
                },
            ]},
        )
        response = SimpleNamespace(content=[text_block, tool_block], model="m")

        result = mapper._parse_tool_response(response)
        assert len(result.suggestions) == 1

    def test_parse_ignores_other_tool_names(self):
        """Tool blocks with a different name are ignored."""
        mapper = ClaudeSchemaMapper(api_key="x")
        other_block = SimpleNamespace(
            type="tool_use",
            name="some_other_tool",
            input={"data": "irrelevant"},
        )
        response = SimpleNamespace(content=[other_block], model="m")

        result = mapper._parse_tool_response(response)
        assert result.suggestions == ()

    def test_parse_multiple_tool_blocks(self):
        """Multiple tool_use blocks with the right name accumulate suggestions."""
        mapper = ClaudeSchemaMapper(api_key="x")
        block1 = SimpleNamespace(
            type="tool_use",
            name="submit_mapping_suggestions",
            input={"mappings": [
                {
                    "vendor_table": "T1",
                    "vendor_field": "F1",
                    "canonical_table": "T2",
                    "canonical_field": "F2",
                    "confidence": 0.9,
                    "reasoning": "first",
                },
            ]},
        )
        block2 = SimpleNamespace(
            type="tool_use",
            name="submit_mapping_suggestions",
            input={"mappings": [
                {
                    "vendor_table": "T3",
                    "vendor_field": "F3",
                    "canonical_table": "T4",
                    "canonical_field": "F4",
                    "confidence": 0.7,
                    "reasoning": "second",
                },
            ]},
        )
        response = SimpleNamespace(content=[block1, block2], model="m")

        result = mapper._parse_tool_response(response)
        assert len(result.suggestions) == 2


# ---- Tests: prompt construction ----

class TestPromptConstruction:
    def test_system_prompt_content(self):
        mapper = ClaudeSchemaMapper(api_key="x")
        system = mapper._build_system_prompt()
        assert "telco" in system.lower()
        assert "BSS" in system
        assert "confidence" in system.lower()

    def test_user_prompt_includes_schemas(self, imported_tables, canonical_tables):
        mapper = ClaudeSchemaMapper(api_key="x")
        prompt = mapper._build_user_prompt(imported_tables, canonical_tables)

        assert "SOURCE SCHEMA" in prompt
        assert "TARGET SCHEMA" in prompt
        assert "CM_SUBSCRIBER" in prompt
        assert "SUBSCRIBER_ID" in prompt
        assert "subscriber_profile" in prompt
        assert "subscriber_id" in prompt

    def test_user_prompt_includes_data_types(self, imported_tables, canonical_tables):
        mapper = ClaudeSchemaMapper(api_key="x")
        prompt = mapper._build_user_prompt(imported_tables, canonical_tables)

        assert "VARCHAR" in prompt
        assert "STRING" in prompt

    def test_user_prompt_empty_tables(self):
        mapper = ClaudeSchemaMapper(api_key="x")
        prompt = mapper._build_user_prompt((), ())
        assert "SOURCE SCHEMA" in prompt
        assert "TARGET SCHEMA" in prompt


# ---- Tests: data classes ----

class TestDataClasses:
    def test_ai_mapping_suggestion_frozen(self):
        s = AIMappingSuggestion(
            vendor_table="T1",
            vendor_field="F1",
            canonical_table="T2",
            canonical_field="F2",
            confidence=0.9,
            reasoning="test",
        )
        assert s.transformation == ""
        with pytest.raises(AttributeError):
            s.confidence = 0.5  # type: ignore[misc]

    def test_ai_mapping_result_defaults(self):
        r = AIMappingResult()
        assert r.suggestions == ()
        assert r.model_used == ""
        assert r.message == ""
        assert r.available is True

    def test_ai_mapping_result_unavailable(self):
        r = AIMappingResult(available=False, message="No key")
        assert r.available is False
        assert r.message == "No key"
