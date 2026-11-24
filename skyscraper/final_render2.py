# -*- coding: utf-8 -*-
"""Финальный рендер: 2 кадра, CPU-оптимизированные настройки."""
import bpy
from mathutils import Vector

sc = bpy.scene if False else bpy.context.scene
H = 427.8

# Подсветка окон поярче (для ночного неба)
nt = bpy.data.materials['Windows_Lit'].node_tree
for n in nt.nodes:
    if n.type == 'MATH' and n.operation == 'MULTIPLY':
        n.inputs[1].default_value = 30.0

bpy.data.lights['KeySpot'].energy = 10_000_000

# Разумные настройки для CPU: 96 сэмплов + денойз, 70% резолва -> потом апскейл не нужен
sc.cycles.samples = 96
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 6
sc.render.resolution_percentage = 75   # 1440x810

cam = bpy.data.objects['Camera']

# Кадр 1 — ночной героический снизу
cam.location = (-H*0.62, -H*0.68, 10)
d = Vector((0, 0, H*0.52)) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 30
cam.data.dof.use_dof = False
sc.view_settings.exposure = 1.6
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

bpy.ops.wm.save_as_mainfile(filepath='/workspace/skyscraper/skyscraper.blend')
print('BLEND UPDATED')
print('ALL DONE')
