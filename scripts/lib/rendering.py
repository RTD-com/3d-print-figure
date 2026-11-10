"""两个 Blender CLI 共享正交相机与引擎设置；导入模块不启动 Blender。"""
from pathlib import Path

from .camera_math import camera_frame
from .view_spec import VIEWS


def select_engine(requested, available):
    choices = {'eevee': ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'),
               'workbench': ('BLENDER_WORKBENCH',), 'cycles': ('CYCLES',)}
    for engine in choices.get(requested, ()):
        if engine in available:
            return engine
    raise ValueError('所需渲染引擎不可用: {}; 可用值: {}'.format(requested, ', '.join(available)))


def render_views(obj, out_dir, res=1600, engine='workbench'):
    import bpy
    from mathutils import Matrix, Vector

    scene = bpy.context.scene
    available = [item.identifier for item in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
    actual_engine = select_engine(engine, available)
    scene.render.engine = actual_engine
    bbox = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    lower = [min(point[i] for point in bbox) for i in range(3)]
    upper = [max(point[i] for point in bbox) for i in range(3)]
    center = tuple((lower[i] + upper[i]) / 2 for i in range(3))
    size = max(upper[i] - lower[i] for i in range(3)) * 1.12
    if size <= 0:
        raise ValueError('模型包围盒为空')
    cam_data = bpy.data.cameras.new('review_cam')
    cam = bpy.data.objects.new('review_cam', cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = size
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.view_settings.view_transform = 'Standard'
    if engine == 'workbench':
        shading = scene.display.shading
        shading.light = 'STUDIO'
        shading.color_type = 'MATERIAL'
        shading.show_shadows = True
        shading.show_cavity = True
        shading.cavity_type = 'BOTH'
        scene.display.render_aa = '8'
    else:
        if engine == 'cycles':
            scene.cycles.device = 'CPU'
            scene.cycles.samples = 24
            scene.cycles.use_denoising = True
        for name, direction, energy in [('key', (3, -4, 5), 800), ('fill', (-4, -2, 2), 400), ('rim', (0, 4, 4), 600)]:
            light_data = bpy.data.lights.new(name, 'AREA')
            light_data.energy = energy * size * size
            light_data.size = size
            light = bpy.data.objects.new(name, light_data)
            scene.collection.objects.link(light)
            light.location = Vector(center) + Vector(direction) * size
            light.rotation_euler = (Vector(center) - light.location).to_track_quat('-Z', 'Y').to_euler()
    target = Path(out_dir) / 'renders'
    target.mkdir(parents=True, exist_ok=True)
    outputs = []
    for filename, slot in VIEWS:
        frame = camera_frame(slot, center, size * 2)
        cam.location = frame['position']
        # Blender 相机本地 +X 向右、+Y 向上、-Z 向前；显式矩阵避免 top/bottom 极点滚转。
        rotation = Matrix((frame['right'], frame['up'], tuple(-v for v in frame['forward']))).transposed()
        cam.rotation_euler = rotation.to_quaternion().to_euler()
        scene.render.filepath = str(target / filename)
        bpy.ops.render.render(write_still=True)
        outputs.append(scene.render.filepath)
    return outputs, actual_engine
