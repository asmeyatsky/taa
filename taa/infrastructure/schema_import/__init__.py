"""Schema import/discovery module."""

from taa.infrastructure.schema_import.parser import SchemaParser, ImportedTable, ImportedColumn
from taa.infrastructure.schema_import.vendor_detector import VendorDetector
from taa.infrastructure.schema_import.mapping_suggester import MappingSuggester, SuggestedMapping
from taa.infrastructure.schema_import.gap_analyzer import GapAnalyzer, GapReport
from taa.infrastructure.schema_import.llm_mapper import LLMSchemaMapper, LLMMapperConfig
from taa.infrastructure.schema_import.bss_connector import BSSConnector, BSSConnectionConfig

__all__ = [
    "SchemaParser",
    "ImportedTable",
    "ImportedColumn",
    "VendorDetector",
    "MappingSuggester",
    "SuggestedMapping",
    "GapAnalyzer",
    "GapReport",
    "LLMSchemaMapper",
    "LLMMapperConfig",
    "BSSConnector",
    "BSSConnectionConfig",
]
