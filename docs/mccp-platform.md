# Optional APEX MCCP workload integration

The CloudOps-owned workload repository is [apex-mccp-platform](https://github.com/multicloud-control-plane/apex-mccp-platform). It defines the dedicated private ADB platform under `CMP-LZ-PLATFORM-KEY`, with its own Terraform state. The existing foundation runner executes it through the manually dispatched `MCCP platform manual deployment` workflow; the private workload repo runs source checks only. It does not modify this foundation's state or manage any existing LB subresource. APEX installation remains manual and team-owned.

This integration is inactive when the customer declaration has no `mccp_publication` field. The source update changes no generated phase document or live OCI resource by itself. OP00-OP04 and existing workload permissions are unchanged. Do not combine source adoption with a customer publication change: the protected generated-contract workflow must first receive the trusted adapter.

## Export sanitized dependencies

The simplified manual deployment workflow exports references itself before planning or applying the separate workload stack. The standalone `Export MCCP foundation references` workflow remains an optional administrative utility. The foundation runner needs Python 3.9+, the OCI Python SDK (tested with 2.189.0), Jsonnet and the existing Terraform/backend prerequisites. The private workload repository cannot dispatch either workflow. Human review/merge is the owner-approved first-deployment control; these controls are not technically enforced GitHub review rules.

The exporter reads OP01 state privately, extracts only the root official `compartments_output` and `network_output` local-file contents, validates that they contain reference maps only, and uploads immutable objects to `platform-dependencies/<export-commit>/compartments_output.json` and `network_output.json` in `OCI_TF_STATE_BUCKET`. Metadata binds source repository, export commit, tenancy and region. No raw state is uploaded or shown. The exporter commit identifies a reference snapshot, not the last apply revision of every resource. Repeated exports of the same revision can reuse identical objects but cannot overwrite changed content.

The existing foundation runner retains its foundation identity and existing state access. It reads the sanitized reference objects for workload inputs and uses a separate state object, `apex-mccp-platform/eu-frankfurt-1/terraform.tfstate`, in the existing private versioned foundation bucket. OP01 state remains separate. This simpler mode creates no additional runner, bucket, or IAM grant; it relies on trusted foundation maintainers reviewing the exact workload revision before dispatch. It does not provide separate least-privilege execution identities.

## Manual workload execution

The owner requested the simplest path on 2026-11-18: keep the workload definitions in the separate private repository and reuse foundation execution. The new workflow is manual-only, main-only and additionally gated by the initially unset foundation variable `MCCP_AUTOMATION_READY`. It never executes on a workload PR or merge.

Review and merge the complete workload source/configuration first. The workflow takes a full `platform_revision` already on workload main, requests a contents-read token scoped to that repository from the existing bootstrap App, and uses the existing foundation runner. The App installation must allow that private repository; this source update does not grant installation access. Select operation `plan`; review the result; then dispatch `apply` with the same revision repeated in `approved_revision`. Each apply replans and applies its own binary plan. Deletion/replacement of cloud resources is rejected by the workload guard. Administrator access can bypass manual review.

A temporary copy of the workload declaration receives only this workflow's `GITHUB_SHA` as `foundation_revision`, binding it to the reference export. Scope mismatches, disabled declarations and an explicit conflicting snapshot revision are rejected. Customer choices and the ADMIN secret reference are not invented. The existing foundation variables, state bucket and App credentials are reused. Verify effective OCI permissions and tools before enabling the workflow. No ADB, secret value, runner, bucket or public listener is created by adopting this source.

## Publish a completed workload

First deploy the private workload, then obtain its actual private endpoint IP from the successful handoff. Reserve a new DNS hostname, issue/import its matching certificate into OCI Certificates and prepare the trusted ADB backend CA references. Do not reuse the existing ClickOps hostname for a parallel deployment. DNS, certificate issuance/import and renewal remain administrator-owned manual prerequisites in this release; certificate private keys and DuckDNS tokens must never enter the declaration.

The following is a **configuration shape**, not a configured deployment. Replace every symbolic value with reviewed references before generation:

```jsonnet
mccp_publication: {
  enabled: true,
  load_balancer_key: 'LB-FRA-LZ-DEV-01-KEY',
  hub_route_table_keys: [
    'RT-FRA-LZ-HUB-LB-KEY',
    'RT-FRA-LZ-HUB-MGMT-KEY',
  ],
  platform_cidr: '<approved-platform-vcn-cidr>',
  backend_ip: '<actual-adb-private-endpoint-ip>',
  hostname: '<reserved-mccp-hostname>',
  certificate_id: '<matching-oci-certificate-ocid>',
  backend_trusted_ca_ids: ['<oci-ca-bundle-or-ca-ocid>'],
},
```

Add the block to `config/customer.jsonnet`, regenerate OP01 through `scripts/generate_foundation.sh op01`, then submit a focused OP01 configuration/generated-output PR. OP01 remains the sole owner of the shared LB and all listeners/backends. Review hub routes, hostname, listener, backend, TLS validation, certificate references and all unrelated changes in the matching plan. Never put a second `network_configuration` input beside the complete OP01 network document: Terraform does not deep-merge independent root-variable files.

The overlay adds routes to the explicitly selected hub route tables, a hostname-bound TLS listener on 443 and an HTTPS backend to the private ADB on 443. It preserves existing routes, HTTP listeners and backend sets. It rejects existing 443 listeners, reserved logical keys and invalid backend/hostname references. A currently shared HTTPS listener requires a separately designed extension; never delete it to bypass a conflict. Verify that the existing LB NSG permits 443 and that the new workload's NSG permits the hub LB subnet. Include private-installer hub route tables when handing off SQL access.

The health checker expects `/ords/` to return the standard 302 redirect; validate that behavior during platform acceptance. Backend TLS peer verification is enabled and requires usable trusted-CA references. This source change has offline contract tests but is not a successful OCI plan/apply or end-to-end certification.

For source checks, run `python3 -m unittest discover -s validation -v`. Hosted contract checks use no cloud credentials. The standalone workload repository's deployment guide defines customer inputs, runner/state ownership, application handoff and retirement limits.
