import bpy
from mathutils import Vector
sc = bpy.context.scene
H = 427.8
bpy.data.lights['KeySpot'].energy = 10_000_000
nt = bpy.data.materials['Windows_Lit'].node_tree
for n in nt.nodes:
    if n.type == 'MATH' and n.operation == 'MULTIPLY':
        n.inputs[1].default_value = 30.0
cam = bpy.data.objects['Camera']
# Кадр 1 — ночной героический снизу
cam.location = (-H*0.62, -H*0.68, 10)
d = Vector((0, 0, H*0.52)) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 30
cam.data.dof.use_dof = False
sc.view_settings.exposure = 1.6
sc.cycles.samples = 200
sc.render.resolution_percentage = 100
sc.render.filepath = '/workspace/skyscraper/render_night.png'
bpy.ops.render.render(write_still=True)
print('NIGHT OK')
# Кадр 2 — общий план с высоты
cam.location = (-H*1.05, -H*1.15, H*0.75)
dd = Vector((0, 0, H*0.38)) - cam.location
cam.rotation_euler = dd.to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 45
sc.render.filepath = '/workspace/skyscraper/render_hero.png'
bpy.ops.render.render(write_still=True)
print('HERO OK')
# Сохранить финальный .blend с настроенными камерой/светом
bpy.ops.wm.save_as_mainfile(filepath='/workspace/skyscraper/skyscraper.blend')
print('BLEND UPDATED')
