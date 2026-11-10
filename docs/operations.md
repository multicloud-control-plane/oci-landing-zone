# Phase operations

Use this page to find the configuration and success condition for each phase.

| Phase | Configuration | Successful outcome |
|---|---|---|
| Bootstrap readiness | `.github/workflows/oci-bootstrap-readiness.yaml` | Private foundation runner identity, required tools, and read-only state access are verified |
| OP00 | `op00_manage_global_landing_zone/` | Approved tenancy-wide groups and policies exist |
| OP01 | `op01_manage_landing_zone_environment/` | Shared compartments, network, governance, and security match the plan |
| OP02 | `op02_manage_environment/{environment}/` | Environment resources exist and `project-onboarding-environment.json` is validated |
| OP03 | `op03_manage_platform_gitops/` | Required platform IAM, network, and compute exist |
| OP04 | `op04_manage_project/{environment}/{project}/` | OE project compartments, TBAC groups, AES-256 HSM key in the shared workload Vault, and both handoff files exist |

OP03 is optional only when the platform is hosted elsewhere. When it is hosted in this tenancy, complete its `infrastructure` and `identity` stages before the first OP02: OCI compiles the OP02 runner policies against the existing dynamic group. OP02 repeats per environment. OP04 accepts one project target per run and remains a Cloud Operator operation.

## Frequency and dependency

| Phase | How often | Required predecessor |
|---|---|---|
| Bootstrap readiness | Once before automation, and again after bootstrap changes | Private runner and state boundary |
| OP00 | Once per tenancy; amend only when tenancy-wide IAM changes | Bootstrap readiness |
| OP01 | Start once at `core`, then advance through `pre` and `final` as environments are promoted | OP00; a protected environment blueprint before `pre` and `final` |
| OP03 | Once when MCCP is hosted in this tenancy; `infrastructure` then `identity` | OP01 `core`; focused OP01 Bastion update before `identity` |
| OP02 | Once for every environment | OP03 `identity` when hosted here; otherwise OP01 `core` |
| OP04 | Once for every project in an existing environment | Successful OP02 and OP01 `final` for that environment |

The generated OP01 final security configuration uses only the reviewed OE `master` root CIS Level 1 target. The shared-network and environment child targets are deliberately not part of this MVP: their recipes prohibit NSG deletion and therefore prevent a project-managed NSG lifecycle and project retirement. Do not add a project-specific Security Zone exception; introduce a stronger project-zone design only after its create, update, and delete behavior has been certified.

OP04 creates each delegated project compartment under the environment's `PROJECTS` compartment. Project Teams do not manage Security Zones or receive Security Zone permissions.

OP02 creates the fixed MVP runner policies once per environment. They cover the `PROJECTS` subtree, shared `NETWORK`, and shared `SECURITY` for Compute, ADB, and project NSGs. OP04 does not create a runner policy; it creates the official TBAC project structure and the project key in the environment shared workload Vault. Keep these generated scopes unchanged when onboarding or retiring a project.

The Hub management security list must allow SSH only from the platform Bastion's current private endpoint `/32`. Retrieve that address from OCI, record it in `config/customer.jsonnet` as `platform_bastion_private_endpoint_cidr`, regenerate OP01, and review the focused network plan. A `null` value removes OE's non-authoritative example rule and fails closed. Recreate this focused change whenever the Bastion endpoint is replaced.

## Standard change procedure

1. Confirm the earlier phase outputs and state are healthy.
2. Edit the protected source configuration and generate only the selected phase with `scripts/generate_foundation.sh`.
3. Open a pull request and review the exact Terraform plan.
4. Check replacements, deletions, IAM scope, routes, CIDRs, and state key.
5. Obtain independent approval, merge, and verify the workflow result in OCI.

If a plan or apply fails, retain its logs and reconcile OCI with Terraform state before retrying. Never repair the failure with an unreviewed local apply or a manual state edit.

If an already merged project apply fails because a reviewed foundation dependency is missing or ineffective, correct that foundation through its own plan-and-merge gate first. After verifying the project state contains no partially created OCI resource, a human operator may rerun only the exact failed merge-commit job. Do not push a synthetic no-op manifest change, rerun a different commit, or let the Project GitOps skill control the workflow.

An unchanged configuration should not propose updates that remove `Oracle-Tags.CreatedBy` or `Oracle-Tags.CreatedOn`. OCI adds those automatic default tags after resource creation. The phase workflows use the OCI provider's `ignore_defined_tags` setting for exactly those two keys so a later apply preserves them and remains idempotent. If either tag appears as a removal in a plan, stop before merge and verify that the protected workflow still contains that provider setting.

An idempotency plan can recreate `local_file.*_output` resources because the runner workspace is temporary. Those files are the Orchestrator's dependency JSON artifacts, not OCI resources.

The official Observability module has one known normalization exception for an Object Storage Service Connector target. OCI does not return `target.compartment_id`, while the module supplies it again on every plan. The same behavior is recorded in upstream [issue 17](https://github.com/oci-landing-zones/terraform-oci-modules-observability/issues/17), which was closed as not planned and is still present in the module used by Orchestrator release 2.1.4.

For an unchanged OP01 final configuration, accept repeatability evidence only when the complete plan contains:

- ephemeral `local_file.*_output` creates;
- at most the single in-place `oci_sch_service_connector` update that adds only `target.compartment_id`; and
- no other OCI changes, replacements, or destroys.

Close an idempotency-only pull request without merging it. If the connector diff changes any other field, or any other OCI resource changes, stop and investigate. Do not patch the downloaded official module or suppress broader changes with `ignore_changes`.

After OP04, use `project-foundation-handoff.json` for machine processing and `environment_information.md` for people. The dev onboarding publication job validates these artifacts before creating an absent private project repository from template `main` and publishing its handoff. The schema-5 handoff has a project root plus distinct Application, Database, and Infrastructure child-compartment OCIDs.

The apply job renders both handoff files from its initialized Terraform outputs and uploads only those validated files. The repository publication job consumes that artifact and uses GitHub only. To recover a missing handoff after a completed apply, run `OCI Project Foundation Handoff` on `main` for the exact project. It reads the existing state through OCI CLI with Instance Principal and uses the same renderer, without planning or applying resources. Temporary state and output files are protected and removed; raw state is never uploaded.

## Project Vault lifecycle

Onboarding contract 6 creates one AES-256 HSM key in each new project/environment DB compartment through the currently pinned official security module. It creates no Vault. CloudOps first prepares one DEFAULT workload Vault per environment and OCI region in the environment security compartment through a separate approved CLI operation, then registers its logical key and OCID in blueprint 3 under `security.workload_vault`. The project key uses that authorized `vault_id` in the existing OP04 state and reviewed workflow. The official DB role already permits use of environment security Vaults and manages keys and secrets under the project TBAC condition. The shared runner identity and its permissions remain unchanged.

The schema-5 handoff requires `vault`, `vault_key`, and `secrets_compartment`. Its Vault reference comes only from the protected blueprint, and its key comes from the real OP04 `security_resources` output. Before publication, the renderer validates current Vault metadata, DEFAULT type, ACTIVE state, security-compartment placement, OCI region, the project key ENABLED state, AES-256 HSM shape, DB compartment, and exact management-endpoint binding. Key material stays in HSM; the OCID is a reference. Project Team creates and rotates secrets manually in Database. Onboarding creates no secrets or passwords. Legacy contracts are rejected without migration or changes to existing project declarations or state.


Deploy the reviewed code and register the administratively prepared workload Vault before certifying a fresh dev onboarding. Check the reused Vault, created key, and handoff, then run a second plan with no managed OCI changes. There is no migration of existing projects, no new VM, and no automatic secret or ADB creation.

Project-secret and key retirement is manual. CloudOps removes the project secrets and completes deletion of its key through the approved process before retiring the project foundation; a pending deletion is insufficient. Always retain the shared workload Vault, which is outside OP04 state. The refreshed plan must show the project key absent. The existing plan guard continues to reject all Vault, key and key-version deletion or replacement, including during destroy. Never automate deletion, waiting, or state removal.

OP04 pins the official Orchestrator v2.3.0 release commit. Its root integration supplies `vaults_dependency = null` through `op04_vault_dependency_override.tf` because OP04 owns the Vault and key in the same declaration and accepts no external Vault dependency. This compensates for v2.3.0 normalizing an absent dependency to `{}`, which makes Security v0.2.3 select a nonexistent data lookup. The official child module and resource addresses remain unchanged. Remove this root adapter only after an upstream fix passes the same onboarding and idempotency checks.

## OP04 provider mirror

OP04 pins `oracle/oci` to 9.12.1 and copies `config/op04-provider.lock.hcl` from the trusted controls revision before initialization. The lock records official checksums obtained from the origin registry with `terraform providers lock -platform=linux_arm64 -platform=linux_amd64 oracle/oci`. Review the signing-key identity printed by Terraform when generating or updating this file. Never generate the trusted lock from the mirror itself.

The optional repository variable `OP04_OCI_PROVIDER_MIRROR_PATH` selects an absolute filesystem mirror path on every eligible OP04 runner, for example `/opt/mccp/terraform-provider-mirror`. When unset, OP04 uses its normal provider installation configuration and still verifies OCI against the trusted lock. When set, OP04 creates a private temporary CLI configuration under `RUNNER_TEMP` and sets `TF_CLI_CONFIG_FILE` for that job only. It installs only `registry.terraform.io/oracle/oci` from the mirror and excludes that provider from direct installation. Mirror mode disables the shared plugin cache so each job verifies the selected mirror archive against the trusted lock. Other providers keep direct registry installation. A missing package or checksum mismatch fails initialization; there is no OCI download fallback. The existing five initialization attempts remain in place.

Prepare the mirror on a connected administrative host using a temporary Terraform root that requires only `oracle/oci` at `= 9.12.1`. Generate the lock from the origin registry using the command above, compare it with the reviewed lock, then run `terraform providers mirror -platform=linux_arm64 /path/to/staging-mirror`. Terraform authenticates the official package using the publisher's signed checksums. Retain that verification evidence and compare the archive's SHA-256 digest with the signed release checksums before and after transfer through the existing administrative connection. Include `-platform=linux_amd64` when AMD64 runners also need the mirror. Do not open network rules to install it.

For the packed filesystem layout, the ARM64 archive must be at `/opt/mccp/terraform-provider-mirror/registry.terraform.io/oracle/oci/terraform-provider-oci_9.12.1_linux_arm64.zip`. Install the verified archive with root ownership, directories mode `0755`, and files mode `0644`; only administrators may write to the mirror or its parent directories. Keep archives and signing evidence outside Git. Set the repository variable only after testing on the runner with OCI provider download access blocked, a minimal provider-only root, the reviewed lock, and `terraform init -backend=false`. Confirm success with the valid archive and failure with a missing or modified archive in separate temporary mirrors. This check must not use foundation state or apply resources.

For an update, obtain a new official package and origin-registry lock, review the OP04 version pin and lock together, stage and verify the package on each runner, then merge the reviewed change. Keep the previous package until existing jobs finish. Removing the repository variable restores normal installation without changing the pinned version. This mirror removes only the OCI provider download dependency from OP04; module downloads and other providers still require network access.

For the separately approved administrative procedure and first certification, see [shared workload Vault administration](workload-vault.md).
