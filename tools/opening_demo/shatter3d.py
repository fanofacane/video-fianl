"""用 Blender (bpy) 渲染 3D 玻璃碎片聚合开场：碎片有厚度、3D 翻转、玻璃反光、景深与动态模糊。

用法: python3 shatter3d.py --image bg.png --out frames_dir [--frames 60] [--samples 48]
输出 frames_dir/0001.png ...（30fps），最后一帧碎片全部落位、还原成背景图。
"""
import argparse, math, os, random
import bpy
from mathutils import Vector, Euler

W_PX, H_PX = 1280, 720
PW, PH = 16.0, 9.0          # 板子尺寸（Blender 单位）
THICK = 0.07
FPS = 30


def clip_poly(poly, a, b, c):
    """保留 a*x + b*y <= c 的部分（Sutherland–Hodgman）。"""
    out = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        fp, fq = a * p[0] + b * p[1] - c, a * q[0] + b * q[1] - c
        if fp <= 0:
            out.append(p)
        if (fp <= 0) != (fq <= 0):
            t = fp / (fp - fq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def voronoi_cells(seed):
    rnd = random.Random(seed)
    pts = []
    gx, gy = 7, 4
    for j in range(gy):
        for i in range(gx):
            pts.append(((i + 0.5 + rnd.uniform(-.4, .4)) / gx * PW - PW / 2,
                        (j + 0.5 + rnd.uniform(-.4, .4)) / gy * PH - PH / 2))
    for _ in range(10):  # 中心区域多切几块小碎片
        pts.append((rnd.uniform(-4, 4), rnd.uniform(-2.2, 2.2)))
    rect = [(-PW / 2, -PH / 2), (PW / 2, -PH / 2), (PW / 2, PH / 2), (-PW / 2, PH / 2)]
    cells = []
    for i, p in enumerate(pts):
        poly = rect
        for j, q in enumerate(pts):
            if i == j:
                continue
            a, b = q[0] - p[0], q[1] - p[1]
            c = (q[0] ** 2 + q[1] ** 2 - p[0] ** 2 - p[1] ** 2) / 2
            poly = clip_poly(poly, a, b, c)
            if not poly:
                break
        if len(poly) >= 3:
            cells.append(poly)
    return cells


def uv_of(x, y):
    return ((x + PW / 2) / PW, (y + PH / 2) / PH)


def make_shard(name, poly, mats):
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    n = len(poly)
    verts = [(x - cx, y - cy, 0.0) for x, y in poly] + [(x - cx, y - cy, -THICK) for x, y in poly]
    faces = [list(range(n)), list(range(2 * n - 1, n - 1, -1))]
    for i in range(n):
        k = (i + 1) % n
        faces.append([i, i + n, k + n, k])
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    for poly_f in me.polygons:
        poly_f.material_index = 0 if poly_f.index == 0 else (1 if poly_f.index == 1 else 2)
        for li in poly_f.loop_indices:
            vi = me.loops[li].vertex_index
            x, y = poly[vi % n]
            uv.data[li].uv = uv_of(x, y)
    ob = bpy.data.objects.new(name, me)
    for m in mats:
        ob.data.materials.append(m)
    ob.location = (cx, cy, 0)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def node_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for nd in list(nt.nodes):
        nt.nodes.remove(nd)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return m, nt, out


def front_material(img, back=False):
    m, nt, out = node_mat("back" if back else "front")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    emit.inputs["Strength"].default_value = 0.35 if back else 1.0
    gloss = nt.nodes.new("ShaderNodeBsdfGlossy")
    gloss.inputs["Roughness"].default_value = 0.05
    gloss.inputs["Color"].default_value = (0.75, 0.85, 1.0, 1)
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.6
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


def edge_material():
    m, nt, out = node_mat("edge")
    gloss = nt.nodes.new("ShaderNodeBsdfGlossy")
    gloss.inputs["Roughness"].default_value = 0.15
    gloss.inputs["Color"].default_value = (0.8, 0.9, 1.0, 1)
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (0.55, 0.7, 1.0, 1)
    emit.inputs["Strength"].default_value = 0.9
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(gloss.outputs[0], add.inputs[0])
    nt.links.new(emit.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    return m


def ease_out(p):
    return 1 - (1 - p) ** 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--only", type=int, default=0, help="只渲染这一帧（调试用）")
    args = ap.parse_args()

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = args.samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = W_PX, H_PX
    sc.render.fps = FPS
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"
    sc.frame_start, sc.frame_end = 1, args.frames

    world = bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    # 相机直接看到的是纯黑；碎片反射到的是蓝色环境
    wn = world.node_tree
    bg = wn.nodes["Background"]
    bg.inputs["Color"].default_value = (0.05, 0.1, 0.25, 1)
    bg.inputs["Strength"].default_value = 1.0
    lp = wn.nodes.new("ShaderNodeLightPath")
    blk = wn.nodes.new("ShaderNodeBackground")
    blk.inputs["Color"].default_value = (0, 0, 0, 1)
    mixw = wn.nodes.new("ShaderNodeMixShader")
    wn.links.new(lp.outputs["Is Camera Ray"], mixw.inputs[0])
    wn.links.new(bg.outputs[0], mixw.inputs[1])
    wn.links.new(blk.outputs[0], mixw.inputs[2])
    wn.links.new(mixw.outputs[0], wn.nodes["World Output"].inputs["Surface"])

    img = bpy.data.images.load(os.path.abspath(args.image))
    mats = [front_material(img), front_material(img, back=True), edge_material()]

    # 相机：50mm，正好框住板子
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

    # 反光用的灯：几块大面光，碎片转到某个角度时闪白
    for loc, rot, size, power, col in [
        ((-14, 9, 16), (math.radians(-30), math.radians(-40), 0), 10, 9000, (0.8, 0.9, 1.0)),
        ((15, -6, 14), (math.radians(25), math.radians(45), 0), 8, 7000, (0.75, 0.85, 1.0)),
        ((0, 14, 6), (math.radians(-70), 0, 0), 14, 6000, (0.6, 0.75, 1.0)),
    ]:
        ld = bpy.data.lights.new("L", "AREA")
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = size, size * 0.25
        ld.energy = power
        ld.color = col
        lo = bpy.data.objects.new("L", ld)
        lo.location = loc
        lo.rotation_euler = rot
        lo.visible_camera = False
        sc.collection.objects.link(lo)

    bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
    rnd = random.Random(11)
    cells = voronoi_cells(5)
    for i, poly in enumerate(cells):
        ob = make_shard(f"s{i}", poly, mats)
        rest = ob.location.copy()
        d = Vector((rest.x + rnd.uniform(-1, 1), rest.y + rnd.uniform(-1, 1), 0))
        if d.length < 0.5:
            d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0))
        d.normalize()
        near = rnd.random() < 0.2  # 少数碎片贴着镜头飞过，景深虚化
        off = d * rnd.uniform(9, 16) + Vector((0, 0, rnd.uniform(14, 19) if near else rnd.uniform(2, 12)))
        rot0 = Vector([rnd.choice([-1, 1]) * rnd.uniform(1.6, 4.4) for _ in range(3)])
        start = rnd.uniform(6, 21)       # 帧
        dur = rnd.uniform(15, 24)
        for f in range(1, args.frames + 2):
            p = min(1.0, max(0.0, (f - start) / dur))
            rem = 1 - ease_out(p)
            ob.location = rest + off * rem
            ob.rotation_euler = Euler(rot0 * rem)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("rotation_euler", frame=f)

    os.makedirs(args.out, exist_ok=True)
    frames = [args.only] if args.only else range(1, args.frames + 1)
    for f in frames:
        sc.frame_set(f)
        sc.render.filepath = os.path.join(os.path.abspath(args.out), f"{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        print("frame", f, flush=True)


if __name__ == "__main__":
    main()
