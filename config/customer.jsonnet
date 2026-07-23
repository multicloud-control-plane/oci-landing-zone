// Customer-owned One-OE source configuration.
//
// Replace every customer token below before generating the reviewed JSON files.
// Add further environments here later; the same protected foundation state
// makes those additions normal, repeatable Landing Zone changes.
{
  notification_email: 'david.gutierrez.colodra@oracle.com',
  // OCI assigns this address when the OP03 Bastion is created. Keep it null
  // until then so the generated network contains no example SSH source.
  platform_bastion_private_endpoint_cidr: '10.200.1.213/32',
  // OP01 uses this list to render security and observability controls. During
  // initial installation OP01 remains in its core stage until DEV OP02 exists.
  // Add later environments here only after their OP02 state exists.
  activated_environments: ['dev'],
  blueprint: {
    region: 'eu-frankfurt-1',
    region_short_name: 'fra',
    realm: 'oc1',
    cis_level: 1,

    // Hub E is the low-cost, no-firewall One-OE topology.
    hub: {
      kind: 'hub_e',
      network: { vcn: '10.200.0.0/21' },
    },

    environments: {
      dev: {
        shared_project_network: {
          network: { vcn: '10.200.64.0/21' },
        },
      },
    },
  },
}
