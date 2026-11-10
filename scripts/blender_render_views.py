#!/usr/bin/env python
"""Blender 无头入口：导入 GLB、归一化并渲染八视角；默认拒绝覆盖。

运行：blender --background --python <skillRoot>/scripts/blender_render_views.py --
  --glb <初版.glb> --out-dir <4.1初版> --height-mm 150 --res 1600
GLB 朝向无法自动认证；经审核后可用 --front-axis 显式声明源模型正面。
"""
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.artifact_policy import ensure_new
from lib.rendering import render_views
from lib.view_spec import EXPECTED


def parse_args(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument('--glb', required=True)
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--height-mm', type=float, default=150.0)
    parser.add_argument('--res', type=int, default=1600)
    parser.add_argument('--engine', choices=('workbench', 'eevee', 'cycles'), default='workbench')
    parser.add_argument('--front-axis', choices=('unknown', '-Y', '+Y', '+X', '-X'), default='unknown')
    parser.add_argument('--force', action='store_true')
    return parser.parse_args(argv)


def main():
    args = parse_args()
    if not math.isfinite(args.height_mm) or args.height_mm <= 0 or args.res < 1:
        raise ValueError('目标高度与分辨率必须为正数')
    source = Path(args.glb).resolve()
    if not source.is_file():
        raise FileNotFoundError(str(source))
    out_dir = Path(args.out_dir).resolve()
    blend = out_dir / '初版.blend'
    info_file = out_dir / 'scene-info.json'
    ensure_new([blend, info_file] + [out_dir / 'renders' / name for name in EXPECTED], args.force)

    import bpy
    from mathutils import Vector

    # 仅限本无头新建场景入口，不用于用户正在编辑的 live 场景。
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if not meshes:
        raise RuntimeError('GLB 中没有 mesh 对象')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = 'figure'
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 0.001
    if args.front_axis != 'unknown':
        obj.rotation_euler.z += {'-Y': 0, '+Y': math.pi, '+X': -math.pi / 2, '-X': math.pi / 2}[args.front_axis]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.context.view_layer.update()
    bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    height = max(point.z for point in bbox) - min(point.z for point in bbox)
    if height <= 0:
        raise RuntimeError('模型高度为 0')
    factor = args.height_mm / height
    obj.scale = (factor, factor, factor)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.context.view_layer.update()
    bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    center = Vector(((max(p.x for p in bbox) + min(p.x for p in bbox)) / 2,
                     (max(p.y for p in bbox) + min(p.y for p in bbox)) / 2,
                     min(p.z for p in bbox)))
    obj.location -= center
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    bpy.context.view_layer.update()
    out_dir.mkdir(parents=True, exist_ok=True)
    renders, engine = render_views(obj, out_dir, args.res, args.engine)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    info = {'glb': str(source), 'blend': str(blend), 'heightMm': args.height_mm,
            'unit': '1 BU = 1 mm', 'bboxMm': [max(p[i] for p in bbox) - min(p[i] for p in bbox) for i in range(3)],
            'verts': len(obj.data.vertices), 'faces': len(obj.data.polygons), 'renders': renders,
            'engine': engine, 'orientation': 'unknown' if args.front_axis == 'unknown' else 'user-declared',
            'sourceFrontAxis': args.front_axis, 'coordinateConvention': 'front=-Y; character-left=+X; up=+Z'}
    info_file.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SCENE_INFO ' + json.dumps(info, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('BLENDER_ERROR ' + repr(exc), file=sys.stderr)
        sys.exit(1)
