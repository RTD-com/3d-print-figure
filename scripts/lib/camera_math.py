"""纯数学正交相机：角色左=+X，角色正面=-Y，头顶=+Z。

top 的画面上=+Y；bottom 的画面上=-Y；其余视角画面上=+Z。
返回的 x/y 分别为画面向右/向上，独立于 Blender。
"""
import math

from .view_spec import VIEWS

CAMERA_DIRECTIONS = {
    'top': (0, 0, 1), 'left45': (1, -1, 0), 'front': (0, -1, 0),
    'right45': (-1, -1, 0), 'left': (1, 0, 0), 'right': (-1, 0, 0),
    'back': (0, 1, 0), 'bottom': (0, 0, -1),
}


def _normalized(vector):
    magnitude = math.sqrt(sum(v * v for v in vector))
    return tuple(v / magnitude for v in vector)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def camera_frame(view, center=(0.0, 0.0, 0.0), distance=1.0):
    if view not in CAMERA_DIRECTIONS:
        raise ValueError('未知视角: {}'.format(view))
    if not math.isfinite(distance) or distance <= 0:
        raise ValueError('相机距离必须为正数')
    direction = _normalized(CAMERA_DIRECTIONS[view])
    forward = tuple(-v for v in direction)
    up = (0.0, 1.0, 0.0) if view == 'top' else ((0.0, -1.0, 0.0) if view == 'bottom' else (0.0, 0.0, 1.0))
    right = _normalized(_cross(forward, up))
    up = _cross(right, forward)
    return {'position': tuple(center[i] + direction[i] * distance for i in range(3)),
            'forward': forward, 'right': right, 'up': up}


def project_point(point, view, center=(0.0, 0.0, 0.0)):
    frame = camera_frame(view, center)
    relative = tuple(point[i] - center[i] for i in range(3))
    return tuple(sum(relative[i] * frame[axis][i] for i in range(3)) for axis in ('right', 'up'))
