#!/usr/bin/env python3
"""Bind a reviewed workload declaration to this foundation reference export."""
import json
import os
from pathlib import Path
import re
import sys


def prepare(settings, revision, tenancy, region):
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("A full foundation revision is required")
    if settings.get("enabled") is not True:
        raise ValueError("The reviewed workload declaration is disabled")
    if (settings.get("foundation_repository") != "multicloud-control-plane/oci-landing-zone"
            or settings.get("tenancy_ocid") != tenancy or settings.get("region") != region):
        raise ValueError("Workload scope differs from this foundation")
    if settings.get("foundation_revision") not in (None, revision):
        raise ValueError("An explicit snapshot must match this foundation export")
    return {**settings, "foundation_revision": revision}


if __name__ == "__main__":
    result = prepare(json.loads(Path(sys.argv[1]).read_text()), os.environ["GITHUB_SHA"],
                     os.environ["OCI_TENANCY_OCID"], os.environ["REGION"])
    Path(sys.argv[2]).write_text(json.dumps(result))
