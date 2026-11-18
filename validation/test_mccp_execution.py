import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("prepare_mccp", Path(__file__).resolve().parents[1] / "scripts/prepare_mccp_configuration.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExecutionTests(unittest.TestCase):
    def settings(self):
        return {"enabled": True, "foundation_repository": "multicloud-control-plane/oci-landing-zone",
                "foundation_revision": None, "tenancy_ocid": "tenancy", "region": "region",
                "database": {"admin_password_secret_id": "secret-reference"}}

    def test_snapshot_binding_preserves_customer_values_and_input(self):
        settings = self.settings()
        prepared = module.prepare(settings, "a" * 40, "tenancy", "region")
        self.assertEqual(prepared, {**settings, "foundation_revision": "a" * 40})
        self.assertIsNone(settings["foundation_revision"])

    def test_rejects_disabled_foreign_scope_and_stale_snapshot(self):
        for key, value in (("enabled", False), ("enabled", 1), ("region", "foreign"),
                           ("tenancy_ocid", "foreign"), ("foundation_repository", "foreign"),
                           ("foundation_revision", "b" * 40)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.prepare({**self.settings(), key: value}, "a" * 40, "tenancy", "region")
        with self.assertRaises(ValueError):
            module.prepare(self.settings(), "main", "tenancy", "region")
