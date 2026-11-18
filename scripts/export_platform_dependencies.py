#!/usr/bin/env python3
"""Publish only official reference artifacts; raw foundation state stays private."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def extract(state):
    result = {}
    for name, root in (("compartments_output", "compartments"), ("network_output", "network_resources")):
        matches = [i["attributes"]["content"] for r in state.get("resources", []) if r.get("type") == "local_file" and r.get("name") == name and not r.get("module") for i in r.get("instances", [])]
        if len(matches) != 1:
            raise ValueError("Expected exactly one official " + name)
        value = json.loads(matches[0])
        if set(value) != {root} or not isinstance(value[root], dict):
            raise ValueError("Unexpected dependency document")
        maps = [value[root]] if root == "compartments" else list(value[root].values())
        for entries in maps:
            if not isinstance(entries, dict):
                raise ValueError("Expected dependency map")
            for reference in entries.values():
                if not isinstance(reference, dict) or set(reference) - {"id", "region_name"} or not isinstance(reference.get("id"), str) or not reference["id"].startswith("ocid1."):
                    raise ValueError("Dependency artifacts may contain only OCI references and region names")
        result[name + ".json"] = value
    return result


def command(args, cwd):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise ValueError("Foundation state read failed; no state or unrestricted diagnostics published")
    return result.stdout


def main():
    values = {}
    for name in ("GITHUB_REPOSITORY", "GITHUB_SHA", "OCI_TENANCY_OCID", "REGION", "OCI_TF_STATE_NAMESPACE", "OCI_TF_STATE_BUCKET"):
        if not os.environ.get(name):
            raise ValueError("Missing configuration: " + name)
        values[name] = os.environ[name]
    if values["GITHUB_REPOSITORY"] != "multicloud-control-plane/oci-landing-zone" or not re.fullmatch(r"[a-f0-9]{40}", values["GITHUB_SHA"]):
        raise ValueError("Unexpected snapshot publisher")
    import oci
    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    if signer.tenancy_id != values["OCI_TENANCY_OCID"]:
        raise ValueError("Runner tenancy mismatch")
    storage = oci.object_storage.ObjectStorageClient({"region": values["REGION"]}, signer=signer)
    with tempfile.TemporaryDirectory(prefix="mccp-dependency-export-") as t:
        Path(t, "backend.tf").write_text('terraform {\n  backend "oci" {}\n}\n')
        command(["terraform", "init", "-input=false", "-no-color", "-backend-config=auth=InstancePrincipal", "-backend-config=namespace=" + values["OCI_TF_STATE_NAMESPACE"], "-backend-config=bucket=" + values["OCI_TF_STATE_BUCKET"], "-backend-config=region=" + values["REGION"], "-backend-config=key=op01_manage_landing_zone_environment/terraform.tfstate"], t)
        documents = extract(json.loads(command(["terraform", "state", "pull"], t)))
    metadata = {"source-repository": values["GITHUB_REPOSITORY"], "source-commit": values["GITHUB_SHA"], "tenancy": values["OCI_TENANCY_OCID"], "region": values["REGION"]}
    for name, document in documents.items():
        body = json.dumps(document, sort_keys=True).encode()
        key = "platform-dependencies/" + values["GITHUB_SHA"] + "/" + name
        try:
            storage.put_object(values["OCI_TF_STATE_NAMESPACE"], values["OCI_TF_STATE_BUCKET"], key, body, opc_meta=metadata, if_none_match="*", content_type="application/json")
        except oci.exceptions.ServiceError as exc:
            if exc.status != 412:
                raise
            previous = storage.get_object(values["OCI_TF_STATE_NAMESPACE"], values["OCI_TF_STATE_BUCKET"], key)
            if previous.data.content != body or any(previous.headers.get("opc-meta-" + k) != v for k, v in metadata.items()):
                raise ValueError("Snapshot is immutable; export changed state from a new reviewed foundation revision") from None
    print("Published two immutable official dependency documents. No raw state exported.")
    print("Snapshot revision: " + values["GITHUB_SHA"])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.exit(str(exc) if isinstance(exc, ValueError) else "Dependency export stopped: " + type(exc).__name__)
