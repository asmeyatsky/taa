"""VendorMapping entity."""

from __future__ import annotations

from dataclasses import dataclass

from taa.domain.value_objects.enums import BSSVendor


@dataclass(frozen=True)
class VendorMapping:
    """Maps a vendor BSS field to a canonical TAA field."""

    vendor: BSSVendor
    vendor_table: str
    vendor_field: str
    canonical_table: str
    canonical_field: str
    transformation: str = ""
    confidence: float = 1.0
