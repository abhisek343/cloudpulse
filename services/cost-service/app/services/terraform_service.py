"""
CloudPulse AI - Cost Service
Terraform cost estimation service.

Parses `terraform plan -json` output and estimates monthly costs
using a built-in rate table for common cloud resources.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Monthly cost rates for common Terraform resource types.
# Rates are rough estimates (USD/month) for default / small configurations.
RATE_TABLE: dict[str, dict[str, Any]] = {
    # --- AWS ---
    "aws_instance": {
        "provider": "aws",
        "description": "EC2 Instance",
        "rates": {
            "t3.micro": 7.59, "t3.small": 15.18, "t3.medium": 30.37,
            "t3.large": 60.74, "t3.xlarge": 121.47,
            "m5.large": 69.12, "m5.xlarge": 138.24, "m5.2xlarge": 276.48,
            "c5.large": 62.05, "c5.xlarge": 124.10,
            "r5.large": 90.72, "r5.xlarge": 181.44,
        },
        "default_rate": 30.00,
        "size_key": "instance_type",
    },
    "aws_db_instance": {
        "provider": "aws",
        "description": "RDS Instance",
        "rates": {
            "db.t3.micro": 12.41, "db.t3.small": 24.82, "db.t3.medium": 49.64,
            "db.m5.large": 124.10, "db.m5.xlarge": 248.20,
            "db.r5.large": 172.80, "db.r5.xlarge": 345.60,
        },
        "default_rate": 50.00,
        "size_key": "instance_class",
    },
    "aws_lambda_function": {
        "provider": "aws",
        "description": "Lambda Function",
        "rates": {},
        "default_rate": 5.00,
        "size_key": None,
    },
    "aws_s3_bucket": {
        "provider": "aws",
        "description": "S3 Bucket",
        "rates": {},
        "default_rate": 2.30,
        "size_key": None,
    },
    "aws_nat_gateway": {
        "provider": "aws",
        "description": "NAT Gateway",
        "rates": {},
        "default_rate": 32.40,
        "size_key": None,
    },
    "aws_elasticache_cluster": {
        "provider": "aws",
        "description": "ElastiCache Cluster",
        "rates": {
            "cache.t3.micro": 11.52, "cache.t3.small": 23.04,
            "cache.m5.large": 110.59, "cache.r5.large": 163.58,
        },
        "default_rate": 23.00,
        "size_key": "node_type",
    },
    "aws_lb": {
        "provider": "aws",
        "description": "Load Balancer",
        "rates": {},
        "default_rate": 16.20,
        "size_key": None,
    },
    # --- Azure ---
    "azurerm_virtual_machine": {
        "provider": "azure",
        "description": "Azure VM",
        "rates": {
            "Standard_B1s": 7.59, "Standard_B2s": 30.37,
            "Standard_D2s_v3": 70.08, "Standard_D4s_v3": 140.16,
            "Standard_E2s_v3": 91.98, "Standard_F2s_v2": 61.32,
        },
        "default_rate": 70.00,
        "size_key": "vm_size",
    },
    "azurerm_linux_virtual_machine": {
        "provider": "azure",
        "description": "Azure Linux VM",
        "rates": {
            "Standard_B1s": 7.59, "Standard_B2s": 30.37,
            "Standard_D2s_v3": 70.08, "Standard_D4s_v3": 140.16,
        },
        "default_rate": 70.00,
        "size_key": "size",
    },
    "azurerm_managed_disk": {
        "provider": "azure",
        "description": "Managed Disk",
        "rates": {},
        "default_rate": 5.00,
        "size_key": None,
    },
    "azurerm_sql_database": {
        "provider": "azure",
        "description": "Azure SQL Database",
        "rates": {},
        "default_rate": 15.00,
        "size_key": None,
    },
    # --- GCP ---
    "google_compute_instance": {
        "provider": "gcp",
        "description": "GCP Compute Instance",
        "rates": {
            "e2-micro": 6.11, "e2-small": 12.23, "e2-medium": 24.46,
            "n1-standard-1": 24.27, "n1-standard-2": 48.55, "n1-standard-4": 97.09,
            "n2-standard-2": 56.52, "n2-standard-4": 113.04,
        },
        "default_rate": 25.00,
        "size_key": "machine_type",
    },
    "google_sql_database_instance": {
        "provider": "gcp",
        "description": "Cloud SQL Instance",
        "rates": {},
        "default_rate": 25.00,
        "size_key": None,
    },
    "google_storage_bucket": {
        "provider": "gcp",
        "description": "Cloud Storage Bucket",
        "rates": {},
        "default_rate": 2.30,
        "size_key": None,
    },
    "google_cloud_run_service": {
        "provider": "gcp",
        "description": "Cloud Run Service",
        "rates": {},
        "default_rate": 5.00,
        "size_key": None,
    },
}


def get_supported_resources() -> list[dict[str, str]]:
    """Return list of supported Terraform resource types with metadata."""
    result = []
    for resource_type, info in RATE_TABLE.items():
        result.append({
            "type": resource_type,
            "provider": info["provider"],
            "description": info["description"],
            "has_size_rates": bool(info.get("rates")),
        })
    return result


def _estimate_resource_cost(resource_type: str, values: dict) -> float | None:
    """Estimate monthly cost for a single resource given its planned values."""
    entry = RATE_TABLE.get(resource_type)
    if not entry:
        return None

    size_key = entry.get("size_key")
    if size_key and size_key in values:
        size_val = values[size_key]
        # For GCP machine_type, extract the suffix
        if "/" in str(size_val):
            size_val = size_val.rsplit("/", 1)[-1]
        rate = entry["rates"].get(size_val, entry["default_rate"])
    else:
        rate = entry["default_rate"]

    return round(float(rate), 2)


def estimate_plan(plan_json: dict) -> dict:
    """
    Estimate costs from a terraform plan JSON output.

    Expects the output of `terraform show -json <planfile>` which contains
    a `resource_changes` array.

    Returns a cost breakdown with per-resource estimates and totals.
    """
    resource_changes = plan_json.get("resource_changes", [])

    resources: list[dict] = []
    total_created = 0.0
    total_destroyed = 0.0
    unsupported: list[str] = []

    for rc in resource_changes:
        resource_type = rc.get("type", "")
        name = rc.get("name", "")
        address = rc.get("address", f"{resource_type}.{name}")
        change = rc.get("change", {})
        actions = change.get("actions", [])

        # Skip no-op
        if actions == ["no-op"]:
            continue

        after_values = change.get("after", {}) or {}
        before_values = change.get("before", {}) or {}

        after_cost = _estimate_resource_cost(resource_type, after_values)
        before_cost = _estimate_resource_cost(resource_type, before_values)

        is_supported = after_cost is not None or before_cost is not None
        if not is_supported:
            unsupported.append(address)

        entry: dict[str, Any] = {
            "address": address,
            "type": resource_type,
            "name": name,
            "action": "+".join(actions),
            "monthly_cost": None,
            "previous_cost": None,
        }

        if "create" in actions:
            cost = after_cost or 0.0
            entry["monthly_cost"] = cost
            entry["previous_cost"] = 0.0
            total_created += cost
        elif "delete" in actions:
            cost = before_cost or 0.0
            entry["monthly_cost"] = 0.0
            entry["previous_cost"] = cost
            total_destroyed += cost
        elif "update" in actions:
            new_cost = after_cost or 0.0
            old_cost = before_cost or 0.0
            entry["monthly_cost"] = new_cost
            entry["previous_cost"] = old_cost
            if new_cost > old_cost:
                total_created += new_cost - old_cost
            else:
                total_destroyed += old_cost - new_cost
        elif "create" in actions and "delete" in actions:
            # replace
            new_cost = after_cost or 0.0
            old_cost = before_cost or 0.0
            entry["monthly_cost"] = new_cost
            entry["previous_cost"] = old_cost
            total_created += new_cost
            total_destroyed += old_cost

        resources.append(entry)

    net_delta = round(total_created - total_destroyed, 2)

    return {
        "resources": resources,
        "summary": {
            "total_resources": len(resources),
            "estimated_monthly_increase": round(total_created, 2),
            "estimated_monthly_decrease": round(total_destroyed, 2),
            "net_monthly_delta": net_delta,
            "unsupported_count": len(unsupported),
        },
        "unsupported_resources": unsupported,
    }
