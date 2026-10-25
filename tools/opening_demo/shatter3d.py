"""用 Blender (bpy) 渲染 3D 玻璃碎片聚合开场：碎片有厚度、3D 翻转、玻璃反光、景深与动态模糊。

用法: python3 shatter3d.py --image bg.png --out frames_dir [--frames 60] [--samples 48]
输出 frames_dir/0001.png ...（30fps），最后一帧碎片全部落位、还原成背景图。
"""
import argparse, math, os, random
import bpy
from mathutils import Vector, Euler

W_PX, H_PX = 1280, 720
PW, PH = 16.0, 9.0          # 板子尺寸（Blender 单位）
THICK = 0.045
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


def jagged_cells(seed, n_pieces=26):
    """像真实碎玻璃一样：用带折角的裂纹线反复切分画面，得到少量大块、细长、尖锐的碎片。"""
    from shapely.geometry import Polygon, LineString
    from shapely.ops import split
    rnd = random.Random(seed)
    pieces = [Polygon([(-PW / 2, -PH / 2), (PW / 2, -PH / 2), (PW / 2, PH / 2), (-PW / 2, PH / 2)])]
    tries = 0
    while len(pieces) < n_pieces and tries < 500:
        tries += 1
        pieces.sort(key=lambda g: g.area)
        big = pieces[-1] if rnd.random() < 0.55 else pieces[rnd.randrange(len(pieces))]
        c = big.representative_point()
        ang = rnd.uniform(0, math.pi)
        dx, dy = math.cos(ang), math.sin(ang)
        L = 30
        k = rnd.randint(3, 5)  # 裂纹折点数
        pts = []
        for i in range(k + 2):
            u = -L + 2 * L * i / (k + 1)
            j = 0 if i in (0, k + 1) else rnd.uniform(-0.6, 0.6)
            pts.append((c.x + dx * u - dy * j, c.y + dy * u + dx * j))
        # 把中段折点压到碎片范围内，让折角真正落在碎片上
        mid = []
        for i in range(k + 2):
            u = (i / (k + 1) - 0.5) * 2 * math.sqrt(big.area) * 1.2
            j = 0 if i in (0, k + 1) else rnd.uniform(-0.45, 0.45)
            mid.append((c.x + dx * u - dy * j, c.y + dy * u + dx * j))
        line = LineString([pts[0]] + mid[1:-1] + [pts[-1]])
        parts = [g for g in split(big, line).geoms if g.geom_type == "Polygon"]
        if len(parts) < 2 or min(g.area for g in parts) < 0.5:
            continue
        pieces.remove(big)
        pieces.extend(parts)
    cells = []
    for g in pieces:
        g = g.simplify(0.01)
        cells.append(list(g.exterior.coords)[:-1])
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
    gloss.inputs["Roughness"].default_value = 0.03
    gloss.inputs["Color"].default_value = (0.75, 0.85, 1.0, 1)
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
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
    emit.inputs["Color"].default_value = (0.78, 0.85, 1.0, 1)
    emit.inputs["Strength"].default_value = 1.3
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
    bg.inputs["Color"].default_value = (0.012, 0.022, 0.06, 1)
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
    # 灯放在画面镜像反射范围之外：板子平躺时看不到灯的倒影，碎片翻转时才闪光
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
    rnd = random.Random(11)
    cells = jagged_cells(12)

    def ease5(p):
        return 1 - (1 - p) ** 4

    for i, poly in enumerate(cells):
        ob = make_shard(f"s{i}", poly, mats)
        rest = ob.location.copy()
        d = Vector((rest.x + rnd.uniform(-1.5, 1.5), rest.y + rnd.uniform(-1.5, 1.5), 0))
        if d.length < 0.5:
            d = Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), 0))
        d.normalize()
        near = rnd.random() < 0.25  # 少数碎片贴着镜头飞过，景深虚化
        off = d * rnd.uniform(5, 12) + Vector((0, 0, rnd.uniform(12, 17) if near else rnd.uniform(3, 10)))
        # 绕各轴多转几圈，翻滚中经常侧对镜头，呈刀片状
        rot0 = Vector([rnd.choice([-1, 1]) * rnd.uniform(3.0, 9.0) for _ in range(3)])
        start = rnd.uniform(7, 16)       # 帧：0.23–0.53s 陆续出现
        dur = rnd.uniform(26, 38)        # 约 1.1–1.8s 落位
        for f in range(1, args.frames + 2):
            p = (f - start) / dur
            if p < 0:
                ob.scale = (0, 0, 0)
                p = 0
            else:
                ob.scale = (1, 1, 1)
            p = min(1.0, p)
            rem = 1 - ease5(p)
            ob.location = rest + off * rem
            ob.rotation_euler = Euler(rot0 * (1 - ease_out(p)))
            for k in ("location", "rotation_euler", "scale"):
                ob.keyframe_insert(k, frame=f)

    # 4) 第一下：一片细长碎片侧着身横穿标题，带一道亮光
    blade = make_shard("blade", [(-1.9, -0.06), (1.7, 0.0), (1.9, 0.08), (-0.4, 0.16)], mats)
    for f in range(1, args.frames + 2):
        p = (f - 5) / 10
        if p < 0 or p > 1:
            blade.scale = (0, 0, 0)
        else:
            blade.scale = (1, 1, 1)
        p = min(1, max(0, p))
        blade.location = (-11 + 22 * p, 1.1 + 0.3 * p, 7)
        blade.rotation_euler = (math.radians(70 + 40 * p), math.radians(8), math.radians(-6 + 10 * p))
        for k in ("location", "rotation_euler", "scale"):
            blade.keyframe_insert(k, frame=f)

    os.makedirs(args.out, exist_ok=True)
    frames = [args.only] if args.only else range(1, args.frames + 1)
    for f in frames:
        sc.frame_set(f)
        sc.render.filepath = os.path.join(os.path.abspath(args.out), f"{f:04d}.png")
        bpy.ops.render.render(write_still=True)
        print("frame", f, flush=True)


if __name__ == "__main__":
    main()
