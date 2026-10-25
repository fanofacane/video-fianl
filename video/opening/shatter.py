"""用 Blender (bpy) 渲染碎片聚合的 3D 帧序列。

碎片有厚度、3D 翻转、玻璃反光、景深与动态模糊；从画面上方坠落，
底部先落位、逐渐向上补齐，最后一帧拼回完整背景图。
"""
import math
import os
import random

import bpy
from mathutils import Euler, Vector

from ..config import FPS, H, W
from .cuts import PH, PW, cells_from_mask

THICK = 0.03  # 玻璃厚度


def _ease_out(p):
    return 1 - (1 - p) ** 3


def _node_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    return m, nt, nt.nodes.new("ShaderNodeOutputMaterial")


def _face_material(img, back=False):
    """正面显示背景图（自发光，落位后与原图一致），叠加带微起伏的玻璃反光。"""
    m, nt, out = _node_mat("back" if back else "front")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    emit.inputs["Strength"].default_value = 0.35 if back else 1.0
    gloss = nt.nodes.new("ShaderNodeBsdfGlossy")
    gloss.inputs["Roughness"].default_value = 0.03
    gloss.inputs["Color"].default_value = (0.75, 0.85, 1.0, 1)
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 3.0
    nz.inputs["Detail"].default_value = 6.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], gloss.inputs["Normal"])
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    nt.links.new(bump.outputs["Normal"], lw.inputs["Normal"])
    black = nt.nodes.new("ShaderNodeBsdfTransparent")
    black.inputs["Color"].default_value = (0, 0, 0, 1)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lw.outputs["Fresnel"], mix.inputs[0])
    nt.links.new(black.outputs[0], mix.inputs[1])
    nt.links.new(gloss.outputs[0], mix.inputs[2])
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(emit.outputs[0], add.inputs[0])
    nt.links.new(mix.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    return m


def _edge_material():
    """玻璃侧边：银白亮边。"""
    m, nt, out = _node_mat("edge")
    gloss = nt.nodes.new("ShaderNodeBsdfGlossy")
    gloss.inputs["Roughness"].default_value = 0.15
    gloss.inputs["Color"].default_value = (0.8, 0.9, 1.0, 1)
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (0.78, 0.85, 1.0, 1)
    emit.inputs["Strength"].default_value = 1.0
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(gloss.outputs[0], add.inputs[0])
    nt.links.new(emit.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    return m


def _make_shard(name, poly, mats):
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    n = len(poly)
    verts = [(x - cx, y - cy, 0.0) for x, y in poly] + [(x - cx, y - cy, -THICK) for x, y in poly]
    faces = [list(range(n)), list(range(2 * n - 1, n - 1, -1))]
    faces += [[i, i + n, (i + 1) % n + n, (i + 1) % n] for i in range(n)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    for f in me.polygons:
        f.material_index = min(f.index, 2)  # 0=正面 1=背面 2=侧边
        for li in f.loop_indices:
            x, y = poly[me.loops[li].vertex_index % n]
            uv.data[li].uv = ((x + PW / 2) / PW, (y + PH / 2) / PH)
    ob = bpy.data.objects.new(name, me)
    for m in mats:
        ob.data.materials.append(m)
    ob.location = (cx, cy, 0)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _setup_scene(samples, frames):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.fps = FPS
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.view_settings.view_transform = "Standard"  # 落位后颜色与原图一致
    sc.render.image_settings.file_format = "PNG"
    sc.frame_start, sc.frame_end = 1, frames

    # 世界：相机直接看到纯黑；碎片反射到的是有明暗条纹的蓝色环境
    world = bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    wn = world.node_tree
    bg = wn.nodes["Background"]
    nz = wn.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 2.5
    nz.inputs["Detail"].default_value = 4.0
    ramp = wn.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[0].color = (0.004, 0.008, 0.02, 1)
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = (0.12, 0.18, 0.35, 1)
    wn.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    wn.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    lp = wn.nodes.new("ShaderNodeLightPath")
    blk = wn.nodes.new("ShaderNodeBackground")
    blk.inputs["Color"].default_value = (0, 0, 0, 1)
    mix = wn.nodes.new("ShaderNodeMixShader")
    wn.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    wn.links.new(bg.outputs[0], mix.inputs[1])
    wn.links.new(blk.outputs[0], mix.inputs[2])
    wn.links.new(mix.outputs[0], wn.nodes["World Output"].inputs["Surface"])

    # 相机：50mm 正好框住画面板，浅景深让贴近镜头的碎片虚化
    cam_d = PW * 50 / 36
    cd = bpy.data.cameras.new("cam")
    cd.lens = 50
    cd.sensor_fit = "HORIZONTAL"
    cd.dof.use_dof = True
    cd.dof.focus_distance = cam_d
    cd.dof.aperture_fstop = 2.0
    cam = bpy.data.objects.new("cam", cd)
    cam.location = (0, 0, cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam

    # 反光灯放在画面镜像反射范围之外：碎片平躺时看不到倒影，翻转时才闪光
    for loc, size, power, col in [
        ((-34, 20, 12), 12, 30000, (0.8, 0.9, 1.0)),
        ((36, -16, 14), 10, 26000, (0.75, 0.85, 1.0)),
        ((6, 30, 8), 16, 24000, (0.6, 0.75, 1.0)),
    ]:
        ld = bpy.data.lights.new("L", "AREA")
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = size, size * 0.25
        ld.energy = power
        ld.color = col
        lo = bpy.data.objects.new("L", ld)
        lo.location = loc
        lo.rotation_euler = (-Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        lo.visible_camera = False
        sc.collection.objects.link(lo)
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    return sc


def _key(ob, f, loc, rot, visible):
    ob.location, ob.rotation_euler = loc, rot
    ob.scale = (1, 1, 1) if visible else (0, 0, 0)
    for k in ("location", "rotation_euler", "scale"):
        ob.keyframe_insert(k, frame=f)


def render_frames(image, out_dir, cuts=None, frames=60, samples=48, seed=11, only=None):
    """渲染碎片聚合帧到 out_dir/0001.png...；返回每片碎片的落位时间（秒），供音效使用。"""
    sc = _setup_scene(samples, frames)
    img = bpy.data.images.load(os.path.abspath(str(image)))
    mats = [_face_material(img), _face_material(img, back=True), _edge_material()]
    rnd = random.Random(seed)
    lands = []

    # 下坠式聚合：每片从画面上方掉下来落回原位；底部先落位，逐渐向上补齐
    for i, poly in enumerate(cells_from_mask(cuts) if cuts else cells_from_mask()):
        ob = _make_shard(f"s{i}", poly, mats)
        rest = ob.location.copy()
        h = (rest.y + PH / 2) / PH                         # 0=底部, 1=顶部
        fall = (PH / 2 - rest.y) + rnd.uniform(2.0, 6.0)  # 从画面顶部之上开始掉
        land = 28 + h * 17 + rnd.uniform(-2, 2)            # 约 0.93s(底) → 1.5s(顶)
        dur = 12 + fall * 1.3
        start = land - dur
        drift = rnd.uniform(-1.5, 1.5)
        z0 = rnd.uniform(8, 12) if rnd.random() < 0.2 else rnd.uniform(1.5, 6)  # 少数贴近镜头
        rot0 = Vector([rnd.choice([-1, 1]) * rnd.uniform(3.0, 8.0) for _ in range(3)])
        lands.append(land / FPS)
        for f in range(1, frames + 2):
            p = (f - start) / dur
            rem = 1 - _ease_out(min(1.0, max(0.0, p)))
            _key(ob, f, rest + Vector((drift * rem, fall * rem, z0 * rem)), Euler(rot0 * rem), p >= 0)

    # 开头第一下：一片细长碎片侧着身横穿标题，拉出一道亮光
    blade = _make_shard("blade", [(-1.9, -0.06), (1.7, 0.0), (1.9, 0.08), (-0.4, 0.16)], mats)
    for f in range(1, frames + 2):
        p = (f - 5) / 10
        q = min(1, max(0, p))
        rot = (math.radians(70 + 40 * q), math.radians(8), math.radians(-6 + 10 * q))
        _key(blade, f, (-11 + 22 * q, 1.1 + 0.3 * q, 7), rot, 0 <= p <= 1)

    os.makedirs(out_dir, exist_ok=True)
    for f in ([only] if only else range(1, frames + 1)):
        sc.frame_set(f)
        sc.render.filepath = os.path.join(os.path.abspath(str(out_dir)), f"{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        print(f"碎片帧 {f}/{frames}", flush=True)
    return sorted(lands)
