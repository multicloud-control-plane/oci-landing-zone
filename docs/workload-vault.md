# Shared workload Vault administration

CloudOps owns one DEFAULT workload Vault for each environment and OCI region, including its administration, lifecycle, quota checks and recovery. This is a separately approved, one-time OCI CLI operation. Do not add a Terraform module, state or workflow for the Vault. OP04 creates only the project key. The audit Vault and existing project Vaults are outside this operation.

## Prepare and register

1. Use the protected environment blueprint from the configured foundation repository at `main`. Read its tenancy, region and `compartments.security.ocid`; do not accept scope overrides. The first certification uses `dev`, `eu-frankfurt-1`, `cmp-lz-dev-security` and `vlt-lz-dev-workloads`.
2. Check the effective KMS service limits and available capacity in that tenancy and region. Inspect the existing increase request and verify that its approval is effective and the requested limit of 25 is visible before depending on it. An open request or an approval notification alone is insufficient. Do not automatically cancel the request. Select the DEFAULT Vault limit returned by OCI, rather than assuming that a private-Vault limit applies.
3. List all Vaults in the blueprint security compartment, including non-ACTIVE entries. If exactly one expected workload Vault exists, verify its metadata and reuse it only when it is DEFAULT and ACTIVE in the exact compartment and region. Stop on duplicates, an incompatible resource, pending deletion, or any ambiguous result. Never repurpose an audit or project Vault.
4. If no expected Vault exists and capacity is available, create the DEFAULT Vault and wait for ACTIVE. Verify its OCID, display name, type, region and compartment from the returned metadata. Do not record a pending or failed Vault.

The following commands are for the separately authorized CloudOps administrative session. `BLUEPRINT` names the protected environment file; derive `REGION`, `SECURITY_COMPARTMENT` and `TENANCY` from it. Keep administrative evidence outside Git. These commands contain no secret values.

```bash
REGION="$(jq -er '.region' "$BLUEPRINT")"
SECURITY_COMPARTMENT="$(jq -er '.compartments.security.ocid' "$BLUEPRINT")"
TENANCY="$(jq -er '.tenancy_ocid' "$BLUEPRINT")"
oci limits value list --service-name kms --compartment-id "$TENANCY" --region "$REGION" --all
# Select the DEFAULT Vault limit name from this result, then check availability.
oci limits resource-availability get --service-name kms --limit-name "$DEFAULT_VAULT_LIMIT" --compartment-id "$TENANCY" --region "$REGION"
oci kms management vault list --compartment-id "$SECURITY_COMPARTMENT" --region "$REGION" --all
# Only after the checks above establish that no expected Vault exists:
oci kms management vault create --compartment-id "$SECURITY_COMPARTMENT" --display-name vlt-lz-dev-workloads --vault-type DEFAULT --region "$REGION" --wait-for-state ACTIVE
oci kms management vault get --vault-id "$WORKLOAD_VAULT_OCID" --region "$REGION"
```

After metadata verification, prepare one reviewed blueprint PR that sets `schema_version` to `3` and adds:

```json
{
  "security": {
    "workload_vault": {
      "key": "VLT-LZ-DEV-WORKLOADS-KEY",
      "ocid": "<verified workload Vault OCID>"
    }
  }
}
```

Keep every existing blueprint field, including the exact `source` provenance. This administrative registration does not require a new OP02 run. The protected blueprint is the only authorized Vault reference. A later OP02 capture preserves the registration only when environment, region, tenancy, projects parent and security compartment remain compatible; it rejects incompatible references. Initial OP02 evidence can exist without a Vault registration, but OP04 onboarding cannot proceed until the registration is reviewed and merged.

## Access and retirement

Keep the official TBAC DB role permissions to manage keys and secret-family inside the project Database compartment, and its existing `use vaults` permission in environment security. The existing shared runner already uses environment Vaults and reads the approved project resources; do not broaden its permissions or create another runner without a demonstrated need. Verify effective metadata and secret-bundle access during the reviewed certification. Both automatic publication and artifact-only recovery read current key metadata through the shared Vault management endpoint before rendering the handoff. They require the saved key OCID to remain ENABLED, in project Database, bound to the authorized Vault, and AES-256 HSM. A failed query or incomplete response stops publication; no key material is read. The existing official security module v0.2.3 accepts a literal `vault_id`; keep its provider/module pins and the existing null dependency override.

CloudOps must manually remove project secrets and complete deletion of the project key before retiring its foundation. Pending deletion is insufficient. Refresh must show the key absent; the plan guard must reject key or Vault deletion or replacement. Always retain the shared Vault, which has no OP04 state ownership. Do not migrate or edit declarations, resources or state of old projects.

## First live certification after human review and merge

Verify that `dev-project130` is free before selecting it. Never reuse the partial state of `dev-project129`. Onboard the new project, then verify one project key, zero new Vaults, the automatically created private repository and its handoff. Create two independent password secrets in project Database and a control secret outside it, without printing their values. Verify that the foreign secret fails before content retrieval or Terraform initialization.

Use the unchanged approved profiles: OCI Small BYOL private in Frankfurt, and Azure Small BYOL public with mTLS in `dev/uksouth`, resource group `rg-emea-oa`. Each ADB uses its own `admin_password_secret_id`. Verify resources and a subsequent plan with no unexpected changes, replacements or deletions. Do not test SQL connections. Real Vault preparation, registration publication, onboarding and deployments require their existing approvals; local regression success is not live certification.
