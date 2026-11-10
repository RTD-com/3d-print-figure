import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
NAMES = ['01_top.png', '02_left45.png', '03_front.png', '04_right45.png', '05_left.png', '06_right.png', '07_back.png', '08_bottom.png']


class ValidateViewsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        for name in NAMES:
            Image.new('RGBA', (20, 20), (255, 0, 0, 0)).save(self.root / name)

    def run_validator(self, *args):
        result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(SCRIPTS / 'validate_views.py'), '--input', str(self.root), *args], capture_output=True, text=True, encoding='utf-8')
        report = self.root / '校验报告.json'
        return result, json.loads(report.read_text(encoding='utf-8')) if report.exists() else None

    def test_one_rgb_image_cannot_hide_among_rgba_images(self):
        Image.new('RGB', (20, 20), 'white').save(self.root / NAMES[3])
        result, report = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['ok'])

    def test_identically_sized_rectangles_fail_square_gate(self):
        for name in NAMES:
            Image.new('RGBA', (20, 10), (0, 0, 0, 0)).save(self.root / name)
        result, report = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['checks']['square'])

    def test_alpha_ratio_at_ten_percent_fails(self):
        im = Image.new('RGBA', (20, 20), (255, 0, 0, 255))
        for x in range(20):
            for y in range(2):
                im.putpixel((x, y), (255, 0, 0, 0))
        im.save(self.root / NAMES[0])
        result, _ = self.run_validator()
        self.assertEqual(result.returncode, 1)

    def test_white_mode_accepts_white_rgb_and_records_mode(self):
        for name in NAMES:
            Image.new('RGB', (20, 20), 'white').save(self.root / name)
        result, report = self.run_validator('--alpha-mode', 'white')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report['alphaMode'], 'white')

    def test_corrupt_expected_image_fails(self):
        (self.root / NAMES[2]).write_bytes(b'not png')
        result, report = self.run_validator()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['files'][2]['ok'])

    def test_explicit_six_view_subset_does_not_silently_take_first_six(self):
        (self.root / NAMES[0]).unlink()
        (self.root / NAMES[7]).unlink()
        result, report = self.run_validator('--expected', '6', '--views', 'left45,front,right45,left,right,back')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([e['file'] for e in report['files']], NAMES[1:7])

    def test_contact_sheet_rerun_excludes_itself(self):
        command = [sys.executable, '-X', 'utf8', '-B', str(SCRIPTS / 'build_contact_sheet.py'), '--input', str(self.root), '--thumb', '20', '--cols', '8']
        for _ in range(2):
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with Image.open(self.root / 'contact-sheet.png') as sheet:
                self.assertEqual(sheet.size, (304, 86))


if __name__ == '__main__':
    unittest.main()
