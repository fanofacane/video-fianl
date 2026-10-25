"""用 Blender (bpy) 渲染 3D 玻璃碎片聚合开场：碎片有厚度、3D 翻转、玻璃反光、景深与动态模糊。

用法: python3 shatter3d.py --image bg.png --out frames_dir [--frames 60] [--samples 48]
输出 frames_dir/0001.png ...（30fps），最后一帧碎片全部落位、还原成背景图。
"""
import argparse, math, os, random
import bpy
from mathutils import Vector, Euler

W_PX, H_PX = 1280, 720
PW, PH = 16.0, 9.0          # 板子尺寸（Blender 单位）
THICK = 0.03
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


def _bent(p0, p1, bend, n=8, jag=0.0, rnd=None):
    """p0→p1 的微弯折线，模拟玻璃贝壳状裂纹。"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L
    pts = []
    for i in range(n + 1):
        u = i / n
        off = bend * 4 * u * (1 - u) + (rnd.uniform(-jag, jag) if (rnd and 0 < i < n) else 0)
        pts.append((p0[0] + dx * u + nx * off, p0[1] + dy * u + ny * off))
    return pts


def radial_cells(seed, n_rays=10):
    """中心一块大碎片托住标题，裂纹从中心向外放射，外圈碎片逐渐变小。"""
    from shapely.geometry import Polygon, LineString, box
    from shapely.ops import polygonize, unary_union
    rnd = random.Random(seed)
    cx, cy = 0.0, 0.9                       # 标题位置附近（画面中心略偏上）
    # 中心大碎片：不规则多边形，每条边微弯
    k = 7
    ring = []
    angs = sorted(rnd.uniform(0, 2 * math.pi) for _ in range(k))
    corners = [(cx + math.cos(a) * 3.9 * rnd.uniform(0.85, 1.1), cy + math.sin(a) * 2.3 * rnd.uniform(0.85, 1.1)) for a in angs]
    for i in range(k):
        seg = _bent(corners[i], corners[(i + 1) % k], rnd.uniform(-0.25, 0.25))
        ring.extend(seg[:-1])
    center = Polygon(ring).buffer(0)
    lines = [LineString(list(center.exterior.coords))]
    # 放射裂纹：从中心碎片边缘一直延伸到画面外
    base = rnd.uniform(0, 2 * math.pi)
    for i in range(n_rays):
        a = base + i * 2 * math.pi / n_rays + rnd.uniform(-0.18, 0.18)
        p0 = (cx + math.cos(a) * 2.0, cy + math.sin(a) * 1.2)
        p1 = (cx + math.cos(a) * 14, cy + math.sin(a) * 14)
        lines.append(LineString(_bent(p0, p1, rnd.uniform(-0.6, 0.6), n=10, jag=0.08, rnd=rnd)))
    # 外圈环形裂纹，把外围切得更碎
    for rx, ry in [(6.3, 3.6)]:
        pts = []
        for i in range(25):
            a = i / 24 * 2 * math.pi
            r = rnd.uniform(0.9, 1.1)
            pts.append((cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r))
        lines.append(LineString(pts))
    frame = box(-PW / 2, -PH / 2, PW / 2, PH / 2)
    lines.append(frame.exterior)
    faces = [g for g in polygonize(unary_union(lines)) if frame.contains(g.representative_point())]
    pieces = []
    for g in faces:
        g = g.intersection(frame)
        if g.area < 0.05:
            continue
        if g.geom_type != "Polygon":
            continue
        pieces.append(g)
    # 太细碎的合并给相邻块，避免出现碎屑
    merged = True
    while merged:
        merged = False
        pieces.sort(key=lambda g: g.area)
        if pieces[0].area < 0.35:
            small = pieces.pop(0)
            best = max(pieces, key=lambda g: g.intersection(small.buffer(0.02)).area)
            pieces.remove(best)
            u = best.union(small)
            pieces.append(u if u.geom_type == "Polygon" else best)
            merged = True
    return [list(g.simplify(0.005).exterior.coords)[:-1] for g in pieces]


def extract_red_lines(src, out_mask):
    """从手绘标注图里只提取红色裂纹线，存成黑底白线的 1280x720 遮罩。"""
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(src).convert("RGB").resize((W_PX, H_PX), Image.LANCZOS)).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    red = (r > 170) & (g < 120) & (b < 120) & (r - g > 80)
    Image.fromarray((red * 255).astype(np.uint8)).save(out_mask)


def close_line_gaps(lines, max_ext=140, back=18):
    """手绘裂纹线的末端往往差一点没碰到别的线或画面边缘。
    把每个线头顺着走向延长，碰到其他线或边缘就停，让每块区域真正封闭。"""
    import cv2
    import numpy as np
    from skimage.morphology import skeletonize
    h, w = lines.shape
    # 去掉零星噪点（例如字幕描边被误识别的小点）
    n, lab, stats, _ = cv2.connectedComponentsWithStats(lines, connectivity=8)
    keep = np.zeros_like(lines)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= 120:
            keep[lab == i] = 1
    sk = skeletonize(keep > 0).astype(np.uint8)
    nb = cv2.filter2D(sk, -1, np.ones((3, 3), np.float32), borderType=cv2.BORDER_CONSTANT) - sk
    ends = np.argwhere((sk == 1) & (nb == 1))
    out = keep.copy()
    _, sklab = cv2.connectedComponents(sk, connectivity=8)
    for y, x in ends:
        # 用线头附近同一条线上的点估计走向
        y0, y1, x0, x1 = max(0, y - back), min(h, y + back + 1), max(0, x - back), min(w, x + back + 1)
        win = np.argwhere(sklab[y0:y1, x0:x1] == sklab[y, x]) + [y0, x0]
        if len(win) < 4:
            continue
        d = np.array([y, x], float) - win.mean(0)
        if np.linalg.norm(d) < 1e-3:
            continue
        d /= np.linalg.norm(d)
        last = (x, y)
        for t in range(3, max_ext):
            py, px = int(round(y + d[0] * t)), int(round(x + d[1] * t))
            if px < 0 or py < 0 or px >= w or py >= h:
                last = (min(max(px, 0), w - 1), min(max(py, 0), h - 1))
                cv2.line(out, (int(x), int(y)), last, 1, 2)
                break
            if t > 6 and keep[py, px] and sklab[py, px] != sklab[y, x]:
                cv2.line(out, (int(x), int(y)), (px, py), 1, 2)
                break
            if t > 12 and keep[py, px]:
                cv2.line(out, (int(x), int(y)), (px, py), 1, 2)
                break
    return out


def cells_from_mask(mask_path, min_area_px=1500):
    """按遮罩里的白线把画面分区，每个封闭区域就是一块碎片。"""
    import cv2
    import numpy as np
    m = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    m = cv2.resize(m, (W_PX, H_PX), interpolation=cv2.INTER_NEAREST)
    lines = close_line_gaps((m > 127).astype(np.uint8))
    lines = cv2.dilate(lines, np.ones((5, 5), np.uint8))
    free = (1 - lines).astype(np.uint8)
    n, lab = cv2.connectedComponents(free, connectivity=4)
    markers = np.zeros((H_PX, W_PX), np.int32)
    k = 0
    for i in range(1, n):
        if (lab == i).sum() >= min_area_px:
            k += 1
            markers[lab == i] = k
    # 用分水岭把线条像素分给相邻区域，碎片之间无缝拼合
    ws = cv2.watershed(np.zeros((H_PX, W_PX, 3), np.uint8), markers.copy())
    for _ in range(3):  # 分水岭留下的边界像素归给邻近区域
        hole = ws <= 0
        if not hole.any():
            break
        grown = cv2.dilate(np.where(hole, 0, ws).astype(np.float32), np.ones((3, 3), np.uint8)).astype(np.int32)
        ws = np.where(hole, grown, ws)
    cells = []
    for i in range(1, k + 1):
        reg = (ws == i).astype(np.uint8)
        cs, _ = cv2.findContours(reg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cs:
            continue
        c = max(cs, key=cv2.contourArea)
        c = cv2.approxPolyDP(c, 2.0, True)[:, 0, :]
        if len(c) < 3:
            continue
        # 像素坐标 → 板子坐标（y 轴向上）
        cells.append([(x / W_PX * PW - PW / 2, PH / 2 - y / H_PX * PH) for x, y in c][::-1])
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
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 3.0
    nz.inputs["Detail"].default_value = 6.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    nt.links.new(nz.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], gloss.inputs["Normal"])
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    nt.links.new(bump.outputs["Normal"], lw.inputs["Normal"])
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
    emit.inputs["Strength"].default_value = 1.0
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
    ap.add_argument("--cuts", default="", help="裂纹遮罩图（黑底白线）；给了就按它切碎片，否则自动放射状切分")
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
    wnz = wn.nodes.new("ShaderNodeTexNoise")
    wnz.inputs["Scale"].default_value = 2.5
    wnz.inputs["Detail"].default_value = 4.0
    ramp = wn.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[0].color = (0.004, 0.008, 0.02, 1)
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = (0.12, 0.18, 0.35, 1)
    wn.links.new(wnz.outputs["Fac"], ramp.inputs["Fac"])
    wn.links.new(ramp.outputs["Color"], bg.inputs["Color"])
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
    cells = cells_from_mask(args.cuts) if args.cuts else radial_cells(11)

    def ease5(p):
        return 1 - (1 - p) ** 4

    # 下坠式聚合：每片从画面上方掉下来落到原位；底部先落位，逐渐向上补齐，顶部最后
    # 下坠式聚合：每片从画面上方掉下来落到原位；底部先落位，逐渐向上补齐，顶部最后
    for i, poly in enumerate(cells):
        ob = make_shard(f"s{i}", poly, mats)
        rest = ob.location.copy()
        h = (rest.y + PH / 2) / PH                     # 0=底部, 1=顶部
        fall = (PH / 2 - rest.y) + rnd.uniform(2.0, 6.0)  # 从画面顶部之上开始掉
        land = 28 + h * 17 + rnd.uniform(-2, 2)        # 约 0.93s(底) → 1.5s(顶) 落位
        dur = 12 + fall * 1.3
        start = land - dur
        drift = rnd.uniform(-1.5, 1.5)
        near = rnd.random() < 0.2  # 少数碎片离镜头很近，景深虚化
        z0 = rnd.uniform(8, 12) if near else rnd.uniform(1.5, 6)
        rot0 = Vector([rnd.choice([-1, 1]) * rnd.uniform(3.0, 8.0) for _ in range(3)])
        for f in range(1, args.frames + 2):
            p = (f - start) / dur
            if p < 0:
                ob.scale = (0, 0, 0)
                p = 0
            else:
                ob.scale = (1, 1, 1)
            p = min(1.0, p)
            rem = 1 - ease_out(p)                       # 前段快速下落，末段减速落位
            ob.location = rest + Vector((drift * rem, fall * rem, z0 * rem))
            ob.rotation_euler = Euler(rot0 * rem)
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
