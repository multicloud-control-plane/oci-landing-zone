import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def original():
    return {"network_configuration": {"network_configuration_categories": {"0-shared": {
        "vcns": {"HUB": {"cidr_blocks": ["10.200.0.0/21"], "route_tables": {"RT": {"route_rules": {"internet": {"destination": "0.0.0.0/0"}}}}}},
        "non_vcn_specific_gateways": {"l7_load_balancers": {"LB": {
            "is_private": False,
            "listeners": {"OLD": {"name": "old", "port": "80", "protocol": "HTTP"}},
            "backend_sets": {"OLD": {"name": "old-backend"}},
        }}},
    }}}}


def publication():
    return {
        "enabled": True, "load_balancer_key": "LB", "hub_route_table_keys": ["RT"],
        "platform_cidr": "10.254.0.0/24", "backend_ip": "10.254.0.5",
        "hostname": "mccp.example.org", "certificate_id": "ocid1.certificate.oc1.eu-frankfurt-1.unit",
        "backend_trusted_ca_ids": ["ocid1.cabundle.oc1.eu-frankfurt-1.unit"],
    }


class PublicationTests(unittest.TestCase):
    def render(self, document, pub):
        lib = ROOT / "config/mccp_publication.libsonnet"
        with tempfile.TemporaryDirectory() as t:
            p = Path(t)
            (p / "input.json").write_text(json.dumps(document))
            (p / "pub.json").write_text(json.dumps(pub))
            expr = '(import %s).apply(import %s, import %s, "HUB", "DRG")' % tuple(json.dumps(str(f)) for f in (lib, p / "input.json", p / "pub.json"))
            return subprocess.run(["jsonnet", "-e", expr], capture_output=True, text=True)

    def test_disabled_is_exact_identity(self):
        for p in (None, {"enabled": False}):
            r = self.render(original(), p)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout), original())

    def test_adds_https_and_preserves_unrelated_resources(self):
        before = original(); r = self.render(before, publication())
        self.assertEqual(r.returncode, 0, r.stderr)
        cat = json.loads(r.stdout)["network_configuration"]["network_configuration_categories"]["0-shared"]
        lb = cat["non_vcn_specific_gateways"]["l7_load_balancers"]["LB"]
        self.assertEqual(lb["listeners"]["OLD"], before["network_configuration"]["network_configuration_categories"]["0-shared"]["non_vcn_specific_gateways"]["l7_load_balancers"]["LB"]["listeners"]["OLD"])
        listener = lb["listeners"]["MCCP-HTTPS-KEY"]
        self.assertEqual(listener["port"], "443")
        self.assertEqual(listener["hostname_keys"], ["MCCP-HOSTNAME-KEY"])
        self.assertEqual(listener["ssl_configuration"]["certificate_ids"], [publication()["certificate_id"]])
        backend = lb["backend_sets"]["MCCP-BACKEND-KEY"]
        self.assertTrue(backend["ssl_configuration"]["verify_peer_certificate"])
        self.assertEqual(backend["backends"]["MCCP-ADB-KEY"]["port"], 443)
        routes = cat["vcns"]["HUB"]["route_tables"]["RT"]["route_rules"]
        self.assertIn("internet", routes)
        self.assertEqual(routes["mccp-platform"]["network_entity_key"], "DRG")

    def test_rejects_existing_https_listener(self):
        d = original(); d["network_configuration"]["network_configuration_categories"]["0-shared"]["non_vcn_specific_gateways"]["l7_load_balancers"]["LB"]["listeners"]["EXISTING"] = {"port": "443"}
        self.assertNotEqual(self.render(d, publication()).returncode, 0)

    def test_rejects_bad_backend_domain_certificate_or_unknown_fields(self):
        for key, value in (("backend_ip", "8.8.8.8"), ("backend_ip", "10.254.1.5"), ("hostname", "https://mccp.example.org/"), ("certificate_id", "private-key"), ("backend_trusted_ca_ids", []), ("private_key", "forbidden")):
            p = publication(); p[key] = value
            with self.subTest(key=key, value=value):
                self.assertNotEqual(self.render(original(), p).returncode, 0)

    def test_rejects_existing_reserved_backend_key(self):
        d = original(); d["network_configuration"]["network_configuration_categories"]["0-shared"]["non_vcn_specific_gateways"]["l7_load_balancers"]["LB"]["backend_sets"]["MCCP-BACKEND-KEY"] = {}
        self.assertNotEqual(self.render(d, publication()).returncode, 0)

    def test_rejects_network_spanning_public_space_or_overlapping_hub(self):
        for network, address in (("192.168.0.0/13", "192.168.0.5"), ("10.200.0.0/24", "10.200.0.5")):
            p = publication(); p["platform_cidr"] = network; p["backend_ip"] = address
            with self.subTest(network=network):
                self.assertNotEqual(self.render(original(), p).returncode, 0)


if __name__ == "__main__":
    unittest.main()
