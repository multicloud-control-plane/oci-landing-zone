#!/usr/bin/env python3
# Copyright (c) 2026 Oracle and/or its affiliates.
"""Publish resource actions only; Terraform plan values remain on the runner."""

import json
import re
import sys

from validate_op04_plan import validate_plan


def has_unknown(value) -> bool:
    if isinstance(value, dict):
        return any(has_unknown(item) for item in value.values())
    if isinstance(value, list):
        return any(has_unknown(item) for item in value)
    return value is True


def changed_attributes(change: dict) -> list[str]:
    before = change.get("before") or {}
    after = change.get("after") or {}
    unknown = change.get("after_unknown") or {}
    if not all(isinstance(value, dict) for value in (before, after, unknown)):
        raise ValueError("Invalid resource attribute maps")
    changed = {
        key for key in set(before) | set(after) | set(unknown)
        if before.get(key) != after.get(key) or has_unknown(unknown.get(key))
    }
    # Only schema-level names are useful for review. Nested map keys and all
    # values stay private, including sensitive fields and tag contents.
    return sorted({
        key if re.fullmatch(r"[a-z][a-z0-9_]*", key) else "[attribute name omitted]"
        for key in changed
    })


def main() -> int:
    try:
        plan = json.load(sys.stdin)
        validate_plan(plan)
        changes = plan.get("resource_changes", [])
        lines = []
        totals = {"create": 0, "update": 0, "delete": 0, "replace": 0}
        for resource in changes:
            if resource.get("mode") == "data":
                continue
            actions = resource["change"]["actions"]
            if actions == ["no-op"]:
                continue
            if actions not in [["create"], ["read"], ["update"], ["delete"], ["delete", "create"], ["create", "delete"]]:
                raise ValueError("Unsupported resource action")
            for action in ("create", "update", "delete"):
                totals[action] += action in actions
            totals["replace"] += "create" in actions and "delete" in actions
            # Resource keys are project-controlled: omit unsafe addresses rather
            # than allowing Markdown or workflow-command injection into reports.
            address = resource["address"]
            if not isinstance(address, str) or not re.fullmatch(r'[A-Za-z0-9_.\[\]"/-]+', address):
                address = "[resource address omitted]"
            lines.append(f"{', '.join(actions)}: {address}")
            if "update" in actions:
                attributes = changed_attributes(resource["change"])
                if attributes:
                    lines.append(f"  changed attributes: {', '.join(attributes)}")
        print(f"Plan: {totals['create']} to add, {totals['update']} to change, "
              f"{totals['delete']} to destroy; {totals['replace']} replacement(s).")
        print("Replacement adds and destroys are included in the totals. Counts include local Terraform resources.")
        print("\n".join(lines) if lines else "No managed resource changes.")
        print("Values and data-source contents are omitted. Review the manifest diff with this action summary.")
    except (ValueError, TypeError, KeyError, AttributeError):
        print("Cannot produce a safe Terraform action summary.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
