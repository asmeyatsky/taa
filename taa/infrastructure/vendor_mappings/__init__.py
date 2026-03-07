"""Vendor mapping readers."""

from taa.infrastructure.vendor_mappings.readers import (
    VendorSchemaReader,
    AmdocsReader,
    HuaweiCBSReader,
    OracleBRMReader,
    EricsonBSCSReader,
)

__all__ = [
    "VendorSchemaReader",
    "AmdocsReader",
    "HuaweiCBSReader",
    "OracleBRMReader",
    "EricsonBSCSReader",
]
