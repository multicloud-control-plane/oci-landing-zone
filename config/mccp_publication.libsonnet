// Optional customer-owned MCCP publication, using the existing OP01 LB state.
local field(obj, key, fallback) =
  if std.objectHas(obj, key) && obj[key] != null then obj[key] else fallback;
local ipv4(ip) =
  assert std.type(ip) == 'string' : 'MCCP backend must be an IPv4 address';
  local parts = std.split(ip, '.');
  assert std.length(parts) == 4 : 'Expected IPv4';
  local numbers = [
    assert std.length(part) > 0 && std.length(part) <= 3 : 'Invalid IPv4 octet';
    assert std.foldl(function(ok, char) ok && std.member('0123456789', char), std.stringChars(part), true) : 'Invalid IPv4 octet';
    local number = std.parseInt(part);
    assert number <= 255 && std.toString(number) == part : 'Noncanonical IPv4';
    number
    for part in parts
  ];
  std.foldl(function(value, number) value * 256 + number, numbers, 0);
local private(ip) =
  (ip >= ipv4('10.0.0.0') && ip <= ipv4('10.255.255.255')) ||
  (ip >= ipv4('172.16.0.0') && ip <= ipv4('172.31.255.255')) ||
  (ip >= ipv4('192.168.0.0') && ip <= ipv4('192.168.255.255'));
local valid_hostname(hostname) =
  std.type(hostname) == 'string' && std.length(hostname) <= 253 &&
  std.length(std.split(hostname, '.')) >= 2 &&
  std.foldl(function(ok, label)
    ok && std.length(label) > 0 && std.length(label) <= 63 &&
    !std.startsWith(label, '-') && !std.endsWith(label, '-') &&
    std.foldl(function(good, char) good && std.member('abcdefghijklmnopqrstuvwxyz0123456789-', char), std.stringChars(label), true),
    std.split(hostname, '.'), true);
{
  apply(document, p, hub_vcn_key, drg_key, routed_cidrs=[]):
    if p == null then document
    else
      assert std.type(p) == 'object' && std.objectHas(p, 'enabled') && std.type(p.enabled) == 'boolean' : 'MCCP publication requires an explicit boolean enabled';
      if !p.enabled then
        assert std.objectFields(p) == ['enabled'] : 'Disabled MCCP publication must contain only enabled: false';
        document
      else
        assert std.objectFields(p) == std.sort([
          'enabled', 'load_balancer_key', 'hub_route_table_keys', 'platform_cidr',
          'backend_ip', 'hostname', 'certificate_id', 'backend_trusted_ca_ids',
        ]) : 'Unexpected or missing MCCP publication fields; never pass private keys';
        assert valid_hostname(p.hostname) : 'Expected a lowercase DNS hostname, without scheme or path';
        assert std.type(p.certificate_id) == 'string' && std.startsWith(p.certificate_id, 'ocid1.certificate.oc1.') : 'Provide an existing OCI Certificate reference';
        assert std.type(p.backend_trusted_ca_ids) == 'array' && std.length(p.backend_trusted_ca_ids) > 0 : 'Provide the trusted CA references for the ADB TLS certificate';
        assert std.foldl(function(ok, id) ok && std.type(id) == 'string' && (std.startsWith(id, 'ocid1.cabundle.oc1.') || std.startsWith(id, 'ocid1.certificateauthority.oc1.')), p.backend_trusted_ca_ids, true) : 'Invalid backend CA reference';
        local parts = std.split(p.platform_cidr, '/');
        assert std.length(parts) == 2 : 'Expected platform CIDR';
        local base = ipv4(parts[0]);
        local prefix = std.parseInt(parts[1]);
        assert prefix >= 8 && prefix <= 29 && private(base) : 'Expected a private platform CIDR';
        local size = std.pow(2, 32 - prefix);
        assert std.mod(base, size) == 0 : 'Platform CIDR must be canonical';
        assert private(base + size - 1) : 'The entire platform CIDR must be private';
        local ip = ipv4(p.backend_ip);
        assert ip > base && ip < base + size - 1 && private(ip) : 'ADB private IP must be in the platform network';
        local category = document.network_configuration.network_configuration_categories['0-shared'];
        local hub = category.vcns[hub_vcn_key];
        local forbidden = routed_cidrs + std.flattenArrays([field(category.vcns[key], 'cidr_blocks', []) for key in std.objectFields(category.vcns)]);
        assert std.foldl(function(ok, cidr)
          local other = std.split(cidr, '/');
          local start = ipv4(other[0]);
          local end = start + std.pow(2, 32 - std.parseInt(other[1])) - 1;
          ok && !(base <= end && start < base + size),
          forbidden, true) : 'MCCP network overlaps an existing foundation network';
        assert std.type(p.hub_route_table_keys) == 'array' && std.length(p.hub_route_table_keys) > 0 : 'Choose the hub route tables for LB and private installers';
        assert std.length(std.set(p.hub_route_table_keys)) == std.length(p.hub_route_table_keys) : 'Duplicate route table key';
        assert std.foldl(function(ok, key) ok && std.objectHas(hub.route_tables, key), p.hub_route_table_keys, true) : 'Unknown hub route table';
        local lbs = category.non_vcn_specific_gateways.l7_load_balancers;
        assert std.objectHas(lbs, p.load_balancer_key) : 'Unknown shared LB key';
        local lb = lbs[p.load_balancer_key];
        local listeners = field(lb, 'listeners', {});
        local backends = field(lb, 'backend_sets', {});
        local hostnames = field(lb, 'host_names', {});
        assert !field(lb, 'is_private', false) : 'MCCP publication requires the shared public LB';
        assert std.length([key for key in std.objectFields(listeners) if std.toString(listeners[key].port) == '443']) == 0 : 'HTTPS port is already owned: extend the existing listener through a separate reviewed design';
        assert !std.objectHas(listeners, 'MCCP-HTTPS-KEY') && !std.objectHas(backends, 'MCCP-BACKEND-KEY') && !std.objectHas(hostnames, 'MCCP-HOSTNAME-KEY') : 'MCCP logical key collision';
        assert std.length([key for key in std.objectFields(hostnames) if hostnames[key].hostname == p.hostname]) == 0 : 'Hostname is already owned';
        document {
          network_configuration+: {
            network_configuration_categories+: {
              '0-shared'+: {
                vcns+: {
                  [hub_vcn_key]+: {
                    route_tables+: {
                      [key]+: {
                        route_rules+:
                          assert !std.objectHas(hub.route_tables[key].route_rules, 'mccp-platform') : 'MCCP route collision';
                          {
                            'mccp-platform': {
                              description: 'Route to the MCCP platform through the shared DRG',
                              destination: p.platform_cidr, destination_type: 'CIDR_BLOCK', network_entity_key: drg_key,
                            },
                          },
                      }
                      for key in p.hub_route_table_keys
                    },
                  },
                },
                non_vcn_specific_gateways+: {
                  l7_load_balancers+: {
                    [p.load_balancer_key]+: {
                      host_names: hostnames + {
                        'MCCP-HOSTNAME-KEY': { name: 'mccp', hostname: p.hostname },
                      },
                      backend_sets: backends + {
                        'MCCP-BACKEND-KEY': {
                          name: 'mccp-adb', policy: 'ROUND_ROBIN',
                          backends: { 'MCCP-ADB-KEY': { ip_address: p.backend_ip, port: 443 } },
                          health_checker: {
                            protocol: 'HTTP', port: 443, url_path: '/ords/', return_code: 302,
                            interval_ms: 10000, timeout_in_millis: 3000, retries: 3, is_force_plain_text: false,
                          },
                          ssl_configuration: {
                            trusted_certificate_authority_ids: p.backend_trusted_ca_ids,
                            verify_peer_certificate: true, verify_depth: 5,
                            protocols: ['TLSv1.2'],
                          },
                        },
                      },
                      listeners: listeners + {
                        'MCCP-HTTPS-KEY': {
                          name: 'mccp-https', port: '443', protocol: 'HTTP',
                          default_backend_set_key: 'MCCP-BACKEND-KEY', hostname_keys: ['MCCP-HOSTNAME-KEY'],
                          ssl_configuration: { certificate_ids: [p.certificate_id], protocols: ['TLSv1.2'], verify_peer_certificate: false },
                        },
                      },
                    },
                  },
                },
              },
            },
          },
        },
}
