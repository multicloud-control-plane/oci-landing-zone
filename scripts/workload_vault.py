"""Protected shared workload Vault reference; no cloud calls or state ownership."""
import json
import re
from pathlib import Path


def validate_workload_vault(blueprint):
    if blueprint.get("schema_version") != 3:
        raise ValueError("Blueprint 3 is required; legacy contracts are unsupported.")
    environment, region = blueprint.get("environment"), blueprint.get("region")
    vault = blueprint.get("security", {}).get("workload_vault")
    security = blueprint.get("compartments", {}).get("security", {})
    if (not isinstance(vault, dict) or set(vault) != {"key", "ocid"}
        or vault["key"] != f"VLT-LZ-{str(environment).upper()}-WORKLOADS-KEY"
        or not re.fullmatch(r"ocid1\.compartment\.oc1\.\.[A-Za-z0-9_.-]+", str(security.get("ocid", "")))
        or security.get("key") != f"CMP-LZ-{str(environment).upper()}-SECURITY-KEY"):
        raise ValueError("The protected blueprint requires one authorized workload Vault in environment security.")
    match = re.fullmatch(r"ocid1\.vault\.oc1\.([a-z0-9-]+)\.[A-Za-z0-9_.-]+", str(vault["ocid"]))
    aliases = json.loads(Path(__file__).with_name("oci-region-codes.json").read_text())
    if match is None or aliases.get(match[1], match[1]) != region:
        raise ValueError("The workload Vault must belong to the blueprint OCI region.")
    return vault
