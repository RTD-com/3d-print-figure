import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'selfcheck.py'


class SelfcheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('repo_selfcheck', SCRIPT)
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)

    def test_schema_rejects_wrong_pair_and_extra_tuple_item(self):
        schema = {'type': 'array', 'prefixItems': [
            {'type': 'object', 'required': ['file', 'slot'], 'properties': {
                'file': {'const': '01_top.png'}, 'slot': {'const': 'top'}}}
        ], 'items': False, 'minItems': 1}
        self.assertEqual([], self.mod.validate_schema([{'file': '01_top.png', 'slot': 'top'}], schema))
        self.assertTrue(self.mod.validate_schema([{'file': '01_top.png', 'slot': 'front'}], schema))
        self.assertTrue(self.mod.validate_schema([{}, {}], schema))

    def test_unsupported_schema_keyword_is_error(self):
        self.assertTrue(self.mod.validate_schema(1, {'type': 'integer', 'inventedConstraint': 2}))

    def test_boolean_is_not_number(self):
        self.assertTrue(self.mod.validate_schema(True, {'type': 'number'}))

    def test_missing_markdown_resource_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            md = root / 'note.md'
            md.write_text('[missing](missing.py)\n[external](https://example.org)', encoding='utf-8')
            self.assertEqual(['missing.py'], [item[1] for item in self.mod.missing_links(md, root)])

    def test_package_closure_checks_command_resources_and_document_links(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'SKILL.md').write_text('Run `python scripts/validate_views.py`\n[history](docs/missing.md)', encoding='utf-8')
            errors = self.mod.check_package_closure(root, {'entry': 'SKILL.md', 'files': []})
            self.assertTrue(any('scripts/validate_views.py' in error for error in errors))
            self.assertTrue(any('docs/missing.md' in error for error in errors))


    @unittest.skipUnless(shutil.which('git'), 'Git unavailable')
    def test_private_project_and_credentials_are_rejected_even_if_staged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            samples = ('手办/notes.txt', '.env.local', 'docs/evidence/page.txt', 'token.txt')
            for rel in samples:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                content = 'ghp_' + 'a' * 36 if rel == 'token.txt' else 'synthetic'
                path.write_text(content, encoding='utf-8')
            subprocess.run(['git', '-C', str(root), 'add', '--', *samples], check=True)
            check = next(c for c in self.mod.run(root)['checks'] if c['name'] == 'tracked-sensitive-files')
            self.assertEqual('fail', check['status'])
            for rel in samples:
                self.assertTrue(any(rel in error for error in check['errors']), rel)

if __name__ == '__main__':
    unittest.main()
