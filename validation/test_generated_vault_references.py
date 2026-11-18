import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
MARKER = 'python3 - "$GITHUB_WORKSPACE/trusted" "$RUNNER_TEMP/render-config" <<\'PYVAULT\''


class GeneratedVaultReferencesTests(unittest.TestCase):
    def run_preparation(self, projects, blueprint_environment='dev'):
        workflow = (ROOT / '.github/workflows/oci-generated-contract.yaml').read_text()
        self.assertTrue(MARKER in workflow, "CI must prepare protected workload Vault references")
        code = textwrap.dedent(workflow.split(MARKER, 1)[1].split('PYVAULT', 1)[0])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); trusted = root / 'trusted'; rendered = root / 'rendered'
            (trusted / 'scripts').mkdir(parents=True); (trusted / '.github').mkdir()
            (trusted / 'blueprints/dev').mkdir(parents=True); rendered.mkdir()
            for name in ('workload_vault.py', 'oci-region-codes.json'):
                shutil.copyfile(ROOT / 'scripts' / name, trusted / 'scripts' / name)
            contract = {'contract_version': 6, 'environment_blueprints': {'dev': 'blueprints/dev/main.json'}}
            (trusted / '.github/project-onboarding-contract.json').write_text(json.dumps(contract))
            vault = {'key': 'VLT-LZ-DEV-WORKLOADS-KEY', 'ocid': 'ocid1.vault.oc1.eu-frankfurt-1.approved'}
            blueprint = {'schema_version': 3, 'environment': blueprint_environment, 'region': 'eu-frankfurt-1',
                         'compartments': {'security': {'key': 'CMP-LZ-DEV-SECURITY-KEY', 'ocid': 'ocid1.compartment.oc1..security'}},
                         'security': {'workload_vault': vault}}
            (trusted / 'blueprints/dev/main.json').write_text(json.dumps(blueprint))
            (rendered / 'projects.json').write_text(json.dumps({'dev': projects}))
            result = subprocess.run([sys.executable, '-', str(trusted), str(rendered)], input=code, capture_output=True, text=True)
            output = rendered / 'workload_vaults.json'
            return result.returncode, json.loads(output.read_text()) if output.exists() else None, vault

    def test_regenerator_provides_only_protected_vault_references(self):
        code, output, vault = self.run_preparation(['example'])
        self.assertEqual(code, 0)
        self.assertEqual(output, {'dev': vault})

    def test_empty_projects_need_no_vault_and_foreign_blueprint_fails_closed(self):
        code, output, _ = self.run_preparation([])
        self.assertEqual((code, output), (0, {}))
        code, output, _ = self.run_preparation(['example'], blueprint_environment='prod')
        self.assertNotEqual(code, 0)
        self.assertIsNone(output)
