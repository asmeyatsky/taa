"""Partitioning domain service."""

from __future__ import annotations

from taa.domain.entities.table import Table
from taa.domain.value_objects.enums import TelcoDomain
from taa.domain.value_objects.types import PartitioningStrategy, ClusteringStrategy

# PRD-mandated partitioning strategies per domain
_DOMAIN_PARTITIONING: dict[TelcoDomain, PartitioningStrategy] = {
    TelcoDomain.CDR_EVENT: PartitioningStrategy(column_name="event_date", partition_type="DAY"),
    TelcoDomain.SUBSCRIBER: PartitioningStrategy(column_name="activation_date", partition_type="DAY"),
    TelcoDomain.REVENUE_INVOICE: PartitioningStrategy(column_name="bill_cycle_date", partition_type="MONTH"),
    TelcoDomain.PRODUCT_CATALOGUE: PartitioningStrategy(column_name="effective_date", partition_type="DAY"),
    TelcoDomain.INTERCONNECT_ROAMING: PartitioningStrategy(column_name="event_date", partition_type="DAY"),
    TelcoDomain.NETWORK_INVENTORY: PartitioningStrategy(column_name="snapshot_date", partition_type="DAY"),
    TelcoDomain.USAGE_ANALYTICS: PartitioningStrategy(column_name="usage_date", partition_type="DAY"),
}

_DOMAIN_CLUSTERING: dict[TelcoDomain, ClusteringStrategy] = {
    TelcoDomain.CDR_EVENT: ClusteringStrategy(column_names=("subscriber_id", "event_type")),
    TelcoDomain.SUBSCRIBER: ClusteringStrategy(column_names=("subscriber_id",)),
    TelcoDomain.REVENUE_INVOICE: ClusteringStrategy(column_names=("account_id", "invoice_type")),
    TelcoDomain.PRODUCT_CATALOGUE: ClusteringStrategy(column_names=("product_id",)),
    TelcoDomain.INTERCONNECT_ROAMING: ClusteringStrategy(column_names=("partner_operator", "direction")),
    TelcoDomain.NETWORK_INVENTORY: ClusteringStrategy(column_names=("element_type", "region")),
    TelcoDomain.USAGE_ANALYTICS: ClusteringStrategy(column_names=("subscriber_id", "service_type")),
}


class PartitioningService:
    """Applies PRD-mandated partitioning and clustering strategies to tables."""

    def apply_partitioning(self, table: Table) -> Table:
        """Apply domain-appropriate partitioning to a table."""
        if table.partitioning is not None:
            return table
        strategy = _DOMAIN_PARTITIONING.get(table.telco_domain)
        if strategy is None:
            return table
        return Table(
            name=table.name,
            telco_domain=table.telco_domain,
            columns=table.columns,
            partitioning=strategy,
            clustering=table.clustering,
            dataset_name=table.dataset_name,
        )

    def apply_clustering(self, table: Table) -> Table:
        """Apply domain-appropriate clustering to a table."""
        if table.clustering is not None:
            return table
        strategy = _DOMAIN_CLUSTERING.get(table.telco_domain)
        if strategy is None:
            return table
        return Table(
            name=table.name,
            telco_domain=table.telco_domain,
            columns=table.columns,
            partitioning=table.partitioning,
            clustering=strategy,
            dataset_name=table.dataset_name,
        )

    def apply_all(self, table: Table) -> Table:
        """Apply both partitioning and clustering strategies."""
        return self.apply_clustering(self.apply_partitioning(table))

    def get_partition_strategy(self, domain: TelcoDomain) -> PartitioningStrategy | None:
        """Get the partitioning strategy for a domain."""
        return _DOMAIN_PARTITIONING.get(domain)

    def get_clustering_strategy(self, domain: TelcoDomain) -> ClusteringStrategy | None:
        """Get the clustering strategy for a domain."""
        return _DOMAIN_CLUSTERING.get(domain)
