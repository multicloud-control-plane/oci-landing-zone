import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("snapshot", ROOT / "scripts/export_platform_dependencies.py")
        cls.module = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.module)

    def state(self):
        return {"resources": [
            {"type": "local_file", "name": "compartments_output", "instances": [{"attributes": {"content": json.dumps({"compartments": {"PLATFORM": {"id": "ocid1.compartment.oc1..unit"}}})}}]},
            {"type": "local_file", "name": "network_output", "instances": [{"attributes": {"content": json.dumps({"network_resources": {"vcns": {"HUB": {"id": "ocid1.vcn.oc1.eu-frankfurt-1.unit"}}}})}}]},
            {"type": "oci_database_autonomous_database", "name": "ignored", "instances": [{"attributes": {"admin_password": "never-export"}}]},
        ]}

    def test_exports_only_official_reference_artifacts(self):
        value = self.module.extract(self.state())
        self.assertEqual(set(value), {"compartments_output.json", "network_output.json"})
        self.assertNotIn("never-export", json.dumps(value))

    def test_rejects_duplicate_artifact(self):
        state = self.state(); state["resources"].append(state["resources"][0])
        with self.assertRaises(ValueError):
            self.module.extract(state)

    def test_rejects_secret_values_inside_artifact(self):
        state = self.state()
        state["resources"][0]["instances"][0]["attributes"]["content"] = json.dumps({"compartments": {"P": {"id": "ocid1.compartment.oc1..unit", "password": "no"}}})
        with self.assertRaises(ValueError):
            self.module.extract(state)


if __name__ == "__main__":
    unittest.main()
