"""Build only into a disposable repository-local directory; active installs are untouched."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PS = shutil.which('powershell')


@unittest.skipUnless(os.name == 'nt' and PS, 'Windows PowerShell installer tests')
class InstallTests(unittest.TestCase):
    def test_independent_packages_manifest_no_overwrite_and_explicit_update(self):
        (ROOT / '.tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='install-', dir=ROOT / '.tmp') as temp:
            target = Path(temp) / 'target'
            cmd = [PS, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
                   str(ROOT / 'scripts' / 'install.ps1'), '-DestinationRoot', str(target)]
            first = subprocess.run(cmd, cwd=temp, capture_output=True, timeout=30)
            self.assertEqual(0, first.returncode, first.stderr.decode(errors='replace'))
            for rel in ('.dsh/skills/3d-print-figure', '.agents/skills/3d-print-blender'):
                package = target / rel
                manifest = json.loads((package / 'manifest.json').read_text(encoding='utf-8'))
                self.assertEqual('1.0.0', manifest['version'])
                self.assertRegex(manifest['sourceCommit'], r'^[a-f0-9]{40}$')
                self.assertTrue((package / 'scripts/lib/camera_math.py').is_file())
                for entry in manifest['files']:
                    data = (package / entry['path']).read_bytes()
                    self.assertEqual(len(data), entry['bytes'])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
            stale = target / '.agents/skills/3d-print-blender/old.txt'
            stale.write_text('stale', encoding='utf-8')
            second = subprocess.run(cmd, cwd=temp, capture_output=True, timeout=30)
            self.assertNotEqual(0, second.returncode)
            self.assertTrue(stale.is_file())
            update = subprocess.run(cmd + ['-Update'], cwd=temp, capture_output=True, timeout=30)
            self.assertEqual(0, update.returncode, update.stderr.decode(errors='replace'))
            self.assertFalse(stale.exists())


if __name__ == '__main__':
    unittest.main()
