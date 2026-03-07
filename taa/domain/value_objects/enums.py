"""TAA domain enumerations."""

from enum import Enum


class TelcoDomain(str, Enum):
    """7 telco analytics domains."""
    SUBSCRIBER = "subscriber"
    PRODUCT_CATALOGUE = "product_catalogue"
    CDR_EVENT = "cdr_event"
    REVENUE_INVOICE = "revenue_invoice"
    INTERCONNECT_ROAMING = "interconnect_roaming"
    NETWORK_INVENTORY = "network_inventory"
    USAGE_ANALYTICS = "usage_analytics"


class BSSVendor(str, Enum):
    """4 supported BSS vendor platforms."""
    AMDOCS = "amdocs"
    HUAWEI_CBS = "huawei_cbs"
    ORACLE_BRM = "oracle_brm"
    ERICSSON_BSCS = "ericsson_bscs"


class PIICategory(str, Enum):
    """10 PII categories for telco data."""
    MSISDN = "msisdn"
    IMSI = "imsi"
    IMEI = "imei"
    EMAIL = "email"
    NATIONAL_ID = "national_id"
    NAME = "name"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    IP_ADDRESS = "ip_address"
    LOCATION = "location"


class BigQueryType(str, Enum):
    """BigQuery column data types."""
    STRING = "STRING"
    INT64 = "INT64"
    FLOAT64 = "FLOAT64"
    NUMERIC = "NUMERIC"
    BIGNUMERIC = "BIGNUMERIC"
    BOOLEAN = "BOOL"
    BYTES = "BYTES"
    DATE = "DATE"
    DATETIME = "DATETIME"
    TIMESTAMP = "TIMESTAMP"
    TIME = "TIME"
    GEOGRAPHY = "GEOGRAPHY"
    JSON = "JSON"
    STRUCT = "STRUCT"


class PipelineMode(str, Enum):
    """Dataflow pipeline execution modes."""
    BATCH = "batch"
    STREAMING = "streaming"


class PipelineType(str, Enum):
    """Dataflow pipeline types."""
    BATCH_INGESTION = "batch_ingestion"
    CDR_MEDIATION = "cdr_mediation"
    CDC = "cdc"
    TAP_RAP = "tap_rap"
    REVENUE_ASSURANCE = "revenue_assurance"


class TemplateType(str, Enum):
    """Analytics template types."""
    CHURN_PREDICTION = "churn_prediction"
    REVENUE_ASSURANCE = "revenue_assurance"
    NETWORK_QUALITY = "network_quality"
    ARPU_ANALYSIS = "arpu_analysis"
    INTERCONNECT_SETTLEMENT = "interconnect_settlement"
