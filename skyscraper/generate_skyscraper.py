# -*- coding: utf-8 -*-
"""
Процедурный небоскрёб в стиле ар-деко (Blender 4.2 LTS).
Запуск:  blender -b -P generate_skyscraper.py -- build|render|all
"""
import bpy
import bmesh
import math
import random
import sys
from mathutils import Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["all"]
MODE = ARGS[0] if ARGS else "all"

FLOOR_H = 3.2

# ---------------------------------------------------------------- utilities

def link_object(obj):
    bpy.context.collection.objects.link(obj)
    return obj

def new_mesh_object(name):
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    return link_object(ob)

def make_box(name, x0, x1, y0, y1, z0, z1):
    verts = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    faces = [(0,1,2,3),(4,5,6,7),(0,1,5,4),(2,3,7,6),(1,2,6,5),(0,3,7,4)]
    ob = new_mesh_object(name)
    ob.data.from_pydata(verts, [], faces)
    ob.data.update()
    return ob

def prism_from_loop(name, loops):
    """loops: замкнутые контуры вершин по возрастанию Z -> призма со стенками и крышками."""
    ob = new_mesh_object(name)
    bm = bmesh.new()
    rings = [[bm.verts.new(v) for v in loop] for loop in loops]
    for ri in range(len(rings) - 1):
        a, b = rings[ri], rings[ri+1]
        n = len(a)
        for i in range(n):
            j = (i+1) % n
            try: bm.faces.new((a[i], a[j], b[j], b[i]))
            except ValueError: pass
    try: bm.faces.new(list(reversed(rings[0])))
    except ValueError: pass
    try: bm.faces.new(rings[-1])
    except ValueError: pass
    bm.normal_update()
    bm.to_mesh(ob.data); bm.free(); ob.data.update()
    return ob

def add_bevel(ob, width=0.03, angle=math.radians(40)):
    m = ob.modifiers.new("bevel", 'BEVEL')
    m.width = width; m.segments = 2
    m.limit_method = 'ANGLE'; m.angle_limit = angle
    return ob

# ---------------------------------------------------------------- materials

def set_inputs(m, mapping):
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    for k, v in mapping.items():
        if k in bsdf.inputs:
            bsdf.inputs[k].default_value = (*v, 1.0) if isinstance(v, tuple) and len(v) == 3 else v

def mat_simple(name, mapping):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    set_inputs(m, mapping)
    return m

def build_materials():
    mats = {}
    # Камень фасада с процедурной текстурой травертина + bump
    stone = bpy.data.materials.new("Facade_Stone"); stone.use_nodes = True
    nt = stone.node_tree; bsdf = nt.nodes["Principled BSDF"]
    texco = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 6.0
    noise.inputs["Detail"].default_value = 8.0
    nt.links.new(texco.outputs["Object"], noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.055, 0.046, 0.038, 1)
    ramp.color_ramp.elements[1].color = (0.13, 0.11, 0.09, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.62
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.15
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    mats['stone'] = stone

    mats['bronze'] = mat_simple("Bronze_Ribs", {
        "Base Color": (0.30, 0.17, 0.075), "Metallic": 1.0, "Roughness": 0.30})
    mats['gold'] = mat_simple("Gold_Accent", {
        "Base Color": (0.85, 0.60, 0.22), "Metallic": 1.0, "Roughness": 0.20})
    mats['metal'] = mat_simple("Steel_Spire", {
        "Base Color": (0.55, 0.56, 0.58), "Metallic": 1.0, "Roughness": 0.28})
    mats['ground'] = mat_simple("Ground_Asphalt", {
        "Base Color": (0.020, 0.020, 0.024), "Roughness": 0.16})

    # Светящиеся окна: шум решает, какие ячейки горят (Generated coords => уникально на объект)
    lit = bpy.data.materials.new("Windows_Lit"); lit.use_nodes = True
    nt = lit.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.9
    noise.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Generated"], noise.inputs["Vector"])
    gt = nt.nodes.new("ShaderNodeMath"); gt.operation = 'GREATER_THAN'
    gt.inputs[1].default_value = 0.50
    nt.links.new(noise.outputs["Fac"], gt.inputs[0])
    strmul = nt.nodes.new("ShaderNodeMath"); strmul.operation = 'MULTIPLY'
    strmul.inputs[1].default_value = 12.0
    nt.links.new(gt.outputs[0], strmul.inputs[0])
    rampc = nt.nodes.new("ShaderNodeValToRGB")
    rampc.color_ramp.elements[0].color = (1.0, 0.52, 0.16, 1)
    rampc.color_ramp.elements[1].color = (1.0, 0.86, 0.58, 1)
    nt.links.new(noise.outputs["Fac"], rampc.inputs["Fac"])
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(rampc.outputs["Color"], em.inputs["Color"])
    nt.links.new(strmul.outputs[0], em.inputs["Strength"])
    dark = nt.nodes.new("ShaderNodeBsdfDiffuse")
    dark.inputs["Color"].default_value = (0.005, 0.006, 0.008, 1)
    mixsh = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(gt.outputs[0], mixsh.inputs["Fac"])
    nt.links.new(dark.outputs["BSDF"], mixsh.inputs[1])
    nt.links.new(em.outputs[0], mixsh.inputs[2])
    nt.links.new(mixsh.outputs[0], out.inputs["Surface"])
    mats['lit'] = lit

    beac = bpy.data.materials.new("Beacon_Red"); beac.use_nodes = True
    b = beac.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Color"].default_value = (1.0, 0.02, 0.02, 1)
    b.inputs["Emission Strength"].default_value = 80.0
    mats['beacon'] = beac

    lampg = bpy.data.materials.new("LampGlow"); lampg.use_nodes = True
    lb = lampg.node_tree.nodes["Principled BSDF"]
    lb.inputs["Emission Color"].default_value = (1.0, 0.68, 0.34, 1)
    lb.inputs["Emission Strength"].default_value = 45.0
    mats['lamp'] = lampg
    return mats

# ---------------------------------------------------------------- windows

def add_window_bands(blocks, mats):
    """Светящиеся оконные ленты на прямоугольных setback-блоках."""
    count = 0
    for (w, d, z0, z1) in blocks:
        hw, hd = w/2, d/2
        nfloors = max(1, int(round((z1 - z0) / FLOOR_H)))
        cols_w = max(2, round(w / 3.2))
        cols_d = max(2, round(d / 3.2))
        for f in range(nfloors):
            wz0 = z0 + f*FLOOR_H + FLOOR_H*0.20
            wz1 = z0 + f*FLOOR_H + FLOOR_H*0.76
            for side in range(4):
                n = cols_w if side in (0, 1) else cols_d
                for c in range(n):
                    t0 = -1 + 2*c/n + 0.10/n
                    t1 = -1 + 2*(c+0.78)/n
                    u0 = (t0+1)/2; u1 = (t1+1)/2
                    if side == 0:
                        box = make_box("Win", hw, hw+0.18, -hd+u0*d, -hd+u1*d, wz0, wz1)
                    elif side == 1:
                        box = make_box("Win", -hw-0.18, -hw, -hd+u0*d, -hd+u1*d, wz0, wz1)
                    elif side == 2:
                        box = make_box("Win", -hw+u0*w, -hw+u1*w, hd, hd+0.18, wz0, wz1)
                    else:
                        box = make_box("Win", -hw+u0*w, -hw+u1*w, -hd-0.18, -hd, wz0, wz1)
                    box.data.materials.append(mats['lit'])
                    count += 1
    return count

# ---------------------------------------------------------------- tower

def build_tower(mats):
    main_blocks = []
    Z = 18.0

    # Восьмигранный стилобат
    base_r = 27.0
    zsteps = [0.0, 4.0, 9.0, 14.0, 18.0]
    radii = [base_r, base_r*0.985, base_r*0.95, base_r*0.90, base_r*0.86]
    loops = []
    for zz, rr in zip(zsteps, radii):
        loop = [(rr*math.cos(math.pi/8 + i*math.pi/4),
                 rr*math.sin(math.pi/8 + i*math.pi/4), zz) for i in range(8)]
        loops.append(loop)
    podium = prism_from_loop("Podium", loops)
    podium.data.materials.append(mats['stone'])
    add_bevel(podium)

    # Входной портал + стекло + козырёк
    r_in = base_r*0.86*math.cos(math.pi/8)
    portal = make_box("Portal", -5, 5, r_in-1.2, r_in+0.7, 0, 10.5)
    portal.data.materials.append(mats['bronze'])
    pglass = make_box("Portal_Glass", -4.0, 4.0, r_in-0.4, r_in+0.8, 0.6, 9.0)
    pglass.data.materials.append(mats['lit'])
    canopy = make_box("Canopy", -7.2, 7.2, r_in-0.2, r_in+3.6, 10.5, 11.4)
    canopy.data.materials.append(mats['gold'])

    # Ступенчатые блоки (сетбэки) — классика ар-деко
    plan = [
        (44.0, 44.0, 64.0),
        (35.0, 35.0, 58.0),
        (27.0, 27.0, 52.0),
        (19.0, 19.0, 46.0),
        (13.0, 13.0, 40.0),
        (8.5, 8.5, 30.0),
    ]
    for idx, (w, d, hgt) in enumerate(plan):
        z0, z1 = Z, Z + hgt
        blk = make_box("Block_%d" % idx, -w/2, w/2, -d/2, d/2, z0, z1)
        blk.data.materials.append(mats['stone'])
        add_bevel(blk)
        main_blocks.append((w, d, z0, z1))
        # Карниз-пояс сверху
        corn = make_box("Cornice_%d" % idx, -w/2-1.0, w/2+1.0, -d/2-1.0, d/2+1.0, z1-1.6, z1+0.6)
        corn.data.materials.append(mats['bronze'])
        # Угловые пилястры
        for sx, sy in [(-1,-1), (-1,1), (1,-1), (1,1)]:
            xp = sx*w/2; yp = sy*d/2
            px0, px1 = (xp, xp+0.8) if sx > 0 else (xp-0.8, xp)
            py0, py1 = (yp, yp+0.8) if sy > 0 else (yp-0.8, yp)
            pil = make_box("Pilaster", px0, px1, py0, py1, z0, z1+0.6)
            pil.data.materials.append(mats['bronze'])
        # Средние вертикальные рёбра на широких блоках
        if w >= 27:
            for s in (-1, 1):
                ribx = make_box("RibX", s*w/2-0.35, s*w/2+0.35, -1.2, 1.2, z0, z1+0.6)
                ribx.data.materials.append(mats['bronze'])
                riby = make_box("RibY", -1.2, 1.2, s*d/2-0.35, s*d/2+0.35, z0, z1+0.6)
                riby.data.materials.append(mats['bronze'])
        Z = z1

    nwin = add_window_bands(main_blocks, mats)
    print("WINDOW PANELS:", nwin)

    top_z = Z

    # Корона: восьмигранные террасы со светящимися стеклами между ярусами
    cz = top_z
    for (rr, hh) in [(10.5, 3.2), (8.8, 3.2), (7.2, 3.2), (5.6, 3.2)]:
        l1 = [(rr*math.cos(math.pi/8 + i*math.pi/4),
               rr*math.sin(math.pi/8 + i*math.pi/4), cz) for i in range(8)]
        l2 = [(rr*0.93*math.cos(math.pi/8 + i*math.pi/4),
               rr*0.93*math.sin(math.pi/8 + i*math.pi/4), cz+hh) for i in range(8)]
        cr = prism_from_loop("Crown", [l1, l2])
        cr.data.materials.append(mats['gold'])
        add_bevel(cr, 0.05)
        band = make_box("CrownGlass", -rr*0.82, rr*0.82, -rr*0.82, rr*0.82, cz+hh, cz+hh+1.3)
        band.data.materials.append(mats['lit'])
        cz += hh + 1.3

    # Шпиль
    sb = make_box("Spire_Base", -2.4, 2.4, -2.4, 2.4, cz, cz+6)
    sb.data.materials.append(mats['metal'])
    mast_pts = [(1.7, cz+6), (1.25, cz+26), (0.85, cz+50), (0.5, cz+74), (0.22, cz+92), (0.0, cz+100)]
    mloops = []
    for (r, zz) in mast_pts:
        mloops.append([(r*math.cos(i*math.pi/4), r*math.sin(i*math.pi/4), zz) for i in range(8)])
    mast = prism_from_loop("Spire_Mast", mloops)
    mast.data.materials.append(mats['metal'])
    for k in range(4):
        rz = cz + 14 + k*16
        bpy.ops.mesh.primitive_torus_add(major_radius=1.6-k*0.3, minor_radius=0.13, location=(0, 0, rz))
        tor = bpy.context.active_object; tor.name = "Antenna_Ring"
        tor.data.materials.append(mats['gold'])
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.95, segments=24, ring_count=16, location=(0, 0, cz+100.8))
    beacon = bpy.context.active_object; beacon.name = "Beacon"
    beacon.data.materials.append(mats['beacon'])
    bpy.ops.object.shade_smooth()

    H = cz + 101.8
    print("TOTAL HEIGHT m:", H)
    return H

# ---------------------------------------------------------------- city

def build_environment(mats, H):
    bpy.ops.mesh.primitive_plane_add(size=1600, location=(0, 0, 0))
    ground = bpy.context.active_object; ground.name = "Ground"
    ground.data.materials.append(mats['ground'])

    random.seed(7)
    for i in range(30):
        ang = random.uniform(0, 2*math.pi)
        dist = random.uniform(95, 520)
        x, y = dist*math.cos(ang), dist*math.sin(ang)
        w, d = random.uniform(18, 48), random.uniform(18, 48)
        h = random.uniform(22, min(H*0.7, 220))
        blk = make_box("City_%d" % i, x-w/2, x+w/2, y-d/2, y+d/2, 0, h)
        blk.data.materials.append(mats['stone'])
        nf = max(1, int(h/4))
        for f in range(nf):
            if random.random() < 0.30:
                side = random.randint(0, 3)
                z0f, z1f = f*4+1, f*4+3
                if side == 0:
                    win = make_box("cw", x+w/2, x+w/2+0.25, y-d/2, y+d/2, z0f, z1f)
                elif side == 1:
                    win = make_box("cw", x-w/2-0.25, x-w/2, y-d/2, y+d/2, z0f, z1f)
                elif side == 2:
                    win = make_box("cw", x-w/2, x+w/2, y+d/2, y+d/2+0.25, z0f, z1f)
                else:
                    win = make_box("cw", x-w/2, x+w/2, y-d/2-0.25, y-d/2, z0f, z1f)
                win.data.materials.append(mats['lit'])

    for (lx, ly) in [(-42, 42), (42, 42), (-42, -42), (42, -42)]:
        pole = make_box("Lamp", lx-0.16, lx+0.16, ly-0.16, ly+0.16, 0, 8)
        pole.data.materials.append(mats['metal'])
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.55, location=(lx, ly, 8.5))
        bulb = bpy.context.active_object
        bulb.data.materials.append(mats['lamp'])
        pt = bpy.data.lights.new("lamp_pt", 'POINT')
        pt.energy = 2500; pt.color = (1.0, 0.7, 0.4); pt.shadow_soft_size = 0.5
        po = bpy.data.objects.new("lamp_l", pt); po.location = (lx, ly, 8.5)
        link_object(po)

# ---------------------------------------------------------------- scene setup

def setup_scene(mats, H):
    sun = bpy.data.lights.new("Moon", 'SUN')
    sun.energy = 0.5; sun.color = (0.6, 0.7, 1.0); sun.angle = math.radians(3)
    so = bpy.data.objects.new("Moon", sun); link_object(so)
    so.rotation_euler = (math.radians(50), math.radians(-10), math.radians(140))

    spot = bpy.data.lights.new("KeySpot", 'SPOT')
    spot.energy = 4_000_000; spot.color = (1.0, 0.72, 0.45)
    spot.spot_size = math.radians(75); spot.shadow_soft_size = 8
    spo = bpy.data.objects.new("KeySpot", spot); link_object(spo)
    spo.location = (-H*0.85, -H*1.0, H*0.5)
    tgt = Vector((0, 0, H*0.55)) - spo.location
    spo.rotation_euler = tgt.to_track_quat('-Z', 'Y').to_euler()

    fill = bpy.data.lights.new("FillBlue", 'AREA')
    fill.energy = 400_000; fill.color = (0.35, 0.5, 1.0); fill.size = 120
    fio = bpy.data.objects.new("FillBlue", fill); link_object(fio)
    fio.location = (H*0.9, H*0.4, H*0.7)
    tgt = Vector((0, 0, H*0.5)) - fio.location
    fio.rotation_euler = tgt.to_track_quat('-Z', 'Y').to_euler()

    # Небо — градиент городских сумерек
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree; nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -0.1
    mr.inputs["From Max"].default_value = 0.45
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.0005, 0.001, 0.002, 1)
    e = ramp.color_ramp.elements.new(0.6); e.color = (0.010, 0.014, 0.045, 1)
    ramp.color_ramp.elements[-1].position = 1.0
    ramp.color_ramp.elements[-1].color = (0.060, 0.028, 0.012, 1)
    bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = 0.7
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    # Камера — героический ракурс снизу (Z-up: целимся через -Z)
    cam_data = bpy.data.cameras.new("Cam"); cam_data.lens = 24
    cam = bpy.data.objects.new("Camera", cam_data); link_object(cam)
    cam.location = (-H*0.95, -H*1.05, H*0.035)
    look = Vector((0, 0, H*0.60)) - cam.location
    cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.camera = cam
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = (Vector((0, 0, H*0.45)) - cam.location).length
    cam_data.dof.aperture_fstop = 4.0

    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons.get('cycles')
    if prefs:
        cp = prefs.preferences
        for dtype in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
            try:
                cp.compute_device_type = dtype
                cp.get_devices()
                if any(dev.type != 'CPU' for dev in cp.devices):
                    for dev in cp.devices: dev.use = True
                    sc.cycles.device = 'GPU'
                    break
                cp.compute_device_type = 'NONE'
            except Exception:
                continue
    sc.cycles.samples = 200
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8
    try:
        sc.view_settings.view_transform = 'AgX'
        sc.view_settings.look = 'AgX - Punchy'
    except Exception:
        sc.view_settings.view_transform = 'Filmic'
    sc.render.resolution_x = 1920
    sc.render.resolution_y = 1080
    sc.view_settings.exposure = 0.8

def do_render(H):
    sc = bpy.context.scene
    cam = bpy.data.objects["Camera"]
    sc.render.filepath = "/workspace/skyscraper/render_night.png"
    bpy.ops.render.render(write_still=True)
    cam.location = (-H*1.5, -H*1.6, H*0.8)
    look = Vector((0, 0, H*0.40)) - cam.location
    cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = 40
    sc.render.filepath = "/workspace/skyscraper/render_hero.png"
    bpy.ops.render.render(write_still=True)

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for lst in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
        for b in list(lst):
            if b.users == 0: lst.remove(b)

# ---------------------------------------------------------------- main

if MODE in ("build", "all"):
    clear_scene()
    mats = build_materials()
    H = build_tower(mats)
    build_environment(mats, H)
    setup_scene(mats, H)
    bpy.ops.wm.save_as_mainfile(filepath="/workspace/skyscraper/skyscraper.blend")
    print("SAVED:", H)

if MODE in ("render", "all"):
    if MODE == "render":
        bpy.ops.wm.open_mainfile(filepath="/workspace/skyscraper/skyscraper.blend")
        H = 372.0
    do_render(H)
    print("RENDER DONE")

print("SCRIPT FINISHED OK")
