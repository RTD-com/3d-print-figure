import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from lib.artifact_policy import apply_measurement_evidence, ensure_new, export_allowed, validate_g9
from blender_repair_export import print_checks


class ArtifactPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.blend = self.root / 'final.blend'
        self.blend.write_bytes(b'blend fixture')

    def test_existing_output_is_preserved_unless_force_is_explicit(self):
        with self.assertRaises(FileExistsError):
            ensure_new([self.blend])
        self.assertEqual(self.blend.read_bytes(), b'blend fixture')
        ensure_new([self.blend], force=True)

    def test_g9_requires_matching_final_blend_and_shape_acceptance(self):
        record = {'gate': 'G9', 'confirmedAt': '2026-11-05T10:00:00Z', 'shapeAccepted': True,
                  'blendSha256': hashlib.sha256(self.blend.read_bytes()).hexdigest()}
        confirmation = self.root / 'confirm.json'
        confirmation.write_text(json.dumps(record), encoding='utf-8')
        self.assertTrue(validate_g9('G9', confirmation, self.blend)['shapeAccepted'])
        self.blend.write_bytes(b'changed after confirmation')
        with self.assertRaises(ValueError):
            validate_g9('G9', confirmation, self.blend)

    def test_unknown_or_missing_print_check_blocks_final_export(self):
        checks = {name: {'status': 'pass'} for name in ('watertight', 'selfIntersection', 'degenerateFaces', 'duplicateVertices', 'normals', 'volume', 'bbox', 'thinWalls')}
        self.assertTrue(export_allowed(checks))
        checks['thinWalls']['status'] = 'unknown'
        self.assertFalse(export_allowed(checks))
        del checks['thinWalls']
        self.assertFalse(export_allowed(checks))

    def test_confirmation_without_explicit_gate_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_g9(None, None, self.blend)

    def test_measurement_cannot_be_replaced_by_unsubstantiated_pass(self):
        report = self.root / 'checks.json'
        report.write_text(json.dumps({'blendSha256': hashlib.sha256(self.blend.read_bytes()).hexdigest(),
                                      'checks': {'thinWalls': {'status': 'pass'}}}), encoding='utf-8')
        with self.assertRaises(ValueError):
            apply_measurement_evidence({}, report, self.blend, 1.0)

    def test_measurement_is_bound_to_evidence_hash_and_wall_threshold(self):
        evidence = self.root / 'measurement.txt'
        evidence.write_bytes(b'calibrated thickness result')
        report = self.root / 'checks.json'
        value = {'blendSha256': hashlib.sha256(self.blend.read_bytes()).hexdigest(),
                 'checks': {'thinWalls': {'method': 'independent thickness measurement',
                                         'unit': 'mm', 'measured': 0.8, 'threshold': 1.0,
                                         'evidence': {'path': evidence.name, 'sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}}}}
        report.write_text(json.dumps(value), encoding='utf-8')
        checks = apply_measurement_evidence({}, report, self.blend, 1.0)
        self.assertEqual(checks['thinWalls']['status'], 'fail')
        evidence.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            apply_measurement_evidence({}, report, self.blend, 1.0)

    def test_export_missing_g9_exits_before_importing_blender(self):
        script = Path(__file__).resolve().parents[1] / 'scripts' / 'blender_repair_export.py'
        result = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(script), '--',
                                 '--stage', 'export', '--blend', str(self.blend),
                                 '--out-dir', str(self.root / 'report'), '--stl', str(self.root / 'final.stl')],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 14, result.stderr)
        self.assertIn('G9', result.stderr)
        self.assertFalse((self.root / 'final.stl').exists())

    def test_negative_shell_orientation_cannot_hide_in_positive_total_volume(self):
        stats = {'faces': 10, 'nonManifoldEdges': 0, 'looseVerts': 0, 'boundaryEdges': 0,
                 'signedVolumeMm3': 100, 'bboxMm': [80, 60, 150], 'degenerateFaces': 0,
                 'duplicateVertexPairs': 0, 'normalConflicts': 0, 'shellSignedVolumesMm3': [110, -10]}
        checks = print_checks(stats, 150, 1)
        self.assertEqual(checks['watertight']['status'], 'pass')
        self.assertEqual(checks['normals']['status'], 'fail')
        self.assertEqual(checks['selfIntersection']['status'], 'unknown')
        self.assertEqual(checks['thinWalls']['status'], 'unknown')
        self.assertFalse(export_allowed(checks))


if __name__ == '__main__':
    unittest.main()
