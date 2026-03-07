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


@generate.command("analytics")
@click.option("--template", "-t", default=None, help="Specific template name (churn_prediction, revenue_leakage, arpu_analysis, network_quality, five_g_monetization)")
@click.option("--output", "-o", default="./output", type=click.Path(), help="Output directory")
@click.pass_context
def generate_analytics(ctx: click.Context, template: str | None, output: str) -> None:
    """Generate analytics SQL templates (BigQuery ML / Vertex AI)."""
    from taa.infrastructure.generators.analytics import AnalyticsTemplateGenerator
    container: Container = ctx.obj["container"]
    gen = AnalyticsTemplateGenerator(container.renderer)

    output_dir = Path(output) / "analytics"
    writer = container.output_writer

    if template:
        sql = gen.generate(template)
        path = output_dir / f"{template}.sql"
        writer.write(path, sql)
        click.echo(f"Generated: {path}")
    else:
        all_templates = gen.generate_all()
        for name, sql in all_templates.items():
            path = output_dir / f"{name}.sql"
            writer.write(path, sql)
            click.echo(f"Generated: {path}")
        click.echo(f"Success: Generated {len(all_templates)} analytics template(s)")


@generate.command("aws")
@click.option("--domains", "-d", required=True, help="Comma-separated domain names")
@click.option("--jurisdiction", "-j", default="SA", help="Jurisdiction code")
@click.option("--output", "-o", default="./output", type=click.Path(), help="Output directory")
@click.pass_context
def generate_aws(ctx: click.Context, domains: str, jurisdiction: str, output: str) -> None:
    """Generate AWS artefacts (Redshift DDL + CloudFormation)."""
    from taa.infrastructure.generators.multicloud_ddl import AWSRedshiftDDLGenerator, AWSCloudFormationGenerator
    container: Container = ctx.obj["container"]
    output_dir = Path(output)
    writer = container.output_writer
    files = []

    redshift_gen = AWSRedshiftDDLGenerator(container.renderer)
    cf_gen = AWSCloudFormationGenerator(container.renderer)

    from taa.domain.value_objects.enums import TelcoDomain
    from taa.application.commands.generate_terraform import JURISDICTIONS
    jurisdiction_obj = JURISDICTIONS.get(jurisdiction)
    datasets = []

    for domain_name in domains.split(","):
        domain = TelcoDomain(domain_name)
        tables = container.domain_repo.load_tables(domain)
        enriched = tuple(
            type(t)(name=t.name, telco_domain=t.telco_domain,
                   columns=container.pii_service.enrich_columns(t.columns),
                   partitioning=t.partitioning, clustering=t.clustering, dataset_name=t.dataset_name)
            for t in tables
        )
        enriched = tuple(container.partitioning_service.apply_all(t) for t in enriched)

        ddl = redshift_gen.generate(enriched, f"{domain.value}_ds")
        path = output_dir / "aws" / "redshift" / f"{domain.value}.sql"
        writer.write(path, ddl)
        files.append(str(path))

        ds = container.schema_service.build_dataset(f"{domain.value}_ds", domain, enriched, jurisdiction_obj)
        datasets.append(ds)

    if datasets:
        cf_files = cf_gen.generate(tuple(datasets))
        written = writer.write_multiple(cf_files, output_dir / "aws" / "cloudformation")
        files.extend(str(p) for p in written)

    click.echo(f"Success: Generated {len(files)} AWS file(s)")
    for f in files:
        click.echo(f"  {f}")


@generate.command("azure")
@click.option("--domains", "-d", required=True, help="Comma-separated domain names")
@click.option("--jurisdiction", "-j", default="SA", help="Jurisdiction code")
@click.option("--output", "-o", default="./output", type=click.Path(), help="Output directory")
@click.pass_context
def generate_azure(ctx: click.Context, domains: str, jurisdiction: str, output: str) -> None:
    """Generate Azure artefacts (Synapse DDL + Bicep)."""
    from taa.infrastructure.generators.multicloud_ddl import AzureSynapseDDLGenerator, AzureBicepGenerator
    container: Container = ctx.obj["container"]
    output_dir = Path(output)
    writer = container.output_writer
    files = []

    synapse_gen = AzureSynapseDDLGenerator(container.renderer)
    bicep_gen = AzureBicepGenerator(container.renderer)

    from taa.domain.value_objects.enums import TelcoDomain
    from taa.application.commands.generate_terraform import JURISDICTIONS
    jurisdiction_obj = JURISDICTIONS.get(jurisdiction)
    datasets = []

    for domain_name in domains.split(","):
        domain = TelcoDomain(domain_name)
        tables = container.domain_repo.load_tables(domain)
        enriched = tuple(
            type(t)(name=t.name, telco_domain=t.telco_domain,
                   columns=container.pii_service.enrich_columns(t.columns),
                   partitioning=t.partitioning, clustering=t.clustering, dataset_name=t.dataset_name)
            for t in tables
        )
        enriched = tuple(container.partitioning_service.apply_all(t) for t in enriched)

        ddl = synapse_gen.generate(enriched, f"{domain.value}_ds")
        path = output_dir / "azure" / "synapse" / f"{domain.value}.sql"
        writer.write(path, ddl)
        files.append(str(path))

        ds = container.schema_service.build_dataset(f"{domain.value}_ds", domain, enriched, jurisdiction_obj)
        datasets.append(ds)

    if datasets:
        bicep_files = bicep_gen.generate(tuple(datasets))
        written = writer.write_multiple(bicep_files, output_dir / "azure" / "bicep")
        files.extend(str(p) for p in written)

    click.echo(f"Success: Generated {len(files)} Azure file(s)")
    for f in files:
        click.echo(f"  {f}")


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


# --- Schema import commands ---

@cli.group()
def schema() -> None:
    """Schema import and discovery."""


@schema.command("import")
@click.argument("file", type=click.Path(exists=True))
@click.option("--format", "-f", "fmt", default="auto", type=click.Choice(["auto", "ddl", "csv"]),
              help="Input format")
@click.option("--domains", "-d", default=None, help="Comma-separated canonical domains to match against (default: all)")
@click.option("--output", "-o", default=None, type=click.Path(), help="Output file for gap report")
@click.pass_context
def schema_import(ctx: click.Context, file: str, fmt: str, domains: str | None, output: str | None) -> None:
    """Import an external schema (DDL or CSV) and auto-detect vendor, suggest mappings."""
    from taa.infrastructure.schema_import import SchemaParser, VendorDetector, MappingSuggester, GapAnalyzer
    from taa.domain.value_objects.enums import TelcoDomain

    container: Container = ctx.obj["container"]

    # Parse input
    parser = SchemaParser()
    imported = parser.parse_file(file)
    click.echo(f"Parsed {len(imported)} tables, {sum(len(t.columns) for t in imported)} columns")

    # Detect vendor
    detector = VendorDetector()
    detection = detector.detect(imported)
    if detection.vendor:
        click.echo(f"Detected vendor: {detection.vendor.value} (confidence: {detection.confidence:.0%})")
    else:
        click.echo("Could not auto-detect vendor")

    # Load canonical tables
    if domains:
        domain_list = [TelcoDomain(d) for d in domains.split(",")]
    else:
        domain_list = list(TelcoDomain)

    canonical: list = []
    for domain in domain_list:
        canonical.extend(container.domain_repo.load_tables(domain))
    canonical_tables = tuple(canonical)

    # Suggest mappings
    suggester = MappingSuggester()
    suggestions = suggester.suggest(imported, canonical_tables, detection.vendor)

    # Gap analysis
    analyzer = GapAnalyzer()
    report = analyzer.analyze(
        imported, canonical_tables, suggestions,
        vendor=detection.vendor, vendor_confidence=detection.confidence,
    )

    click.echo(f"Suggested {len(suggestions)} mappings")
    click.echo(f"Canonical coverage: {report.mapping_coverage_pct:.1f}%")
    click.echo(f"Import coverage: {report.import_coverage_pct:.1f}%")

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report.to_markdown())
        click.echo(f"Report written to: {output}")
    else:
        # Print top suggestions
        if suggestions:
            click.echo("\nTop mappings:")
            for s in sorted(suggestions, key=lambda x: -x.confidence)[:15]:
                click.echo(f"  {s.vendor_table}.{s.vendor_field} -> {s.canonical_table}.{s.canonical_field} ({s.confidence:.0%} {s.match_reason})")


@schema.command("connect")
@click.option("--host", required=True, help="Database host")
@click.option("--port", required=True, type=int, help="Database port")
@click.option("--database", required=True, help="Database name/SID")
@click.option("--username", required=True, help="Database username")
@click.option("--password", prompt=True, hide_input=True, help="Database password")
@click.option("--db-type", default="oracle", type=click.Choice(["oracle", "mysql", "postgresql", "mssql"]),
              help="Database type")
@click.option("--schema-filter", default="", help="Schema/owner filter")
@click.option("--domains", "-d", default=None, help="Comma-separated canonical domains")
@click.option("--output", "-o", default=None, type=click.Path(), help="Output file for gap report")
@click.pass_context
def schema_connect(ctx: click.Context, host: str, port: int, database: str,
                   username: str, password: str, db_type: str, schema_filter: str,
                   domains: str | None, output: str | None) -> None:
    """Connect to a live BSS database, introspect schema, and suggest mappings."""
    from taa.infrastructure.schema_import import (
        BSSConnector, BSSConnectionConfig, VendorDetector, MappingSuggester, GapAnalyzer,
    )
    from taa.domain.value_objects.enums import TelcoDomain

    container: Container = ctx.obj["container"]

    config = BSSConnectionConfig(
        host=host, port=port, database=database,
        username=username, password=password,
        db_type=db_type, schema_filter=schema_filter,
    )
    connector = BSSConnector(config)

    click.echo(f"Connecting to {db_type}://{host}:{port}/{database}...")
    if not connector.test_connection():
        click.secho("Connection failed. Check credentials and network.", fg="red")
        return

    click.echo("Connected. Introspecting schema...")
    imported = connector.introspect()
    click.echo(f"Found {len(imported)} tables, {sum(len(t.columns) for t in imported)} columns")

    # Detect vendor
    detector = VendorDetector()
    detection = detector.detect(imported)
    if detection.vendor:
        click.echo(f"Detected vendor: {detection.vendor.value} (confidence: {detection.confidence:.0%})")

    # Load canonical
    if domains:
        domain_list = [TelcoDomain(d) for d in domains.split(",")]
    else:
        domain_list = list(TelcoDomain)
    canonical = []
    for domain in domain_list:
        canonical.extend(container.domain_repo.load_tables(domain))

    # Suggest mappings
    suggester = MappingSuggester()
    suggestions = suggester.suggest(imported, tuple(canonical), detection.vendor)

    analyzer = GapAnalyzer()
    report = analyzer.analyze(
        imported, tuple(canonical), suggestions,
        vendor=detection.vendor, vendor_confidence=detection.confidence,
    )

    click.echo(f"Suggested {len(suggestions)} mappings (coverage: {report.mapping_coverage_pct:.1f}%)")

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report.to_markdown())
        click.echo(f"Report written to: {output}")
    else:
        for s in sorted(suggestions, key=lambda x: -x.confidence)[:15]:
            click.echo(f"  {s.vendor_table}.{s.vendor_field} -> {s.canonical_table}.{s.canonical_field} ({s.confidence:.0%})")


@schema.command("ai-map")
@click.argument("file", type=click.Path(exists=True))
@click.option("--provider", "-p", default="anthropic", type=click.Choice(["anthropic", "google"]),
              help="LLM provider")
@click.option("--model", "-m", default=None, help="Model name (default: claude-sonnet-4-20250514 / gemini-pro)")
@click.option("--domains", "-d", default=None, help="Comma-separated canonical domains")
@click.option("--output", "-o", default=None, type=click.Path(), help="Output file for mapping report")
@click.pass_context
def schema_ai_map(ctx: click.Context, file: str, provider: str, model: str | None,
                  domains: str | None, output: str | None) -> None:
    """Use AI (Claude/Gemini) to suggest schema mappings from a DDL or CSV file."""
    from taa.infrastructure.schema_import import (
        SchemaParser, LLMSchemaMapper, LLMMapperConfig, GapAnalyzer,
    )
    from taa.domain.value_objects.enums import TelcoDomain

    container: Container = ctx.obj["container"]

    parser = SchemaParser()
    imported = parser.parse_file(file)
    click.echo(f"Parsed {len(imported)} tables, {sum(len(t.columns) for t in imported)} columns")

    # Load canonical
    if domains:
        domain_list = [TelcoDomain(d) for d in domains.split(",")]
    else:
        domain_list = list(TelcoDomain)
    canonical = []
    for domain in domain_list:
        canonical.extend(container.domain_repo.load_tables(domain))
    canonical_tables = tuple(canonical)

    # Configure LLM
    default_model = "claude-sonnet-4-20250514" if provider == "anthropic" else "gemini-pro"
    config = LLMMapperConfig(provider=provider, model=model or default_model)
    mapper = LLMSchemaMapper(config)

    click.echo(f"Calling {provider} ({config.model})...")
    try:
        suggestions = mapper.suggest_mappings(imported, canonical_tables)
    except (ValueError, RuntimeError) as e:
        click.secho(f"Error: {e}", fg="red")
        return

    click.echo(f"AI suggested {len(suggestions)} mappings")

    analyzer = GapAnalyzer()
    report = analyzer.analyze(imported, canonical_tables, suggestions)

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report.to_markdown())
        click.echo(f"Report written to: {output}")
    else:
        for s in sorted(suggestions, key=lambda x: -x.confidence)[:20]:
            click.echo(f"  {s.vendor_table}.{s.vendor_field} -> {s.canonical_table}.{s.canonical_field} ({s.confidence:.0%} {s.match_reason})")


# --- Cost estimation commands ---

@cli.command("estimate")
@click.option("--domains", "-d", required=True, help="Comma-separated domain names")
@click.option("--subscribers", "-s", default=1_000_000, type=int, help="Subscriber count")
@click.option("--cdr-volume", "-c", default=500.0, type=float, help="Monthly CDR volume in GB")
@click.option("--cloud", default="gcp", type=click.Choice(["gcp", "aws", "azure"]), help="Cloud provider")
@click.option("--region", default="me-central1", help="Cloud region")
@click.option("--retention", default=24, type=int, help="Data retention in months")
@click.option("--output", "-o", default=None, type=click.Path(), help="Output file for cost report")
@click.pass_context
def estimate_cost(ctx: click.Context, domains: str, subscribers: int, cdr_volume: float,
                  cloud: str, region: str, retention: int, output: str | None) -> None:
    """Estimate cloud infrastructure costs for a TAA deployment."""
    from taa.infrastructure.cost_estimation import CostEstimator
    from taa.domain.value_objects.enums import TelcoDomain

    container: Container = ctx.obj["container"]

    all_tables = []
    for domain_name in domains.split(","):
        domain = TelcoDomain(domain_name)
        all_tables.extend(container.domain_repo.load_tables(domain))

    estimator = CostEstimator()
    estimate = estimator.estimate(
        tables=tuple(all_tables),
        subscriber_count=subscribers,
        monthly_cdr_volume_gb=cdr_volume,
        cloud_provider=cloud,
        region=region,
        retention_months=retention,
    )

    click.echo(f"\n{'='*60}")
    click.echo(f"  TAA Cost Estimate — {estimate.cloud_provider} ({estimate.region})")
    click.echo(f"{'='*60}")
    click.echo(f"  Subscribers: {estimate.subscriber_count:,}")
    click.echo(f"  Monthly CDR: {estimate.monthly_cdr_volume_gb:,.0f} GB")
    click.echo(f"{'='*60}")
    for b in estimate.breakdowns:
        click.echo(f"  {b.service:<25s} ${b.monthly_cost_usd:>10,.2f}/mo  ${b.annual_cost_usd:>12,.2f}/yr")
    click.echo(f"  {'─'*55}")
    click.echo(f"  {'TOTAL':<25s} ${estimate.total_monthly_usd:>10,.2f}/mo  ${estimate.total_annual_usd:>12,.2f}/yr")
    click.echo()

    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(estimate.to_markdown())
        click.echo(f"Report written to: {output}")


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
