"""Vendor detector — identifies BSS vendor from table naming patterns."""

from __future__ import annotations

from dataclasses import dataclass

from taa.domain.value_objects.enums import BSSVendor
from taa.infrastructure.schema_import.parser import ImportedTable


@dataclass(frozen=True)
class VendorDetection:
    """Result of vendor auto-detection."""

    vendor: BSSVendor | None
    confidence: float
    matched_patterns: tuple[str, ...]
    table_count: int


# Vendor-specific naming patterns (prefix → vendor)
_VENDOR_PATTERNS: dict[BSSVendor, list[str]] = {
    BSSVendor.AMDOCS: [
        "CM_",        # Customer Management
        "PM_",        # Product Management
        "AR_",        # Accounts Receivable
        "CDR_",       # Call Detail Records (Amdocs convention)
        "OM_",        # Order Management
        "BM_",        # Billing Management
        "IC_",        # Interconnect
    ],
    BSSVendor.HUAWEI_CBS: [
        "CBS_",       # Convergent Billing System
        "OCS_",       # Online Charging System
        "CBSS_",      # CBS Subscriber
    ],
    BSSVendor.ORACLE_BRM: [
        "_T",         # Oracle BRM table suffix convention
        "ACCOUNT_T",
        "SERVICE_T",
        "EVENT_T",
        "BILL_T",
        "ITEM_T",
        "BAL_GRP_T",
        "SUB_BAL_T",
        "NAMEINFO_T",
        "PAYINFO_T",
        "PROFILE_T",
        "DEVICE_T",
    ],
    BSSVendor.ERICSSON_BSCS: [
        "_ALL",       # Ericsson BSCS suffix convention
        "CONTRACT_ALL",
        "CUSTOMER_ALL",
        "BILLIMAGE_ALL",
        "ORDERHDR_ALL",
        "PAYMENT_ALL",
        "CCONTACT_ALL",
        "DIRECTORY_NUMBER",
        "ADDRESS_ALL",
        "RATEPLAN",
        "MPULKTGR",
        "UDR_ALL",
        "BILLCYCLE",
    ],
}


class VendorDetector:
    """Auto-detects BSS vendor from table naming patterns."""

    def detect(self, tables: tuple[ImportedTable, ...]) -> VendorDetection:
        """Analyze table names and return best vendor match."""
        if not tables:
            return VendorDetection(vendor=None, confidence=0.0, matched_patterns=(), table_count=0)

        table_names = [t.name.upper() for t in tables]
        scores: dict[BSSVendor, list[str]] = {}

        for vendor, patterns in _VENDOR_PATTERNS.items():
            matched: list[str] = []
            for table_name in table_names:
                for pattern in patterns:
                    pattern_upper = pattern.upper()
                    # Check exact match for full table names
                    if table_name == pattern_upper:
                        matched.append(f"{table_name}={pattern}")
                        break
                    # Check prefix match
                    if not pattern_upper.startswith("_") and table_name.startswith(pattern_upper):
                        matched.append(f"{table_name} starts with {pattern}")
                        break
                    # Check suffix match (for _T, _ALL patterns)
                    if pattern_upper.startswith("_") and table_name.endswith(pattern_upper):
                        matched.append(f"{table_name} ends with {pattern}")
                        break
            scores[vendor] = matched

        # Find best match
        best_vendor: BSSVendor | None = None
        best_count = 0
        best_matched: list[str] = []

        for vendor, matched in scores.items():
            if len(matched) > best_count:
                best_count = len(matched)
                best_vendor = vendor
                best_matched = matched

        if best_vendor is None or best_count == 0:
            return VendorDetection(vendor=None, confidence=0.0, matched_patterns=(), table_count=len(tables))

        confidence = min(best_count / len(tables), 1.0)
        return VendorDetection(
            vendor=best_vendor,
            confidence=round(confidence, 2),
            matched_patterns=tuple(best_matched),
            table_count=len(tables),
        )
