#!/usr/bin/env python3
"""Create one non-production project repository and publish its handoff."""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
from pathlib import Path


ORGANIZATION_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
PROJECT_RE = re.compile(r"^dev-([a-z][a-z0-9]*(?:-[a-z0-9]+)*)$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class BootstrapError(ValueError):
    """Raised when a repository cannot be initialized safely."""


def gh_api(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["gh", "api", *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        raise BootstrapError("GitHub repository bootstrap request failed.")
    return result


def load_json(value: str, error: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise BootstrapError(error) from exc
    if not isinstance(parsed, dict):
        raise BootstrapError(error)
    return parsed


def target_repository(project: str) -> str:
    match = PROJECT_RE.fullmatch(project)
    if match is None:
        raise BootstrapError("Only one dev project may be bootstrapped.")
    return f"nonprod-{match.group(1)}"


def ensure_repository(
    organization: str,
    template_repository: str,
    target: str,
) -> None:
    response = gh_api("--method", "GET", f"repos/{organization}/{target}", check=False)
    if response.returncode == 0:
        repository = load_json(
            response.stdout,
            "The existing project repository cannot be verified.",
        )
        if repository.get("private") is not True:
            raise BootstrapError("The existing project repository must be private.")
        return
    if "HTTP 404" not in response.stderr:
        raise BootstrapError("The project repository lookup failed.")
    gh_api(
        "--method",
        "POST",
        f"repos/{organization}/{template_repository}/generate",
        "-f",
        f"owner={organization}",
        "-f",
        f"name={target}",
        "-F",
        "private=true",
    )


def publish_handoff(organization: str, target: str, handoff: Path) -> None:
    path = "environments/dev/environment_information.md"
    response = gh_api(
        "--method",
        "GET",
        f"repos/{organization}/{target}/contents/{path}",
    )
    existing = load_json(
        response.stdout,
        "The template handoff file cannot be verified.",
    )
    sha = existing.get("sha")
    if not isinstance(sha, str) or not sha:
        raise BootstrapError("The template handoff file cannot be verified.")
    content = base64.b64encode(handoff.read_bytes()).decode("ascii")
    gh_api(
        "--method",
        "PUT",
        f"repos/{organization}/{target}/contents/{path}",
        "-f",
        "message=Publish OCI development environment handoff",
        "-f",
        f"content={content}",
        "-f",
        f"sha={sha}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization", required=True)
    parser.add_argument("--template-repository", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--handoff-markdown", required=True, type=Path)
    args = parser.parse_args()
    try:
        if ORGANIZATION_RE.fullmatch(args.organization) is None:
            raise BootstrapError("The GitHub organization is invalid.")
        if REPOSITORY_RE.fullmatch(args.template_repository) is None:
            raise BootstrapError("The template repository is invalid.")
        if not args.handoff_markdown.is_file():
            raise BootstrapError("The project handoff artifact is missing.")
        target = target_repository(args.project)
        ensure_repository(args.organization, args.template_repository, target)
        publish_handoff(args.organization, target, args.handoff_markdown)
        print(json.dumps({"ok": True, "repository": f"{args.organization}/{target}"}))
        return 0
    except (BootstrapError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
