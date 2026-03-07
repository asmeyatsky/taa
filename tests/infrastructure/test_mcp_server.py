"""Comprehensive tests for the TAA MCP server."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

mcp = pytest.importorskip("mcp", reason="mcp package not installed")

from mcp.server import Server
from mcp.types import (
    Tool,
    Resource,
    TextContent,
    ListToolsRequest,
    ListResourcesRequest,
    ReadResourceRequest,
    CallToolRequest,
    ServerResult,
)

from taa.application.dtos.models import (
    GenerationRequest,
    GenerationResult,
    DomainInfo,
    VendorInfo,
    JurisdictionInfo,
    MappingResult,
)
from taa.domain.value_objects.enums import PIICategory


# ---------------------------------------------------------------------------
# Helpers to invoke registered MCP handlers
# ---------------------------------------------------------------------------


def _build_list_tools_request() -> ListToolsRequest:
    """Build a ListToolsRequest suitable for passing to the handler."""
    return ListToolsRequest(method="tools/list")


def _build_list_resources_request() -> ListResourcesRequest:
    """Build a ListResourcesRequest suitable for passing to the handler."""
    return ListResourcesRequest(method="resources/list")


def _build_read_resource_request(uri: str) -> ReadResourceRequest:
    """Build a ReadResourceRequest for a given URI."""
    return ReadResourceRequest(method="resources/read", params={"uri": uri})


def _build_call_tool_request(name: str, arguments: dict | None = None) -> CallToolRequest:
    """Build a CallToolRequest for a given tool name and arguments."""
    return CallToolRequest(
        method="tools/call",
        params={"name": name, "arguments": arguments or {}},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_container():
    """Return a fully mocked Container whose command/query properties return MagicMock instances."""
    with patch("taa.infrastructure.mcp_servers.server.Container") as MockCls:
        container = MagicMock()

        # Commands -- each .execute() returns a GenerationResult by default
        default_result = GenerationResult(
            success=True,
            files_generated=["output/test.sql"],
            summary="generated",
        )
        container.generate_ddl.execute.return_value = default_result
        container.generate_terraform.execute.return_value = default_result
        container.generate_pipeline.execute.return_value = default_result
        container.generate_dag.execute.return_value = default_result
        container.generate_compliance.execute.return_value = default_result
        container.generate_full_pack.execute.return_value = default_result

        mapping_result = MappingResult(
            vendor="amdocs",
            domain="subscriber",
            total_fields=10,
            mapped_fields=8,
            coverage_pct=80.0,
            unmapped_fields=["field_a", "field_b"],
            conflicts=0,
        )
        container.map_vendor_schema.execute.return_value = mapping_result

        # Queries
        container.list_domains.execute.return_value = [
            DomainInfo(name="subscriber", table_count=3, tables=["t1", "t2", "t3"]),
            DomainInfo(name="cdr_event", table_count=2, tables=["t4", "t5"]),
        ]
        container.list_vendors.execute.return_value = [
            VendorInfo(name="amdocs"),
            VendorInfo(name="huawei_cbs"),
        ]
        container.list_jurisdictions.execute.return_value = [
            JurisdictionInfo(
                code="SA",
                name="Saudi Arabia",
                framework="PDPL",
                gcp_region="me-central1",
                data_residency_required=True,
                rule_count=5,
            ),
        ]
        container.get_domain_model.execute.return_value = DomainInfo(
            name="subscriber", table_count=3, tables=["t1", "t2", "t3"],
        )

        # Compliance rule repo (used in read_resource for jurisdiction rules)
        mock_rule = MagicMock()
        mock_rule.rule_id = "SA-PDPL-001"
        mock_rule.framework = "PDPL"
        mock_rule.data_residency_required = True
        mock_rule.encryption_required = True
        container.compliance_rule_repo.load_rules.return_value = [mock_rule]

        MockCls.return_value = container
        yield container


@pytest.fixture()
def server(mock_container):
    """Create the TAA MCP server with a mocked container."""
    from taa.infrastructure.mcp_servers.server import create_server
    return create_server()


# ---------------------------------------------------------------------------
# 1. create_server() basic sanity
# ---------------------------------------------------------------------------


class TestCreateServer:
    """Verify create_server() returns a properly configured Server."""

    def test_returns_server_instance(self, server):
        assert isinstance(server, Server)

    def test_server_name_is_taa(self, server):
        assert server.name == "taa"

    def test_has_list_tools_handler(self, server):
        assert ListToolsRequest in server.request_handlers

    def test_has_call_tool_handler(self, server):
        assert CallToolRequest in server.request_handlers

    def test_has_list_resources_handler(self, server):
        assert ListResourcesRequest in server.request_handlers

    def test_has_read_resource_handler(self, server):
        assert ReadResourceRequest in server.request_handlers


# ---------------------------------------------------------------------------
# 2. list_tools
# ---------------------------------------------------------------------------


class TestListTools:
    """Verify the list_tools handler returns 7 properly defined tools."""

    @pytest.fixture(autouse=True)
    def _setup(self, server):
        self.server = server
        self.handler = server.request_handlers[ListToolsRequest]

    @pytest.mark.asyncio
    async def test_returns_seven_tools(self):
        result: ServerResult = await self.handler(_build_list_tools_request())
        tools = result.root.tools
        assert len(tools) == 7

    @pytest.mark.asyncio
    async def test_tool_names(self):
        result = await self.handler(_build_list_tools_request())
        names = {t.name for t in result.root.tools}
        expected = {
            "generate_ddl",
            "generate_terraform",
            "generate_pipeline",
            "generate_dag",
            "generate_compliance_report",
            "generate_full_pack",
            "map_vendor_schema",
        }
        assert names == expected

    @pytest.mark.asyncio
    async def test_each_tool_has_input_schema(self):
        result = await self.handler(_build_list_tools_request())
        for tool in result.root.tools:
            assert tool.inputSchema is not None
            assert "properties" in tool.inputSchema

    @pytest.mark.asyncio
    async def test_each_tool_has_description(self):
        result = await self.handler(_build_list_tools_request())
        for tool in result.root.tools:
            assert tool.description, f"Tool {tool.name} is missing a description"

    @pytest.mark.asyncio
    async def test_generate_ddl_schema_has_domains_required(self):
        result = await self.handler(_build_list_tools_request())
        ddl_tool = next(t for t in result.root.tools if t.name == "generate_ddl")
        assert "domains" in ddl_tool.inputSchema["properties"]
        assert "domains" in ddl_tool.inputSchema.get("required", [])

    @pytest.mark.asyncio
    async def test_generate_ddl_schema_has_jurisdiction(self):
        result = await self.handler(_build_list_tools_request())
        ddl_tool = next(t for t in result.root.tools if t.name == "generate_ddl")
        props = ddl_tool.inputSchema["properties"]
        assert "jurisdiction" in props
        assert props["jurisdiction"].get("default") == "SA"

    @pytest.mark.asyncio
    async def test_map_vendor_schema_requires_vendor_and_domain(self):
        result = await self.handler(_build_list_tools_request())
        tool = next(t for t in result.root.tools if t.name == "map_vendor_schema")
        required = tool.inputSchema.get("required", [])
        assert "vendor" in required
        assert "domain" in required

    @pytest.mark.asyncio
    async def test_generate_pipeline_has_vendor_field(self):
        result = await self.handler(_build_list_tools_request())
        tool = next(t for t in result.root.tools if t.name == "generate_pipeline")
        assert "vendor" in tool.inputSchema["properties"]

    @pytest.mark.asyncio
    async def test_generate_full_pack_has_all_fields(self):
        result = await self.handler(_build_list_tools_request())
        tool = next(t for t in result.root.tools if t.name == "generate_full_pack")
        props = tool.inputSchema["properties"]
        assert "domains" in props
        assert "jurisdiction" in props
        assert "vendor" in props

    @pytest.mark.asyncio
    async def test_tools_are_tool_instances(self):
        result = await self.handler(_build_list_tools_request())
        for tool in result.root.tools:
            assert isinstance(tool, Tool)


# ---------------------------------------------------------------------------
# 3. call_tool
# ---------------------------------------------------------------------------


class TestCallTool:
    """Verify the call_tool handler dispatches to the correct commands."""

    @pytest.fixture(autouse=True)
    def _setup(self, server, mock_container):
        self.server = server
        self.container = mock_container
        self.handler = server.request_handlers[CallToolRequest]
        # Pre-populate tool cache so input validation works
        self._populate_cache()

    def _populate_cache(self):
        """Populate the server's tool cache from list_tools result."""
        import asyncio
        list_handler = self.server.request_handlers[ListToolsRequest]
        asyncio.get_event_loop().run_until_complete(
            list_handler(_build_list_tools_request())
        )

    @pytest.mark.asyncio
    async def test_generate_ddl_calls_container(self):
        req = _build_call_tool_request("generate_ddl", {"domains": ["subscriber"]})
        result = await self.handler(req)
        self.container.generate_ddl.execute.assert_called_once()
        call_args = self.container.generate_ddl.execute.call_args[0][0]
        assert isinstance(call_args, GenerationRequest)
        assert call_args.domains == ["subscriber"]

    @pytest.mark.asyncio
    async def test_generate_ddl_returns_text_content(self):
        req = _build_call_tool_request("generate_ddl", {"domains": ["subscriber"]})
        result = await self.handler(req)
        content = result.root.content
        assert len(content) >= 1
        assert content[0].type == "text"

    @pytest.mark.asyncio
    async def test_generate_ddl_with_jurisdiction(self):
        req = _build_call_tool_request(
            "generate_ddl", {"domains": ["subscriber"], "jurisdiction": "AE"}
        )
        result = await self.handler(req)
        call_args = self.container.generate_ddl.execute.call_args[0][0]
        assert call_args.jurisdiction == "AE"

    @pytest.mark.asyncio
    async def test_generate_ddl_default_jurisdiction_is_sa(self):
        req = _build_call_tool_request("generate_ddl", {"domains": ["cdr_event"]})
        await self.handler(req)
        call_args = self.container.generate_ddl.execute.call_args[0][0]
        assert call_args.jurisdiction == "SA"

    @pytest.mark.asyncio
    async def test_generate_terraform(self):
        req = _build_call_tool_request(
            "generate_terraform", {"domains": ["subscriber"], "jurisdiction": "SA"}
        )
        await self.handler(req)
        self.container.generate_terraform.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_pipeline(self):
        req = _build_call_tool_request(
            "generate_pipeline", {"domains": ["cdr_event"], "vendor": "amdocs"}
        )
        await self.handler(req)
        self.container.generate_pipeline.execute.assert_called_once()
        call_args = self.container.generate_pipeline.execute.call_args[0][0]
        assert call_args.vendor == "amdocs"

    @pytest.mark.asyncio
    async def test_generate_dag(self):
        req = _build_call_tool_request("generate_dag", {"domains": ["subscriber"]})
        await self.handler(req)
        self.container.generate_dag.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_dag_result_is_json(self):
        req = _build_call_tool_request("generate_dag", {"domains": ["subscriber"]})
        result = await self.handler(req)
        text = result.root.content[0].text
        parsed = json.loads(text)
        assert parsed["success"] is True

    @pytest.mark.asyncio
    async def test_generate_compliance_report(self):
        req = _build_call_tool_request(
            "generate_compliance_report", {"domains": ["subscriber"]}
        )
        await self.handler(req)
        self.container.generate_compliance.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_full_pack(self):
        req = _build_call_tool_request(
            "generate_full_pack",
            {"domains": ["subscriber"], "jurisdiction": "SA", "vendor": "amdocs"},
        )
        await self.handler(req)
        self.container.generate_full_pack.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_full_pack_passes_vendor(self):
        req = _build_call_tool_request(
            "generate_full_pack",
            {"domains": ["subscriber"], "vendor": "huawei_cbs"},
        )
        await self.handler(req)
        call_args = self.container.generate_full_pack.execute.call_args[0][0]
        assert call_args.vendor == "huawei_cbs"

    @pytest.mark.asyncio
    async def test_map_vendor_schema(self):
        req = _build_call_tool_request(
            "map_vendor_schema", {"vendor": "amdocs", "domain": "subscriber"}
        )
        result = await self.handler(req)
        self.container.map_vendor_schema.execute.assert_called_once_with(
            "amdocs", "subscriber"
        )

    @pytest.mark.asyncio
    async def test_map_vendor_schema_returns_mapping_result_json(self):
        req = _build_call_tool_request(
            "map_vendor_schema", {"vendor": "amdocs", "domain": "subscriber"}
        )
        result = await self.handler(req)
        text = result.root.content[0].text
        parsed = json.loads(text)
        assert parsed["vendor"] == "amdocs"
        assert parsed["domain"] == "subscriber"
        assert parsed["total_fields"] == 10
        assert parsed["coverage_pct"] == 80.0

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error_text(self):
        req = _build_call_tool_request("nonexistent_tool", {})
        result = await self.handler(req)
        text = result.root.content[0].text
        assert "Unknown tool" in text or "nonexistent_tool" in text

    @pytest.mark.asyncio
    async def test_generate_ddl_result_contains_files_generated(self):
        req = _build_call_tool_request("generate_ddl", {"domains": ["subscriber"]})
        result = await self.handler(req)
        text = result.root.content[0].text
        parsed = json.loads(text)
        assert "files_generated" in parsed
        assert "output/test.sql" in parsed["files_generated"]


# ---------------------------------------------------------------------------
# 4. list_resources
# ---------------------------------------------------------------------------


class TestListResources:
    """Verify list_resources handler returns 4 static resources."""

    @pytest.fixture(autouse=True)
    def _setup(self, server):
        self.handler = server.request_handlers[ListResourcesRequest]

    @pytest.mark.asyncio
    async def test_returns_four_resources(self):
        result = await self.handler(_build_list_resources_request())
        resources = result.root.resources
        assert len(resources) == 4

    @pytest.mark.asyncio
    async def test_resource_uris(self):
        result = await self.handler(_build_list_resources_request())
        uris = {str(r.uri) for r in result.root.resources}
        expected = {
            "taa://domains",
            "taa://vendors",
            "taa://jurisdictions",
            "taa://pii-categories",
        }
        assert uris == expected

    @pytest.mark.asyncio
    async def test_each_resource_has_name_and_description(self):
        result = await self.handler(_build_list_resources_request())
        for resource in result.root.resources:
            assert resource.name, f"Resource {resource.uri} is missing a name"
            assert resource.description, f"Resource {resource.uri} is missing a description"

    @pytest.mark.asyncio
    async def test_resources_are_resource_instances(self):
        result = await self.handler(_build_list_resources_request())
        for resource in result.root.resources:
            assert isinstance(resource, Resource)

    @pytest.mark.asyncio
    async def test_domains_resource_metadata(self):
        result = await self.handler(_build_list_resources_request())
        domains_res = next(r for r in result.root.resources if str(r.uri) == "taa://domains")
        assert domains_res.name == "Telco Domains"

    @pytest.mark.asyncio
    async def test_vendors_resource_metadata(self):
        result = await self.handler(_build_list_resources_request())
        res = next(r for r in result.root.resources if str(r.uri) == "taa://vendors")
        assert res.name == "BSS Vendors"

    @pytest.mark.asyncio
    async def test_jurisdictions_resource_metadata(self):
        result = await self.handler(_build_list_resources_request())
        res = next(r for r in result.root.resources if str(r.uri) == "taa://jurisdictions")
        assert res.name == "Jurisdictions"

    @pytest.mark.asyncio
    async def test_pii_categories_resource_metadata(self):
        result = await self.handler(_build_list_resources_request())
        res = next(r for r in result.root.resources if str(r.uri) == "taa://pii-categories")
        assert res.name == "PII Categories"


# ---------------------------------------------------------------------------
# 5. read_resource -- static resources
# ---------------------------------------------------------------------------


class TestReadResourceStatic:
    """Verify read_resource for the 4 static resource URIs."""

    @pytest.fixture(autouse=True)
    def _setup(self, server, mock_container):
        self.server = server
        self.container = mock_container
        self.handler = server.request_handlers[ReadResourceRequest]

    @pytest.mark.asyncio
    async def test_domains_returns_json_list(self):
        req = _build_read_resource_request("taa://domains")
        result = await self.handler(req)
        text = result.root.contents[0].text
        parsed = json.loads(text)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "subscriber"

    @pytest.mark.asyncio
    async def test_domains_calls_list_domains_query(self):
        req = _build_read_resource_request("taa://domains")
        await self.handler(req)
        self.container.list_domains.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_vendors_returns_json_list(self):
        req = _build_read_resource_request("taa://vendors")
        result = await self.handler(req)
        text = result.root.contents[0].text
        parsed = json.loads(text)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "amdocs"

    @pytest.mark.asyncio
    async def test_vendors_calls_list_vendors_query(self):
        req = _build_read_resource_request("taa://vendors")
        await self.handler(req)
        self.container.list_vendors.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_jurisdictions_returns_json_list(self):
        req = _build_read_resource_request("taa://jurisdictions")
        result = await self.handler(req)
        text = result.root.contents[0].text
        parsed = json.loads(text)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["code"] == "SA"

    @pytest.mark.asyncio
    async def test_jurisdictions_calls_list_jurisdictions_query(self):
        req = _build_read_resource_request("taa://jurisdictions")
        await self.handler(req)
        self.container.list_jurisdictions.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_pii_categories_returns_all_categories(self):
        req = _build_read_resource_request("taa://pii-categories")
        result = await self.handler(req)
        text = result.root.contents[0].text
        parsed = json.loads(text)
        assert isinstance(parsed, list)
        assert len(parsed) == len(PIICategory)

    @pytest.mark.asyncio
    async def test_pii_categories_have_name_and_description(self):
        req = _build_read_resource_request("taa://pii-categories")
        result = await self.handler(req)
        parsed = json.loads(result.root.contents[0].text)
        for entry in parsed:
            assert "name" in entry
            assert "description" in entry

    @pytest.mark.asyncio
    async def test_pii_categories_values_match_enum(self):
        req = _build_read_resource_request("taa://pii-categories")
        result = await self.handler(req)
        parsed = json.loads(result.root.contents[0].text)
        enum_values = {c.value for c in PIICategory}
        returned_values = {entry["name"] for entry in parsed}
        assert returned_values == enum_values


# ---------------------------------------------------------------------------
# 6. read_resource -- dynamic domain resource
# ---------------------------------------------------------------------------


class TestReadResourceDomain:
    """Verify read_resource for taa://domains/{domain}."""

    @pytest.fixture(autouse=True)
    def _setup(self, server, mock_container):
        self.container = mock_container
        self.handler = server.request_handlers[ReadResourceRequest]

    @pytest.mark.asyncio
    async def test_domains_subscriber(self):
        req = _build_read_resource_request("taa://domains/subscriber")
        result = await self.handler(req)
        text = result.root.contents[0].text
        parsed = json.loads(text)
        assert parsed["name"] == "subscriber"
        assert parsed["table_count"] == 3

    @pytest.mark.asyncio
    async def test_domains_subscriber_calls_get_domain_model(self):
        req = _build_read_resource_request("taa://domains/subscriber")
        await self.handler(req)
        self.container.get_domain_model.execute.assert_called_once_with("subscriber")

    @pytest.mark.asyncio
    async def test_domains_cdr_event(self):
        self.container.get_domain_model.execute.return_value = DomainInfo(
            name="cdr_event", table_count=2, tables=["cdr_raw", "cdr_mediated"],
        )
        req = _build_read_resource_request("taa://domains/cdr_event")
        result = await self.handler(req)
        parsed = json.loads(result.root.contents[0].text)
        assert parsed["name"] == "cdr_event"
        assert parsed["table_count"] == 2


# ---------------------------------------------------------------------------
# 7. read_resource -- dynamic vendor mappings
# ---------------------------------------------------------------------------


class TestReadResourceVendorMappings:
    """Verify read_resource for taa://vendors/{vendor}/mappings/{domain}."""

    @pytest.fixture(autouse=True)
    def _setup(self, server, mock_container):
        self.container = mock_container
        self.handler = server.request_handlers[ReadResourceRequest]

    @pytest.mark.asyncio
    async def test_vendor_mapping_calls_map_vendor_schema(self):
        req = _build_read_resource_request("taa://vendors/amdocs/mappings/subscriber")
        await self.handler(req)
        self.container.map_vendor_schema.execute.assert_called_once_with(
            "amdocs", "subscriber"
        )

    @pytest.mark.asyncio
    async def test_vendor_mapping_returns_json(self):
        req = _build_read_resource_request("taa://vendors/amdocs/mappings/subscriber")
        result = await self.handler(req)
        text = result.root.contents[0].text
        parsed = json.loads(text)
        assert parsed["vendor"] == "amdocs"
        assert parsed["domain"] == "subscriber"

    @pytest.mark.asyncio
    async def test_vendor_mapping_different_vendor(self):
        self.container.map_vendor_schema.execute.return_value = MappingResult(
            vendor="huawei_cbs", domain="cdr_event",
            total_fields=15, mapped_fields=12, coverage_pct=80.0,
        )
        req = _build_read_resource_request("taa://vendors/huawei_cbs/mappings/cdr_event")
        result = await self.handler(req)
        parsed = json.loads(result.root.contents[0].text)
        assert parsed["vendor"] == "huawei_cbs"
        assert parsed["domain"] == "cdr_event"


# ---------------------------------------------------------------------------
# 8. read_resource -- dynamic jurisdiction rules
# ---------------------------------------------------------------------------


class TestReadResourceJurisdictionRules:
    """Verify read_resource for taa://jurisdictions/{jurisdiction}/rules."""

    @pytest.fixture(autouse=True)
    def _setup(self, server, mock_container):
        self.container = mock_container
        self.handler = server.request_handlers[ReadResourceRequest]

    @pytest.mark.asyncio
    async def test_jurisdiction_rules_calls_load_rules(self):
        req = _build_read_resource_request("taa://jurisdictions/SA/rules")
        await self.handler(req)
        self.container.compliance_rule_repo.load_rules.assert_called_once_with("SA")

    @pytest.mark.asyncio
    async def test_jurisdiction_rules_returns_json_list(self):
        req = _build_read_resource_request("taa://jurisdictions/SA/rules")
        result = await self.handler(req)
        text = result.root.contents[0].text
        parsed = json.loads(text)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["rule_id"] == "SA-PDPL-001"
        assert parsed[0]["framework"] == "PDPL"
        assert parsed[0]["data_residency_required"] is True
        assert parsed[0]["encryption_required"] is True

    @pytest.mark.asyncio
    async def test_jurisdiction_rules_different_code(self):
        mock_rule = MagicMock()
        mock_rule.rule_id = "AE-DIFC-001"
        mock_rule.framework = "DIFC"
        mock_rule.data_residency_required = False
        mock_rule.encryption_required = True
        self.container.compliance_rule_repo.load_rules.return_value = [mock_rule]

        req = _build_read_resource_request("taa://jurisdictions/AE/rules")
        result = await self.handler(req)
        parsed = json.loads(result.root.contents[0].text)
        assert parsed[0]["rule_id"] == "AE-DIFC-001"
        self.container.compliance_rule_repo.load_rules.assert_called_with("AE")


# ---------------------------------------------------------------------------
# 9. read_resource -- unknown URI
# ---------------------------------------------------------------------------


class TestReadResourceUnknown:
    """Verify read_resource returns error JSON for an unrecognized URI."""

    @pytest.fixture(autouse=True)
    def _setup(self, server, mock_container):
        self.handler = server.request_handlers[ReadResourceRequest]

    @pytest.mark.asyncio
    async def test_unknown_uri_returns_error_json(self):
        req = _build_read_resource_request("taa://something-unknown")
        result = await self.handler(req)
        text = result.root.contents[0].text
        parsed = json.loads(text)
        assert "error" in parsed
        assert "Unknown resource" in parsed["error"]

    @pytest.mark.asyncio
    async def test_unknown_uri_includes_uri_in_error(self):
        req = _build_read_resource_request("taa://bogus/path")
        result = await self.handler(req)
        parsed = json.loads(result.root.contents[0].text)
        assert "taa://bogus/path" in parsed["error"]


# ---------------------------------------------------------------------------
# 10. Tool input schemas -- deeper validation
# ---------------------------------------------------------------------------


class TestToolInputSchemas:
    """Verify the JSON-schema structure of each tool's inputSchema."""

    @pytest.fixture(autouse=True)
    def _setup(self, server):
        self.handler = server.request_handlers[ListToolsRequest]

    async def _get_tool(self, name: str) -> Tool:
        result = await self.handler(_build_list_tools_request())
        return next(t for t in result.root.tools if t.name == name)

    @pytest.mark.asyncio
    async def test_domains_property_is_array_of_strings(self):
        tool = await self._get_tool("generate_ddl")
        domains = tool.inputSchema["properties"]["domains"]
        assert domains["type"] == "array"
        assert domains["items"]["type"] == "string"

    @pytest.mark.asyncio
    async def test_generate_dag_requires_only_domains(self):
        tool = await self._get_tool("generate_dag")
        assert tool.inputSchema["required"] == ["domains"]

    @pytest.mark.asyncio
    async def test_map_vendor_schema_properties(self):
        tool = await self._get_tool("map_vendor_schema")
        props = tool.inputSchema["properties"]
        assert "vendor" in props
        assert "domain" in props
        assert props["vendor"]["type"] == "string"
        assert props["domain"]["type"] == "string"

    @pytest.mark.asyncio
    async def test_all_schemas_are_objects(self):
        result = await self.handler(_build_list_tools_request())
        for tool in result.root.tools:
            assert tool.inputSchema.get("type") == "object", (
                f"Tool {tool.name} inputSchema is not type 'object'"
            )


# ---------------------------------------------------------------------------
# 11. call_tool error handling
# ---------------------------------------------------------------------------


class TestCallToolErrors:
    """Verify call_tool error behavior."""

    @pytest.fixture(autouse=True)
    def _setup(self, server, mock_container):
        self.server = server
        self.container = mock_container
        self.handler = server.request_handlers[CallToolRequest]
        # Populate tool cache
        import asyncio
        list_handler = server.request_handlers[ListToolsRequest]
        asyncio.get_event_loop().run_until_complete(
            list_handler(_build_list_tools_request())
        )

    @pytest.mark.asyncio
    async def test_generate_ddl_exception_returns_error(self):
        self.container.generate_ddl.execute.side_effect = ValueError("domain not found")
        req = _build_call_tool_request("generate_ddl", {"domains": ["bad_domain"]})
        result = await self.handler(req)
        text = result.root.content[0].text
        assert "domain not found" in text

    @pytest.mark.asyncio
    async def test_map_vendor_schema_exception_returns_error(self):
        self.container.map_vendor_schema.execute.side_effect = KeyError("unknown vendor")
        req = _build_call_tool_request(
            "map_vendor_schema", {"vendor": "unknown", "domain": "subscriber"}
        )
        result = await self.handler(req)
        text = result.root.content[0].text
        assert "unknown vendor" in text


# ---------------------------------------------------------------------------
# 12. MCP import guard
# ---------------------------------------------------------------------------


class TestMCPImportGuard:
    """Verify create_server raises ImportError when mcp is missing."""

    def test_import_error_when_mcp_unavailable(self):
        import importlib
        import sys
        from taa.infrastructure.mcp_servers import server as srv_module

        # Temporarily hide the mcp package
        original = sys.modules.get("mcp.server")
        original_types = sys.modules.get("mcp.types")
        try:
            sys.modules["mcp.server"] = None  # type: ignore[assignment]
            sys.modules["mcp.types"] = None  # type: ignore[assignment]
            importlib.reload(srv_module)
            with pytest.raises(ImportError, match="mcp package required"):
                srv_module.create_server()
        finally:
            # Restore
            if original is not None:
                sys.modules["mcp.server"] = original
            else:
                sys.modules.pop("mcp.server", None)
            if original_types is not None:
                sys.modules["mcp.types"] = original_types
            else:
                sys.modules.pop("mcp.types", None)
            importlib.reload(srv_module)


# ---------------------------------------------------------------------------
# 13. Multiple domain generation
# ---------------------------------------------------------------------------


class TestMultipleDomains:
    """Verify tool calls work with multiple domains."""

    @pytest.fixture(autouse=True)
    def _setup(self, server, mock_container):
        self.container = mock_container
        self.handler = server.request_handlers[CallToolRequest]
        # Populate tool cache
        import asyncio
        list_handler = server.request_handlers[ListToolsRequest]
        asyncio.get_event_loop().run_until_complete(
            list_handler(_build_list_tools_request())
        )

    @pytest.mark.asyncio
    async def test_generate_ddl_multiple_domains(self):
        req = _build_call_tool_request(
            "generate_ddl", {"domains": ["subscriber", "cdr_event"]}
        )
        await self.handler(req)
        call_args = self.container.generate_ddl.execute.call_args[0][0]
        assert call_args.domains == ["subscriber", "cdr_event"]

    @pytest.mark.asyncio
    async def test_generate_full_pack_multiple_domains(self):
        req = _build_call_tool_request(
            "generate_full_pack",
            {"domains": ["subscriber", "revenue_invoice"], "vendor": "amdocs"},
        )
        await self.handler(req)
        call_args = self.container.generate_full_pack.execute.call_args[0][0]
        assert len(call_args.domains) == 2
