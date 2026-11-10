#!/usr/bin/env python
"""Blender 修复与打印导出独立阶段；默认不覆盖，S8 不写最终 STL。

repair: --stage repair --blend <初版.blend> --out-dir <4.2表面修复版>
export: --stage export --blend <最终.blend> --out-dir <打印检查报告目录>
        --stl <5.打印/项目_final.stl> --confirm-gate G9 --confirmation-file <用户确认.json>
自交/薄壁默认 unknown；可用 --checks-file 导入绑定最终 blend 的可靠测量证据。
"""
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.artifact_policy import (apply_measurement_evidence, ensure_new, export_allowed,
                                 sha256, validate_g9)
from lib.rendering import render_views
from lib.view_spec import EXPECTED


class GateError(ValueError):
    pass


def parse_args(argv=None):
    if argv is None:
        argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=('repair', 'export'), required=True)
    parser.add_argument('--blend', required=True)
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--stl')
    parser.add_argument('--confirm-gate')
    parser.add_argument('--confirmation-file')
    parser.add_argument('--checks-file')
    parser.add_argument('--height-mm', type=float, default=150.0)
    parser.add_argument('--min-wall-mm', type=float, default=1.0)
    parser.add_argument('--res', type=int, default=1600)
    parser.add_argument('--engine', choices=('workbench', 'eevee', 'cycles'), default='workbench')
    parser.add_argument('--issues-file', help='本次问题列表JSON（数组或含 issues 数组）')
    parser.add_argument('--force', action='store_true')
    return parser.parse_args(argv)


def mesh_stats(obj):
    import bmesh
    import bpy
    from mathutils.kdtree import KDTree

    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.transform(evaluated.matrix_world)
        unit_mm = bpy.context.scene.unit_settings.scale_length * 1000
        for vert in bm.verts:
            vert.co *= unit_mm
        bm.normal_update()
        boundary = sum(len(edge.link_faces) == 1 for edge in bm.edges)
        nonmanifold = sum(len(edge.link_faces) != 2 for edge in bm.edges)
        loose = sum(not vert.link_faces for vert in bm.verts)
        degenerate = sum(face.calc_area() <= 1e-10 for face in bm.faces)
        normal_conflicts = sum(edge.is_manifold and not edge.is_contiguous for edge in bm.edges)
        # 分连通壳计算有向体积，不能用各壳相互抵消后的总体积冒充法线均朝外。
        unseen = set(bm.faces)
        shell_volumes = []
        while unseen:
            pending = [unseen.pop()]
            signed_shell = 0.0
            while pending:
                face = pending.pop()
                vertices = [vert.co for vert in face.verts]
                for index in range(1, len(vertices) - 1):
                    signed_shell += vertices[0].dot(vertices[index].cross(vertices[index + 1])) / 6
                for edge in face.edges:
                    for neighbor in edge.link_faces:
                        if neighbor in unseen:
                            unseen.remove(neighbor)
                            pending.append(neighbor)
            shell_volumes.append(signed_shell)
        tree = KDTree(len(bm.verts))
        for index, vert in enumerate(bm.verts):
            tree.insert(vert.co, index)
        tree.balance()
        duplicate_pairs = 0
        for index, vert in enumerate(bm.verts):
            duplicate_pairs += sum(other > index for _, other, _ in tree.find_range(vert.co, 1e-5))
        try:
            volume = bm.calc_volume(signed=True)
        except (ValueError, RuntimeError):
            volume = None
        coords = [vert.co.copy() for vert in bm.verts]
        lower = [min((point[i] for point in coords), default=0) for i in range(3)]
        upper = [max((point[i] for point in coords), default=0) for i in range(3)]
        return {'verts': len(bm.verts), 'edges': len(bm.edges), 'faces': len(bm.faces),
                'boundaryEdges': boundary, 'nonManifoldEdges': nonmanifold,
                'looseVerts': loose, 'degenerateFaces': degenerate,
                'duplicateVertexPairs': duplicate_pairs, 'normalConflicts': normal_conflicts,
                'signedVolumeMm3': volume, 'shellSignedVolumesMm3': shell_volumes,
                'volumeMm3': abs(volume) if volume is not None else None,
                'bboxMm': [upper[i] - lower[i] for i in range(3)], 'bboxMinMm': lower,
                'unitFactorMm': unit_mm}
    finally:
        bm.free()
        evaluated.to_mesh_clear()


def print_checks(stats, height_mm, min_wall_mm):
    def result(ok, measured, threshold, method):
        return {'status': 'pass' if ok else 'fail', 'measured': measured,
                'threshold': threshold, 'method': method}
    water = stats['faces'] > 0 and stats['nonManifoldEdges'] == 0 and stats['looseVerts'] == 0
    volume = stats['signedVolumeMm3']
    dims = stats['bboxMm']
    bbox_ok = all(math.isfinite(value) and value > 0 for value in dims) and abs(dims[2] - height_mm) <= 0.5
    checks = {
        'watertight': result(water, {'boundaryEdges': stats['boundaryEdges'], 'nonManifoldEdges': stats['nonManifoldEdges'], 'looseVerts': stats['looseVerts']}, 0, 'evaluated mesh / bmesh edge adjacency'),
        'selfIntersection': {'status': 'unknown', 'reason': '未运行可靠三角面自交测量；不能用水密代替自交检查'},
        'degenerateFaces': result(stats['degenerateFaces'] == 0, stats['degenerateFaces'], 0, 'evaluated world-mm face area <= 1e-10 mm2'),
        'duplicateVertices': result(stats['duplicateVertexPairs'] == 0, stats['duplicateVertexPairs'], 0, 'KDTree world-mm distance <= 1e-5 mm'),
        'normals': result(water and stats['normalConflicts'] == 0 and bool(stats['shellSignedVolumesMm3']) and all(math.isfinite(value) and value > 0 for value in stats['shellSignedVolumesMm3']), {'conflicts': stats['normalConflicts'], 'shellSignedVolumesMm3': stats['shellSignedVolumesMm3']}, 'consistent closed outward orientation per connected shell', 'bmesh contiguous edges + per-shell signed volume'),
        'volume': result(volume is not None and math.isfinite(volume) and abs(volume) > 0, abs(volume) if volume is not None else None, '>0 mm3', 'bmesh calc_volume'),
        'bbox': result(bbox_ok, dims, {'heightMm': height_mm, 'heightToleranceMm': 0.5, 'allDimensions': '>0, finite'}, 'evaluated world bounding box / scene unit scale'),
        'thinWalls': {'status': 'unknown', 'thresholdMm': min_wall_mm, 'reason': '未运行可靠壁厚测量；需带证据的实测报告'},
    }
    if volume is None:
        checks['volume']['status'] = 'unknown'
    return checks


def cleanup(obj):
    import bmesh
    bm = bmesh.new()
    warnings = []
    try:
        bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.0001)
        loose = [vert for vert in bm.verts if not vert.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
        boundary = [edge for edge in bm.edges if edge.is_boundary]
        if boundary:
            try:
                bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
            except (RuntimeError, ValueError) as exc:
                warnings.append('补孔失败: ' + str(exc))
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()
    return warnings


def select_figure():
    import bpy
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if not meshes:
        raise RuntimeError('blend 中没有 mesh 对象')
    # 单物体 fallback 保留实际引用；多mesh不能静默漏导部件。
    if len(meshes) != 1:
        raise GateError('打印/修复需要一个合并后的角色 mesh；发现 {} 个，请先显式合并并审核'.format(len(meshes)))
    return meshes[0]


def write_report(report, out_dir, name):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / (name + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# ' + ('修复说明' if name == 'repair-report' else '打印检查'), '',
             '- 造型门 shapeAccepted：{}'.format(report['shapeAccepted']),
             '- 打印门 watertight：{}'.format(report['checks']['watertight']['status']), '',
             '| 检查 | 状态 |', '|---|---|']
    lines.extend('| {} | {} |'.format(key, value['status']) for key, value in report['checks'].items())
    lines.extend(['', '## 已知限制', ''])
    lines.extend('- ' + str(issue) for issue in report['issues'])
    (out_dir / ('修复说明.md' if name == 'repair-report' else '打印检查.md')).write_text('\n'.join(lines) + '\n', encoding='utf-8')


def export_stl(obj, stl, factor):
    import bpy
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    stl.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    for namespace, operator in (('wm', 'stl_export'), ('export_mesh', 'stl')):
        try:
            function = getattr(getattr(bpy.ops, namespace), operator)
            if namespace == 'wm':
                result = function(filepath=str(stl), export_selected_objects=True,
                                  global_scale=factor, apply_modifiers=True, use_scene_unit=False)
            else:
                result = function(filepath=str(stl), use_selection=True, global_scale=factor,
                                  ascii=False, use_scene_unit=False)
            if 'FINISHED' in result and stl.is_file() and stl.stat().st_size > 84:
                return
        except (AttributeError, RuntimeError, TypeError) as exc:
            errors.append(str(exc))
    raise RuntimeError('STL 导出失败: ' + '; '.join(errors))


def main():
    args = parse_args()
    blend = Path(args.blend).resolve()
    out_dir = Path(args.out_dir).resolve()
    if not blend.is_file():
        raise FileNotFoundError(str(blend))
    if not all(math.isfinite(value) and value > 0 for value in (args.height_mm, args.min_wall_mm)) or args.res < 1:
        raise GateError('尺寸/最小壁厚/分辨率必须为正数')
    user_issues = []
    if args.issues_file:
        supplied = json.loads(Path(args.issues_file).read_text(encoding='utf-8'))
        user_issues = supplied if isinstance(supplied, list) else supplied.get('issues', [])
        if not isinstance(user_issues, list):
            raise ValueError('issues-file 必须包含问题数组')
    if args.stage == 'repair':
        if args.stl or '5.打印' in out_dir.parts:
            raise GateError('repair 仅写修复版本目录，不接受 --stl 或 5.打印 输出目录')
        outputs = [out_dir / filename for filename in ('表面修复版.blend', '表面修复版.glb', 'repair-report.json', '修复说明.md')]
        outputs += [out_dir / 'renders' / filename for filename in EXPECTED]
        if blend == outputs[0]:
            raise GateError('repair 输入与输出 blend 相同；必须使用新版本目录')
        ensure_new(outputs, args.force)
        confirmation = None
    else:
        if not args.stl:
            raise GateError('export 必须提供 --stl')
        try:
            confirmation = validate_g9(args.confirm_gate, args.confirmation_file, blend)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise GateError(str(exc)) from exc
        stl = Path(args.stl).resolve()
        ensure_new([stl, out_dir / 'print-report.json', out_dir / '打印检查.md'], args.force)

    import bpy
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    obj = select_figure()
    before = mesh_stats(obj)
    warnings = cleanup(obj) if args.stage == 'repair' else []
    bpy.context.view_layer.update()
    after = mesh_stats(obj)
    checks = print_checks(after, args.height_mm, args.min_wall_mm)
    if args.stage == 'export':
        try:
            checks = apply_measurement_evidence(checks, args.checks_file, blend, args.min_wall_mm)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise GateError(str(exc)) from exc
    issues = list(user_issues) + warnings
    issues.extend('{}: {}'.format(name, check.get('reason', check.get('measured'))) for name, check in checks.items() if check['status'] != 'pass')
    if args.stage == 'repair':
        issues.append('修复可能改变几何；保形性和造型必须经 S9 渲染对照及用户确认，不能由拓扑数据推定')
    report = {'stage': 'S8' if args.stage == 'repair' else 'S10',
              'sourceBlend': str(blend), 'sourceBlendSha256': sha256(blend),
              'shapeAccepted': confirmation['shapeAccepted'] if confirmation else 'unknown',
              'watertight': checks['watertight']['status'], 'checks': checks,
              'before': before, 'after': after, 'issues': issues, 'stl': None}
    if args.stage == 'repair':
        out_dir.mkdir(parents=True, exist_ok=True)
        renders, engine = render_views(obj, out_dir, args.res, args.engine)
        blend_out = out_dir / '表面修复版.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_out))
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        glb_out = out_dir / '表面修复版.glb'
        bpy.ops.export_scene.gltf(filepath=str(glb_out), export_format='GLB', use_selection=True)
        report.update({'blend': str(blend_out), 'glb': str(glb_out), 'renders': renders, 'engine': engine})
        write_report(report, out_dir, 'repair-report')
        print('REPAIR_REPORT ' + json.dumps(report, ensure_ascii=False))
        return 0
    if not export_allowed(checks):
        write_report(report, out_dir, 'print-report')
        print('PRINT_GATE_BLOCKED ' + json.dumps(report, ensure_ascii=False))
        return 14
    export_stl(obj, stl, after['unitFactorMm'])
    report.update({'stl': str(stl), 'stlBytes': stl.stat().st_size, 'stlSha256': sha256(stl)})
    write_report(report, out_dir, 'print-report')
    print('PRINT_REPORT ' + json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except GateError as exc:
        print('PRINT_GATE_ERROR ' + str(exc), file=sys.stderr)
        sys.exit(14)
    except Exception as exc:
        print('BLENDER_ERROR ' + repr(exc), file=sys.stderr)
        sys.exit(1)
