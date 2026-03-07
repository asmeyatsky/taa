"""Tests for schema import/discovery module."""

import pytest

from taa.infrastructure.schema_import import (
    SchemaParser,
    ImportedTable,
    ImportedColumn,
    VendorDetector,
    MappingSuggester,
    GapAnalyzer,
)
from taa.infrastructure.schema_import.llm_mapper import LLMSchemaMapper, LLMMapperConfig
from taa.domain.entities.column import Column
from taa.domain.entities.table import Table
from taa.domain.value_objects.enums import TelcoDomain, BigQueryType, BSSVendor


# --- Parser Tests ---

class TestSchemaParserDDL:
    def setup_method(self):
        self.parser = SchemaParser()

    def test_parse_simple_create_table(self):
        ddl = """
        CREATE TABLE CM_SUBSCRIBER (
            SUBSCRIBER_ID VARCHAR(50) NOT NULL,
            MSISDN VARCHAR(20),
            STATUS CHAR(1),
            ACTIVATION_DATE DATE NOT NULL
        );
        """
        tables = self.parser.parse(ddl, "ddl")
        assert len(tables) == 1
        assert tables[0].name == "CM_SUBSCRIBER"
        assert len(tables[0].columns) == 4
        assert tables[0].columns[0].name == "SUBSCRIBER_ID"
        assert tables[0].columns[0].nullable is False
        assert tables[0].columns[1].name == "MSISDN"
        assert tables[0].columns[1].nullable is True

    def test_parse_multiple_tables(self):
        ddl = """
        CREATE TABLE ACCOUNT_T (
            POID_ID0 NUMBER NOT NULL,
            ACCOUNT_NO VARCHAR2(100)
        );
        CREATE TABLE SERVICE_T (
            POID_ID0 NUMBER NOT NULL,
            LOGIN VARCHAR2(100)
        );
        """
        tables = self.parser.parse(ddl, "ddl")
        assert len(tables) == 2
        assert tables[0].name == "ACCOUNT_T"
        assert tables[1].name == "SERVICE_T"

    def test_parse_with_schema_prefix(self):
        ddl = "CREATE TABLE billing.INVOICE (invoice_id INT NOT NULL);"
        tables = self.parser.parse(ddl, "ddl")
        assert tables[0].name == "INVOICE"

    def test_parse_with_constraints(self):
        ddl = """
        CREATE TABLE test_table (
            id INT NOT NULL,
            name VARCHAR(100),
            PRIMARY KEY (id),
            UNIQUE (name)
        );
        """
        tables = self.parser.parse(ddl, "ddl")
        assert len(tables[0].columns) == 2

    def test_auto_detect_ddl(self):
        content = "CREATE TABLE foo (id INT);"
        tables = self.parser.parse(content, "auto")
        assert len(tables) == 1


class TestSchemaParserCSV:
    def setup_method(self):
        self.parser = SchemaParser()

    def test_parse_csv(self):
        csv_content = """table_name,column_name,data_type,nullable
CM_SUBSCRIBER,SUBSCRIBER_ID,VARCHAR,NO
CM_SUBSCRIBER,MSISDN,VARCHAR,YES
CM_ACCOUNT,ACCOUNT_ID,NUMBER,NO
"""
        tables = self.parser.parse(csv_content, "csv")
        assert len(tables) == 2
        sub = [t for t in tables if t.name == "CM_SUBSCRIBER"][0]
        assert len(sub.columns) == 2
        assert sub.columns[0].nullable is False
        assert sub.columns[1].nullable is True

    def test_auto_detect_csv(self):
        csv_content = """table_name,column_name,data_type
FOO,bar,INT
"""
        tables = self.parser.parse(csv_content, "auto")
        assert len(tables) == 1

    def test_csv_missing_headers(self):
        csv_content = "a,b,c\n1,2,3\n"
        with pytest.raises(ValueError, match="must have"):
            self.parser.parse(csv_content, "csv")


# --- Vendor Detector Tests ---

class TestVendorDetector:
    def setup_method(self):
        self.detector = VendorDetector()

    def test_detect_amdocs(self):
        tables = (
            ImportedTable(name="CM_SUBSCRIBER"),
            ImportedTable(name="CM_ACCOUNT"),
            ImportedTable(name="AR_INVOICE"),
            ImportedTable(name="PM_PRODUCT"),
        )
        result = self.detector.detect(tables)
        assert result.vendor == BSSVendor.AMDOCS
        assert result.confidence >= 0.5

    def test_detect_oracle_brm(self):
        tables = (
            ImportedTable(name="ACCOUNT_T"),
            ImportedTable(name="SERVICE_T"),
            ImportedTable(name="EVENT_T"),
            ImportedTable(name="BILL_T"),
        )
        result = self.detector.detect(tables)
        assert result.vendor == BSSVendor.ORACLE_BRM

    def test_detect_huawei(self):
        tables = (
            ImportedTable(name="CBS_SUBSCRIBER"),
            ImportedTable(name="CBS_ACCOUNT"),
            ImportedTable(name="CBS_CDR"),
        )
        result = self.detector.detect(tables)
        assert result.vendor == BSSVendor.HUAWEI_CBS

    def test_detect_ericsson(self):
        tables = (
            ImportedTable(name="CONTRACT_ALL"),
            ImportedTable(name="CUSTOMER_ALL"),
            ImportedTable(name="DIRECTORY_NUMBER"),
        )
        result = self.detector.detect(tables)
        assert result.vendor == BSSVendor.ERICSSON_BSCS

    def test_detect_unknown(self):
        tables = (
            ImportedTable(name="RANDOM_TABLE"),
            ImportedTable(name="ANOTHER_TABLE"),
        )
        result = self.detector.detect(tables)
        assert result.vendor is None
        assert result.confidence == 0.0

    def test_detect_empty(self):
        result = self.detector.detect(())
        assert result.vendor is None


# --- Mapping Suggester Tests ---

class TestMappingSuggester:
    def setup_method(self):
        self.suggester = MappingSuggester()
        self.canonical = (
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

    def test_exact_match(self):
        imported = (
            ImportedTable(
                name="CM_SUBSCRIBER",
                columns=(
                    ImportedColumn(name="subscriber_id"),
                    ImportedColumn(name="msisdn"),
                ),
            ),
        )
        suggestions = self.suggester.suggest(imported, self.canonical)
        assert len(suggestions) >= 2
        ids = [s for s in suggestions if s.vendor_field == "subscriber_id"]
        assert len(ids) == 1
        assert ids[0].canonical_field == "subscriber_id"
        assert ids[0].confidence >= 0.9

    def test_variant_match(self):
        imported = (
            ImportedTable(
                name="CBS_SUB",
                columns=(
                    ImportedColumn(name="SUB_ID"),
                    ImportedColumn(name="ACTIVATION_DT"),
                ),
            ),
        )
        suggestions = self.suggester.suggest(imported, self.canonical)
        # SUB_ID should match subscriber_id via abbreviation expansion
        # or ACTIVATION_DT should match activation_date
        assert len(suggestions) >= 1

    def test_no_match(self):
        imported = (
            ImportedTable(
                name="RANDOM",
                columns=(ImportedColumn(name="xyz_totally_random_field"),),
            ),
        )
        suggestions = self.suggester.suggest(imported, self.canonical)
        assert len(suggestions) == 0


# --- Gap Analyzer Tests ---

class TestGapAnalyzer:
    def test_analyze(self):
        from taa.infrastructure.schema_import.mapping_suggester import SuggestedMapping

        imported = (
            ImportedTable(
                name="SRC",
                columns=(
                    ImportedColumn(name="id"),
                    ImportedColumn(name="name"),
                    ImportedColumn(name="extra"),
                ),
            ),
        )
        canonical = (
            Table(
                name="target",
                telco_domain=TelcoDomain.SUBSCRIBER,
                columns=(
                    Column(name="id", bigquery_type=BigQueryType.STRING),
                    Column(name="name", bigquery_type=BigQueryType.STRING),
                    Column(name="status", bigquery_type=BigQueryType.STRING),
                ),
            ),
        )
        suggestions = (
            SuggestedMapping(
                vendor_table="SRC", vendor_field="id",
                canonical_table="target", canonical_field="id",
                confidence=0.95, match_reason="exact",
            ),
            SuggestedMapping(
                vendor_table="SRC", vendor_field="name",
                canonical_table="target", canonical_field="name",
                confidence=0.95, match_reason="exact",
            ),
        )

        analyzer = GapAnalyzer()
        report = analyzer.analyze(imported, canonical, suggestions)

        assert report.imported_tables == 1
        assert report.imported_columns == 3
        assert report.canonical_tables == 1
        assert report.canonical_columns == 3
        assert report.mapped_columns == 2
        assert report.mapping_coverage_pct == pytest.approx(66.7, abs=0.1)
        assert "SRC.extra" in report.unmapped_imported
        assert "target.status" in report.uncovered_canonical

    def test_report_markdown(self):
        from taa.infrastructure.schema_import.mapping_suggester import SuggestedMapping

        report = GapAnalyzer().analyze(
            imported_tables=(ImportedTable(name="T", columns=(ImportedColumn(name="a"),)),),
            canonical_tables=(Table(name="C", telco_domain=TelcoDomain.SUBSCRIBER,
                                   columns=(Column(name="a", bigquery_type=BigQueryType.STRING),)),),
            suggestions=(SuggestedMapping("T", "a", "C", "a", 0.95, "exact"),),
            vendor=BSSVendor.AMDOCS,
            vendor_confidence=0.8,
        )
        md = report.to_markdown()
        assert "# Schema Import Gap Analysis Report" in md
        assert "amdocs" in md
        assert "100.0%" in md


# --- LLM Mapper Tests ---

class TestLLMSchemaMapper:
    def test_parse_response_json_array(self):
        mapper = LLMSchemaMapper()
        response = """[
            {"vendor_table": "CM_SUB", "vendor_field": "MSISDN", "canonical_table": "subscriber_profile", "canonical_field": "msisdn", "confidence": 0.95, "transformation": "", "reason": "direct match"}
        ]"""
        suggestions = mapper._parse_response(response)
        assert len(suggestions) == 1
        assert suggestions[0].vendor_field == "MSISDN"
        assert suggestions[0].canonical_field == "msisdn"
        assert suggestions[0].confidence == 0.95

    def test_parse_response_code_block(self):
        mapper = LLMSchemaMapper()
        response = """```json
[{"vendor_table": "T1", "vendor_field": "F1", "canonical_table": "T2", "canonical_field": "F2", "confidence": 0.8, "reason": "test"}]
```"""
        suggestions = mapper._parse_response(response)
        assert len(suggestions) == 1

    def test_parse_response_invalid(self):
        mapper = LLMSchemaMapper()
        suggestions = mapper._parse_response("not json at all")
        assert suggestions == ()

    def test_build_prompt(self):
        mapper = LLMSchemaMapper()
        imported = (
            ImportedTable(name="T1", columns=(ImportedColumn(name="id", data_type="INT"),)),
        )
        canonical = (
            Table(name="T2", telco_domain=TelcoDomain.SUBSCRIBER,
                  columns=(Column(name="id", bigquery_type=BigQueryType.STRING),)),
        )
        prompt = mapper._build_prompt(imported, canonical)
        assert "SOURCE SCHEMA" in prompt
        assert "TARGET SCHEMA" in prompt
        assert "T1" in prompt
        assert "T2" in prompt

    def test_no_api_key_raises(self):
        import os
        old = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            mapper = LLMSchemaMapper(LLMMapperConfig(api_key=""))
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                mapper.suggest_mappings((), ())
        finally:
            if old:
                os.environ["ANTHROPIC_API_KEY"] = old


# --- BSS Connector Tests ---

class TestBSSConnector:
    def test_config_creation(self):
        from taa.infrastructure.schema_import.bss_connector import BSSConnectionConfig
        config = BSSConnectionConfig(
            host="db.example.com", port=1521, database="BSSDB",
            username="admin", password="secret", db_type="oracle",
        )
        assert config.host == "db.example.com"
        assert config.db_type == "oracle"

    def test_unsupported_db_type(self):
        from taa.infrastructure.schema_import.bss_connector import BSSConnector, BSSConnectionConfig
        config = BSSConnectionConfig(
            host="x", port=1, database="x", username="x", db_type="mongodb",
        )
        connector = BSSConnector(config)
        with pytest.raises(ValueError, match="Unsupported"):
            connector.introspect()

    def test_build_tables(self):
        from taa.infrastructure.schema_import.bss_connector import BSSConnector, BSSConnectionConfig
        config = BSSConnectionConfig(host="x", port=1, database="x", username="x")
        connector = BSSConnector(config)
        rows = [
            ("TABLE1", "COL_A", "VARCHAR2", "Y"),
            ("TABLE1", "COL_B", "NUMBER", "N"),
            ("TABLE2", "COL_C", "DATE", "Y"),
        ]
        tables = connector._build_tables(rows)
        assert len(tables) == 2
        t1 = [t for t in tables if t.name == "TABLE1"][0]
        assert len(t1.columns) == 2
        assert t1.columns[0].nullable is True
        assert t1.columns[1].nullable is False

    def test_connection_fails_without_driver(self):
        from taa.infrastructure.schema_import.bss_connector import BSSConnector, BSSConnectionConfig
        config = BSSConnectionConfig(
            host="nonexistent", port=1521, database="x", username="x", db_type="oracle",
        )
        connector = BSSConnector(config)
        # test_connection catches all exceptions and returns False
        assert connector.test_connection() is False
