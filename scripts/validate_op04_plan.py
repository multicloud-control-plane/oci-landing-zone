#!/usr/bin/env python3
# Copyright (c) 2026 Oracle and/or its affiliates.
"""Block automated Vault and KMS destruction in every OP04 saved plan."""

import argparse
import json
from pathlib import Path


def validate_plan(plan):
    if (
        not isinstance(plan, dict)
        or not str(plan.get("format_version", "")).startswith("1.")
        or plan.get("errored") is True
        or plan.get("complete") is False
        or plan.get("deferred_changes")
        or not isinstance(plan.get("resource_changes", []), list)
    ):
        raise ValueError("Invalid Terraform plan JSON")
    for resource in plan.get("resource_changes", []):
        if resource.get("mode") != "managed":
            continue
        if resource.get("type") in {"oci_kms_vault", "oci_kms_key", "oci_kms_key_version"}:
            actions = resource.get("change", {}).get("actions")
            if not isinstance(actions, list) or not actions or any(
                action not in {"create", "read", "update", "no-op"} for action in actions
            ):
                raise ValueError(
                    "OP04 cannot delete, replace or forget Vault/KMS resources. "
                    "CloudOps must complete manual retirement before project teardown."
                )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    try:
        validate_plan(json.loads(args.plan.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
