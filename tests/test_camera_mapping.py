"""用非对称坐标捕获左右镜像、极点翻转和斜视图误倾斜。"""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from lib.camera_math import camera_frame, project_point
from lib.rendering import select_engine


class CameraMappingTests(unittest.TestCase):
    def test_asymmetric_marker_projects_to_expected_eight_views(self):
        # 角色左 +X；面向 -Y；头顶 +Z。点非对称，能发现镜像或换轴。
        point = (3.0, -2.0, 5.0)
        root = math.sqrt(2)
        expected = {
            'top': (3, -2), 'left45': (1 / root, 5),
            'front': (3, 5), 'right45': (5 / root, 5),
            'left': (-2, 5), 'right': (2, 5),
            'back': (-3, 5), 'bottom': (3, 2),
        }
        for view, want in expected.items():
            with self.subTest(view=view):
                got = project_point(point, view)
                self.assertAlmostEqual(got[0], want[0])
                self.assertAlmostEqual(got[1], want[1])

    def test_second_marker_preserves_up_and_screen_left(self):
        point = (-7.0, 1.0, -4.0)
        expected = {
            'top': (-7, 1), 'left45': (-3 * math.sqrt(2), -4),
            'front': (-7, -4), 'right45': (-4 * math.sqrt(2), -4),
            'left': (1, -4), 'right': (-1, -4),
            'back': (7, -4), 'bottom': (-7, -1),
        }
        for view, want in expected.items():
            with self.subTest(view=view):
                got = project_point(point, view)
                self.assertAlmostEqual(got[0], want[0])
                self.assertAlmostEqual(got[1], want[1])

    def test_front_and_role_left_camera_positions(self):
        self.assertEqual(camera_frame('front')['position'], (0.0, -1.0, 0.0))
        self.assertEqual(camera_frame('left')['position'], (1.0, 0.0, 0.0))
        self.assertEqual(camera_frame('right')['position'], (-1.0, 0.0, 0.0))

    def test_unknown_view_and_nonpositive_distance_are_rejected(self):
        with self.assertRaises(ValueError):
            camera_frame('diagonal')
        with self.assertRaises(ValueError):
            camera_frame('front', distance=0)

    def test_eevee_uses_an_enum_the_running_blender_actually_exposes(self):
        self.assertEqual(select_engine('eevee', ['BLENDER_EEVEE', 'CYCLES']), 'BLENDER_EEVEE')
        self.assertEqual(select_engine('eevee', ['BLENDER_EEVEE_NEXT']), 'BLENDER_EEVEE_NEXT')
        with self.assertRaises(ValueError):
            select_engine('eevee', ['CYCLES'])


if __name__ == '__main__':
    unittest.main()
