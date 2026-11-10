import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'package_artifacts.py'


class PackageArtifactsTests(unittest.TestCase):
    def test_manifest_excludes_profiles_signed_records_and_itself(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('.browser-profiles/Default/Cookies', '2.DSH/model-url.json', '2.DSH/metadata.json', '3.图片/v1/03_front.png'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'test')
            out = root / '2.DSH' / 'manifest.json'
            out.write_text('{}', encoding='utf-8')
            result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(SCRIPT), '--project', str(root)], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual([e['path'] for e in report['files']], ['3.图片/v1/03_front.png'])
            self.assertEqual(report['files'][0]['sha256'], hashlib.sha256(b'test').hexdigest())
            self.assertEqual(report['skillVersion'], '1.0.0')
            self.assertRegex(report['sourceCommit'], r'^[a-f0-9]{40}$')


if __name__ == '__main__':
    unittest.main()
