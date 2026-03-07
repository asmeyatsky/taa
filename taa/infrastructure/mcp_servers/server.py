"""TAA MCP Server implementation."""

from __future__ import annotations

import json
from typing import Any

from taa.infrastructure.config.container import Container
from taa.application.dtos.models import GenerationRequest
from taa.domain.value_objects.enums import TelcoDomain, BSSVendor, PIICategory


def create_server():
    """Create and configure the TAA MCP server."""
    try:
        from mcp.server import Server
        from mcp.types import Tool, Resource, TextContent
    except ImportError:
        raise ImportError("mcp package required. Install with: pip install mcp")

    server = Server("taa")
    container = Container()

    # --- Tools ---

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(name="generate_ddl", description="Generate BigQuery DDL for telco domains",
                 inputSchema={"type": "object", "properties": {
                     "domains": {"type": "array", "items": {"type": "string"}},
                     "jurisdiction": {"type": "string", "default": "SA"},
                 }, "required": ["domains"]}),
            Tool(name="generate_terraform", description="Generate Terraform configuration",
                 inputSchema={"type": "object", "properties": {
                     "domains": {"type": "array", "items": {"type": "string"}},
                     "jurisdiction": {"type": "string", "default": "SA"},
                 }, "required": ["domains"]}),
            Tool(name="generate_pipeline", description="Generate Dataflow pipeline code",
                 inputSchema={"type": "object", "properties": {
                     "domains": {"type": "array", "items": {"type": "string"}},
                     "vendor": {"type": "string"},
                 }, "required": ["domains"]}),
            Tool(name="generate_dag", description="Generate Airflow DAG code",
                 inputSchema={"type": "object", "properties": {
                     "domains": {"type": "array", "items": {"type": "string"}},
                 }, "required": ["domains"]}),
            Tool(name="generate_compliance_report", description="Generate compliance report",
                 inputSchema={"type": "object", "properties": {
                     "domains": {"type": "array", "items": {"type": "string"}},
                     "jurisdiction": {"type": "string", "default": "SA"},
                 }, "required": ["domains"]}),
            Tool(name="generate_full_pack", description="Generate complete artefact pack",
                 inputSchema={"type": "object", "properties": {
                     "domains": {"type": "array", "items": {"type": "string"}},
                     "jurisdiction": {"type": "string", "default": "SA"},
                     "vendor": {"type": "string"},
                 }, "required": ["domains"]}),
            Tool(name="map_vendor_schema", description="Map vendor schema to canonical model",
                 inputSchema={"type": "object", "properties": {
                     "vendor": {"type": "string"},
                     "domain": {"type": "string"},
                 }, "required": ["vendor", "domain"]}),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "generate_ddl":
            request = GenerationRequest(domains=arguments["domains"],
                                       jurisdiction=arguments.get("jurisdiction", "SA"))
            result = container.generate_ddl.execute(request)
        elif name == "generate_terraform":
            request = GenerationRequest(domains=arguments["domains"],
                                       jurisdiction=arguments.get("jurisdiction", "SA"))
            result = container.generate_terraform.execute(request)
        elif name == "generate_pipeline":
            request = GenerationRequest(domains=arguments["domains"],
                                       vendor=arguments.get("vendor"))
            result = container.generate_pipeline.execute(request)
        elif name == "generate_dag":
            request = GenerationRequest(domains=arguments["domains"])
            result = container.generate_dag.execute(request)
        elif name == "generate_compliance_report":
            request = GenerationRequest(domains=arguments["domains"],
                                       jurisdiction=arguments.get("jurisdiction", "SA"))
            result = container.generate_compliance.execute(request)
        elif name == "generate_full_pack":
            request = GenerationRequest(domains=arguments["domains"],
                                       jurisdiction=arguments.get("jurisdiction", "SA"),
                                       vendor=arguments.get("vendor"))
            result = container.generate_full_pack.execute(request)
        elif name == "map_vendor_schema":
            mapping_result = container.map_vendor_schema.execute(
                arguments["vendor"], arguments["domain"])
            return [TextContent(type="text", text=mapping_result.model_dump_json(indent=2))]
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [TextContent(type="text", text=result.model_dump_json(indent=2))]

    # --- Resources ---

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(uri="taa://domains", name="Telco Domains",
                    description="List of all telco analytics domains"),
            Resource(uri="taa://vendors", name="BSS Vendors",
                    description="List of supported BSS vendors"),
            Resource(uri="taa://jurisdictions", name="Jurisdictions",
                    description="List of supported compliance jurisdictions"),
            Resource(uri="taa://pii-categories", name="PII Categories",
                    description="List of PII data categories"),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        uri = str(uri)
        if uri == "taa://domains":
            domains = container.list_domains.execute()
            return json.dumps([d.model_dump() for d in domains], indent=2)
        elif uri == "taa://vendors":
            vendors = container.list_vendors.execute()
            return json.dumps([v.model_dump() for v in vendors], indent=2)
        elif uri == "taa://jurisdictions":
            jurisdictions = container.list_jurisdictions.execute()
            return json.dumps([j.model_dump() for j in jurisdictions], indent=2)
        elif uri == "taa://pii-categories":
            categories = [{"name": c.value, "description": c.name} for c in PIICategory]
            return json.dumps(categories, indent=2)
        elif uri.startswith("taa://domains/"):
            domain_name = uri.split("/")[-1]
            info = container.get_domain_model.execute(domain_name)
            return info.model_dump_json(indent=2)
        elif uri.startswith("taa://vendors/") and "/mappings/" in uri:
            parts = uri.replace("taa://vendors/", "").split("/mappings/")
            result = container.map_vendor_schema.execute(parts[0], parts[1])
            return result.model_dump_json(indent=2)
        elif uri.startswith("taa://jurisdictions/") and "/rules" in uri:
            jcode = uri.replace("taa://jurisdictions/", "").replace("/rules", "")
            rules = container.compliance_rule_repo.load_rules(jcode)
            return json.dumps([{
                "rule_id": r.rule_id, "framework": r.framework,
                "data_residency_required": r.data_residency_required,
                "encryption_required": r.encryption_required,
            } for r in rules], indent=2)
        return json.dumps({"error": f"Unknown resource: {uri}"})

    return server
