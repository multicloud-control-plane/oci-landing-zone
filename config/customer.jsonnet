// Customer-owned One-OE source configuration.
//
// Replace every customer token below before generating the reviewed JSON files.
// Add further environments here later; the same protected foundation state
// makes those additions normal, repeatable Landing Zone changes.
{
  notification_email: 'david.gutierrez.colodra@oracle.com',
  // OCI assigned this endpoint to bst-mccp-platform-runner.
  platform_bastion_private_endpoint_cidr: '10.200.1.213/32',
  // OP01 uses this list to render security and observability controls. During
  // initial installation OP01 remains in its core stage until DEV OP02 exists.
  // Add later environments here only after their OP02 state exists.
  activated_environments: ['dev'],
  // Publish the separately managed MCCP platform through the shared hub LB.
  mccp_publication: {
    enabled: true,
    load_balancer_key: 'LB-FRA-LZ-DEV-01-KEY',
    hub_route_table_keys: ['RT-FRA-LZ-HUB-LB-KEY', 'RT-FRA-LZ-HUB-MGMT-KEY'],
    platform_cidr: '10.200.8.0/24',
    backend_ip: '10.200.8.29',
    hostname: 'apex-mccp.duckdns.org',
    certificate_id: 'ocid1.certificate.oc1.eu-frankfurt-1.amaaaaaa2vk6mfaafml32h3xod6w4dcc4jsxcxa7fzcpyqkdfklnhd6xge3a',
    backend_trusted_ca_ids: ['ocid1.cabundle.oc1.eu-frankfurt-1.amaaaaaa2vk6mfaaohzv75ofvceo5jgvvj2eckzjb67lukxjqhviovblm2mq'],
  },
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
