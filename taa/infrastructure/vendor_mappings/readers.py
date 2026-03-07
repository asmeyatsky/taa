"""Vendor schema readers - load YAML mapping files for each BSS vendor."""

from __future__ import annotations

from pathlib import Path

import yaml

from taa.domain.entities.vendor_mapping import VendorMapping
from taa.domain.value_objects.enums import BSSVendor, TelcoDomain


MAPPING_DATA_DIR = Path(__file__).parent / "mapping_data"


class VendorSchemaReader:
    """Generic vendor schema reader that loads YAML mapping files."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or MAPPING_DATA_DIR

    def load_mappings(self, vendor: BSSVendor, domain: TelcoDomain) -> tuple[VendorMapping, ...]:
        yaml_path = self._data_dir / f"{vendor.value}_{domain.value}.yaml"
        if not yaml_path.exists():
            return ()

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        mappings: list[VendorMapping] = []
        for m in data.get("mappings", []):
            mappings.append(VendorMapping(
                vendor=vendor,
                vendor_table=m["vendor_table"],
                vendor_field=m["vendor_field"],
                canonical_table=m["canonical_table"],
                canonical_field=m["canonical_field"],
                transformation=m.get("transformation", ""),
                confidence=m.get("confidence", 1.0),
            ))
        return tuple(mappings)

    def list_vendors(self) -> tuple[BSSVendor, ...]:
        vendors: set[BSSVendor] = set()
        for yaml_path in self._data_dir.glob("*.yaml"):
            vendor_name = yaml_path.stem.split("_")[0]
            # Handle multi-word vendor names
            for vendor in BSSVendor:
                if yaml_path.stem.startswith(vendor.value):
                    vendors.add(vendor)
                    break
        return tuple(sorted(vendors, key=lambda v: v.value))


# Convenience classes for each vendor
class AmdocsReader(VendorSchemaReader):
    """Amdocs BSS schema reader."""
    pass


class HuaweiCBSReader(VendorSchemaReader):
    """Huawei CBS schema reader."""
    pass


class OracleBRMReader(VendorSchemaReader):
    """Oracle BRM schema reader."""
    pass


class EricsonBSCSReader(VendorSchemaReader):
    """Ericsson BSCS schema reader."""
    pass
