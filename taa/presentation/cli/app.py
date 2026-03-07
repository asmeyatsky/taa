"""TAA CLI application."""

from __future__ import annotations

from pathlib import Path

import click

from taa import __version__
from taa.infrastructure.config.container import Container
from taa.application.dtos.models import GenerationRequest


@click.group()
@click.version_option(version=__version__, prog_name="taa")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """TAA - Telco Analytics Accelerator.

    Auto-generates production-ready BigQuery DDL, Terraform, Dataflow pipelines,
    Airflow DAGs, and compliance reports from telco BSS/OSS configurations.
    """
    ctx.ensure_object(dict)
    ctx.obj["container"] = Container()


# --- Domain commands ---

@cli.group()
def domain() -> None:
    """Manage telco domain models."""


@domain.command("list")
@click.pass_context
def domain_list(ctx: click.Context) -> None:
    """List all available telco domains."""
    container: Container = ctx.obj["container"]
    domains = container.list_domains.execute()
    for d in domains:
        click.echo(f"  {d.name} ({d.table_count} tables): {', '.join(d.tables)}")


@domain.command("show")
@click.argument("name")
@click.pass_context
def domain_show(ctx: click.Context, name: str) -> None:
    """Show details of a specific domain."""
    container: Container = ctx.obj["container"]
    info = container.get_domain_model.execute(name)
    click.echo(f"Domain: {info.name}")
    click.echo(f"Tables ({info.table_count}):")
    for t in info.tables:
        click.echo(f"  - {t}")


# --- Vendor commands ---

@cli.group()
def vendor() -> None:
    """Manage BSS vendor mappings."""


@vendor.command("list")
@click.pass_context
def vendor_list(ctx: click.Context) -> None:
    """List all supported BSS vendors."""
    container: Container = ctx.obj["container"]
    vendors = container.list_vendors.execute()
    for v in vendors:
        click.echo(f"  {v.name}")


@vendor.command("map")
@click.argument("vendor_name")
@click.argument("domain_name")
@click.pass_context
def vendor_map(ctx: click.Context, vendor_name: str, domain_name: str) -> None:
    """Show vendor-to-canonical mapping coverage."""
    container: Container = ctx.obj["container"]
    result = container.map_vendor_schema.execute(vendor_name, domain_name)
    click.echo(f"Vendor: {result.vendor}")
    click.echo(f"Domain: {result.domain}")
    click.echo(f"Coverage: {result.coverage_pct:.1f}% ({result.mapped_fields}/{result.total_fields})")
    if result.unmapped_fields:
        click.echo(f"Unmapped: {', '.join(result.unmapped_fields[:10])}")
    if result.conflicts:
        click.echo(f"Conflicts: {result.conflicts}")


# --- Jurisdiction commands ---

@cli.group()
def jurisdiction() -> None:
    """Manage compliance jurisdictions."""


@jurisdiction.command("list")
@click.pass_context
def jurisdiction_list(ctx: click.Context) -> None:
    """List all supported jurisdictions."""
    container: Container = ctx.obj["container"]
    jurisdictions = container.list_jurisdictions.execute()
    for j in jurisdictions:
        residency = " [data residency]" if j.data_residency_required else ""
        click.echo(f"  {j.code} - {j.name} ({j.framework}, {j.gcp_region}){residency}")


# --- Generate commands ---

@cli.group()
def generate() -> None:
    """Generate artefacts (DDL, Terraform, pipelines, DAGs, compliance)."""


@generate.command("ddl")
@click.option("--domains", "-d", required=True, help="Comma-separated domain names")
@click.option("--jurisdiction", "-j", default="SA", help="Jurisdiction code")
@click.option("--output", "-o", default="./output", type=click.Path(), help="Output directory")
@click.pass_context
def generate_ddl(ctx: click.Context, domains: str, jurisdiction: str, output: str) -> None:
    """Generate BigQuery DDL statements."""
    container: Container = ctx.obj["container"]
    request = GenerationRequest(
        domains=domains.split(","),
        jurisdiction=jurisdiction,
        output_dir=Path(output),
    )
    result = container.generate_ddl.execute(request)
    _print_result(result)


@generate.command("terraform")
@click.option("--domains", "-d", required=True, help="Comma-separated domain names")
@click.option("--jurisdiction", "-j", default="SA", help="Jurisdiction code")
@click.option("--output", "-o", default="./output", type=click.Path(), help="Output directory")
@click.pass_context
def generate_terraform(ctx: click.Context, domains: str, jurisdiction: str, output: str) -> None:
    """Generate Terraform configuration."""
    container: Container = ctx.obj["container"]
    request = GenerationRequest(
        domains=domains.split(","),
        jurisdiction=jurisdiction,
        output_dir=Path(output),
    )
    result = container.generate_terraform.execute(request)
    _print_result(result)


@generate.command("pipeline")
@click.option("--domains", "-d", required=True, help="Comma-separated domain names")
@click.option("--vendor", "-v", default=None, help="BSS vendor name")
@click.option("--output", "-o", default="./output", type=click.Path(), help="Output directory")
@click.pass_context
def generate_pipeline(ctx: click.Context, domains: str, vendor: str | None, output: str) -> None:
    """Generate Dataflow pipeline code."""
    container: Container = ctx.obj["container"]
    request = GenerationRequest(
        domains=domains.split(","),
        vendor=vendor,
        output_dir=Path(output),
    )
    result = container.generate_pipeline.execute(request)
    _print_result(result)


@generate.command("dag")
@click.option("--domains", "-d", required=True, help="Comma-separated domain names")
@click.option("--output", "-o", default="./output", type=click.Path(), help="Output directory")
@click.pass_context
def generate_dag(ctx: click.Context, domains: str, output: str) -> None:
    """Generate Airflow DAG code."""
    container: Container = ctx.obj["container"]
    request = GenerationRequest(
        domains=domains.split(","),
        output_dir=Path(output),
    )
    result = container.generate_dag.execute(request)
    _print_result(result)


@generate.command("compliance")
@click.option("--domains", "-d", required=True, help="Comma-separated domain names")
@click.option("--jurisdiction", "-j", default="SA", help="Jurisdiction code")
@click.option("--output", "-o", default="./output", type=click.Path(), help="Output directory")
@click.pass_context
def generate_compliance(ctx: click.Context, domains: str, jurisdiction: str, output: str) -> None:
    """Generate compliance reports."""
    container: Container = ctx.obj["container"]
    request = GenerationRequest(
        domains=domains.split(","),
        jurisdiction=jurisdiction,
        output_dir=Path(output),
    )
    result = container.generate_compliance.execute(request)
    _print_result(result)


@generate.command("pack")
@click.option("--domains", "-d", required=True, help="Comma-separated domain names")
@click.option("--jurisdiction", "-j", default="SA", help="Jurisdiction code")
@click.option("--vendor", "-v", default=None, help="BSS vendor name")
@click.option("--output", "-o", default="./output", type=click.Path(), help="Output directory")
@click.pass_context
def generate_pack(ctx: click.Context, domains: str, jurisdiction: str, vendor: str | None, output: str) -> None:
    """Generate full artefact pack (DDL + Terraform + pipelines + DAGs + compliance)."""
    container: Container = ctx.obj["container"]
    request = GenerationRequest(
        domains=domains.split(","),
        jurisdiction=jurisdiction,
        vendor=vendor,
        output_dir=Path(output),
    )
    result = container.generate_full_pack.execute(request)
    _print_result(result)


# --- MCP commands ---

@cli.group()
def mcp() -> None:
    """MCP server management."""


@mcp.command("serve")
@click.option("--host", default="localhost", help="Host to bind to")
@click.option("--port", default=8080, type=int, help="Port to bind to")
def mcp_serve(host: str, port: int) -> None:
    """Start the TAA MCP server."""
    click.echo(f"Starting TAA MCP server on {host}:{port}...")
    from taa.infrastructure.mcp_servers.server import create_server
    server = create_server()
    import asyncio
    asyncio.run(server.run_stdio())


def _print_result(result) -> None:
    """Print a GenerationResult to the console."""
    if result.success:
        click.echo(f"Success: {result.summary}")
    else:
        click.echo(f"Completed with errors: {result.summary}")

    if result.files_generated:
        click.echo(f"Files generated ({len(result.files_generated)}):")
        for f in result.files_generated:
            click.echo(f"  {f}")

    for err in result.errors:
        click.secho(f"  ERROR: {err}", fg="red")

    for warn in result.warnings:
        click.secho(f"  WARNING: {warn}", fg="yellow")
