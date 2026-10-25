"""复刻参考视频的开场手法（原创画面与文案）：
玻璃碎片聚合 → 冷色夜景 + 主题大标题 → 提亮溶解 → 米色纸纹拼贴，黄色中英双语字幕。

用法: python3 render.py --fonts FONT_DIR --out out.mp4
FONT_DIR 需要: NotoSerifSC-Black.otf, MaShanZheng.ttf
"""
import argparse, math, os, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, DUR = 1280, 720, 30, 10.5
rng = np.random.default_rng(7)

TITLE = "独处的能力"
SUBS = [  # (开始, 结束, 中文, 英文)
    (0.25, 1.10, "一个人越能独处", "The better you can be alone,"),
    (1.10, 2.50, "就越不怕失去", "the less you fear losing."),
    (2.50, 5.00, "能安静陪伴自己的人往往更自由", "Those who keep themselves company are often freer."),
    (5.00, 6.20, "不是生活上的自由", "Not freedom in how you live,"),
    (6.20, 7.50, "而是内心不再依附他人", "but a heart that no longer clings to others."),
    (7.50, 9.50, "真正的陪伴从来不是填补空缺", "True company never fills a void,"),
    (9.50, 10.6, "而是一个人本身就足够完整", "it comes from being whole on your own."),
]
WATERMARK = "@示例账号"


def ease_out(p):
    return 1 - (1 - p) ** 3


def smooth(a, b, t):
    p = min(1.0, max(0.0, (t - a) / (b - a)))
    return p * p * (3 - 2 * p)


# ---------- 画面素材 ----------
def night_scene():
    y = np.linspace(0, 1, H)[:, None]
    top, mid = np.array([8, 16, 40]), np.array([22, 48, 92])
    sky = top + (mid - top) * (y ** 1.3)[..., None]
    img = np.broadcast_to(sky, (H, W, 3)).copy()
    hz = int(H * 0.76)
    sea_y = np.linspace(0, 1, H - hz)[:, None, None]
    img[hz:] = np.array([30, 52, 86]) * (1 - sea_y) + np.array([14, 18, 28]) * sea_y
    # 浪花
    for i in range(14):
        yy = hz + 6 + i * 3 + rng.integers(0, 3)
        xs = np.arange(W)
        a = 0.25 * (1 - i / 14) * (0.5 + 0.5 * np.sin(xs / (40 + 9 * i) + i))
        img[yy] = img[yy] * (1 - a[:, None]) + np.array([150, 175, 210]) * a[:, None]
    shore = int(H * 0.84)
    k = np.clip((np.arange(H) - shore + 20) / 40, 0, 1)[:, None, None] * 0.45
    img = img * (1 - k) + np.array([20, 20, 26]) * k
    im = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    for _ in range(90):  # 星
        x, yy = rng.integers(0, W), rng.integers(0, hz - 60)
        b = int(rng.integers(90, 200))
        d.point((x, yy), fill=(b, b, min(255, b + 30)))
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((610 - 70, 140 - 70, 610 + 70, 140 + 70), fill=90)
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    im = Image.composite(Image.new("RGB", (W, H), (150, 170, 210)), im, glow)
    d = ImageDraw.Draw(im)
    d.ellipse((594, 124, 626, 156), fill=(232, 236, 240))
    d.ellipse((604, 120, 640, 156), fill=(28, 44, 82))  # 月牙
    # 远处孤独人影
    fx, fy = 640, shore + 18
    d.ellipse((fx - 5, fy - 62, fx + 5, fy - 50), fill=(10, 10, 14))
    d.polygon([(fx - 8, fy - 50), (fx + 8, fy - 50), (fx + 10, fy - 14), (fx - 10, fy - 14)], fill=(10, 10, 14))
    d.rectangle((fx - 6, fy - 14, fx - 2, fy), fill=(10, 10, 14))
    d.rectangle((fx + 2, fy - 14, fx + 6, fy), fill=(10, 10, 14))
    return im


def paper_texture():
    base = np.array([238, 232, 219], float)
    low = np.array(Image.fromarray(rng.integers(0, 255, (18, 32), dtype=np.uint8)).resize((W, H), Image.BICUBIC), float)
    fine = rng.normal(0, 6, (H, W))
    v = (low - 128) / 128 * 6 + fine
    img = base + v[..., None] * np.array([1, 1, 0.9])
    for _ in range(40):  # 纤维
        x, y = rng.integers(0, W), rng.integers(0, H)
        L = rng.integers(10, 40)
        ang = rng.uniform(0, math.pi)
        for k in range(L):
            xx, yy = int(x + k * math.cos(ang)), int(y + k * math.sin(ang))
            if 0 <= xx < W and 0 <= yy < H:
                img[yy, xx] -= 14
    return Image.fromarray(img.clip(0, 255).astype(np.uint8))


def cutout(rgba, border=8, color=(255, 255, 255), shadow=True):
    """给抠图加剪纸描边和投影。"""
    pad = border + 24
    src = Image.new("RGBA", (rgba.width + 2 * pad, rgba.height + 2 * pad))
    src.paste(rgba, (pad, pad), rgba)
    a = src.split()[3]
    grown = a.filter(ImageFilter.MaxFilter(border * 2 + 1)).filter(ImageFilter.GaussianBlur(1.2))
    grown = grown.point(lambda v: 255 if v > 100 else 0)
    out = Image.new("RGBA", src.size)
    if shadow:
        sh = grown.filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * 0.35))
        out.paste((40, 30, 20, 255), (5, 7), sh)
    out.paste(color + (255,), (0, 0), grown)
    out.alpha_composite(src)
    return out


def birdcage():
    s = Image.new("RGBA", (300, 260))
    d = ImageDraw.Draw(s)
    gold = (176, 128, 54, 255)
    cx = 120
    d.arc((cx - 80, 30, cx + 80, 190), 180, 360, fill=gold, width=6)
    for x in range(cx - 80, cx + 81, 20):
        top = 110 - math.sqrt(max(0, 80 ** 2 - (x - cx) ** 2))
        d.line((x, top, x, 220), fill=gold, width=4)
    d.rectangle((cx - 90, 216, cx + 90, 232), fill=(120, 80, 34, 255))
    d.ellipse((cx - 8, 14, cx + 8, 32), outline=gold, width=4)
    d.polygon([(cx + 40, 140), (cx + 92, 118), (cx + 92, 200), (cx + 40, 205)], fill=(232, 220, 196, 255), outline=gold)
    for bx, by, k in [(230, 60, 1.0), (262, 30, 0.8), (205, 26, 0.6)]:  # 飞出的鸟
        d.line((bx - 16 * k, by, bx, by + 10 * k, bx + 16 * k, by), fill=(40, 40, 50, 255), width=4, joint="curve")
    return cutout(s, border=7)


def figure():
    """复古印刷感的人物背影剪影。"""
    s = Image.new("RGBA", (300, 470))
    d = ImageDraw.Draw(s)
    coat = (32, 36, 52, 255)
    d.ellipse((115, 30, 185, 112), fill=(52, 38, 30, 255))  # 头发
    d.polygon([(118, 80), (182, 80), (196, 150), (104, 150)], fill=(52, 38, 30, 255))
    d.rounded_rectangle((60, 120, 240, 440), radius=60, fill=coat)
    d.polygon([(60, 300), (240, 300), (262, 465), (38, 465)], fill=coat)
    d.line((150, 140, 150, 460), fill=(22, 24, 36, 255), width=3)
    a = np.array(s).astype(float)
    dots = np.zeros(a.shape[:2])  # 网点质感
    dots[::4, ::4] = 1
    m = a[..., 3] > 0
    a[..., :3][m] += (rng.normal(0, 10, m.sum())[:, None] + dots[m][:, None] * 18)
    s = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    return cutout(s, border=12, color=(52, 92, 168))


def flower_patch():
    w, h = 760, 520
    im = Image.fromarray(np.clip(np.array([88, 118, 70]) + rng.normal(0, 14, (h, w, 3)), 0, 255).astype(np.uint8))
    im = im.filter(ImageFilter.GaussianBlur(2))
    d = ImageDraw.Draw(im)
    for _ in range(70):
        x, y, r = rng.integers(0, w), rng.integers(0, h), rng.integers(14, 30)
        col = (182, 170, 236) if rng.random() < 0.6 else (246, 246, 240)
        for k in range(12):
            ang = k / 12 * 2 * math.pi + rng.uniform(-.1, .1)
            ex, ey = x + math.cos(ang) * r * 0.65, y + math.sin(ang) * r * 0.65
            d.ellipse((ex - r * 0.42, ey - r * 0.18 - 2, ex + r * 0.42, ey + r * 0.18 + 2), fill=col)
        d.ellipse((x - r * .25, y - r * .25, x + r * .25, y + r * .25), fill=(230, 180, 40))
    # 撕纸边
    pts = []
    for i in range(41):
        pts.append((i / 40 * w, rng.uniform(0, 14)))
    for i in range(31):
        pts.append((w - rng.uniform(0, 14), i / 30 * h))
    for i in range(41):
        pts.append(((40 - i) / 40 * w, h - rng.uniform(0, 14)))
    for i in range(31):
        pts.append((rng.uniform(0, 14), (30 - i) / 30 * h))
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    im.putalpha(m)
    return cutout(im, border=6, color=(246, 242, 232))


def comp(canvas, im, x, y):
    """带边界裁剪的 alpha 合成。"""
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + im.width), min(H, y + im.height)
    if x1 <= x0 or y1 <= y0:
        return
    canvas.alpha_composite(im.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


# ---------- 碎片 ----------
def make_shards(scene, n=46):
    gx, gy = 8, 5
    pts = []
    for j in range(gy + 1):
        for i in range(gx + 1):
            pts.append(((i + rng.uniform(-.4, .4)) / gx * W, (j + rng.uniform(-.4, .4)) / gy * H))
    pts = np.array(pts[:n] + [(rng.uniform(300, 980), rng.uniform(150, 560)) for _ in range(10)])
    ys, xs = np.mgrid[0:H:2, 0:W:2]
    dist = (xs[..., None] - pts[:, 0]) ** 2 + (ys[..., None] - pts[:, 1]) ** 2
    lab = np.array(Image.fromarray(dist.argmin(-1).astype(np.uint8)).resize((W, H), Image.NEAREST))
    sc = np.array(scene.convert("RGBA"))
    shards = []
    for k in range(len(pts)):
        m = lab == k
        if m.sum() < 200:
            continue
        yy, xx = np.where(m)
        x0, x1, y0, y1 = xx.min(), xx.max() + 1, yy.min(), yy.max() + 1
        crop = sc[y0:y1, x0:x1].copy()
        crop[..., 3] = m[y0:y1, x0:x1] * 255
        mask = Image.fromarray(crop[..., 3])
        edge = np.array(mask) - np.array(mask.filter(ImageFilter.MinFilter(5)))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        dirv = np.array([cx - W / 2, cy - H / 2]) + rng.normal(0, 60, 2)
        dirv /= np.linalg.norm(dirv) + 1e-6
        shards.append(dict(
            img=crop, edge=edge, pos=(cx, cy), w=x1 - x0, h=y1 - y0,
            off=dirv * rng.uniform(380, 900), rot=rng.uniform(-110, 110),
            scale=rng.uniform(1.4, 2.4), start=rng.uniform(0.22, 0.75), dur=rng.uniform(0.55, 0.8),
            phase=rng.uniform(0, 6.28),
        ))
    return shards, lab


def draw_shards(canvas, shards, t):
    items = []
    for s in shards:
        p = (t - s["start"]) / s["dur"]
        if p <= 0:
            continue
        p = min(p, 1.0)
        e = ease_out(p)
        items.append((1 - e, s, e, p))
    items.sort(key=lambda x: x[0])  # 已落位的先画，仍在飞的（更近）后画
    for rem, s, e, p in items:
        img = s["img"].astype(float)
        rot = s["rot"] * rem
        flash = rem * max(0.0, math.sin(math.radians(rot) * 3 + s["phase"])) ** 6 * 1.6
        tint = np.array([0.75, 0.85, 1.25])
        rgb = img[..., :3] * (1 - rem * 0.5) + img[..., :3] * tint * rem * 0.5 + rem * 40
        rgb = rgb + flash * 160
        edge_a = s["edge"][..., None] / 255.0 * min(1.0, rem * 2.5)
        rgb = rgb * (1 - edge_a) + 235 * edge_a
        alpha = img[..., 3] * min(1.0, p / 0.25)
        im = Image.fromarray(np.dstack([rgb.clip(0, 255), alpha]).astype(np.uint8), "RGBA")
        k = 1 + (s["scale"] - 1) * rem
        if abs(k - 1) > 1e-3:
            im = im.resize((max(1, int(s["w"] * k)), max(1, int(s["h"] * k))), Image.BILINEAR)
        if abs(rot) > 0.05:
            im = im.rotate(rot, resample=Image.BILINEAR, expand=True)
        cx = s["pos"][0] + s["off"][0] * rem
        cy = s["pos"][1] + s["off"][1] * rem
        comp(canvas, im, int(cx - im.width / 2), int(cy - im.height / 2))


def crack_layer(lab):
    e = (lab[:, 1:] != lab[:, :-1])
    m = np.zeros((H, W), np.uint8)
    m[:, 1:][e] = 255
    e2 = (lab[1:] != lab[:-1])
    m[1:][e2] = 255
    return Image.fromarray(m).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.8))


# ---------- 文字 ----------
def text_layer(fonts):
    zh = ImageFont.truetype(fonts["serif"], 36)
    en = ImageFont.truetype(fonts["en"], 21)
    layers = []
    for a, b, c, e in SUBS:
        im = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(im)
        sh = Image.new("RGBA", (W, H))
        sd = ImageDraw.Draw(sh)
        sd.text((W / 2 + 2, 628 + 3), c, font=zh, anchor="mm", fill=(0, 0, 0, 200), stroke_width=4, stroke_fill=(0, 0, 0, 200))
        sd.text((W / 2 + 1, 668 + 2), e, font=en, anchor="mm", fill=(0, 0, 0, 200))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(2)))
        d.text((W / 2, 628), c, font=zh, anchor="mm", fill=(255, 212, 0), stroke_width=3, stroke_fill=(70, 34, 0))
        d.text((W / 2, 668), e, font=en, anchor="mm", fill=(250, 250, 250), stroke_width=1, stroke_fill=(20, 20, 20))
        layers.append((a, b, im))
    wm = Image.new("RGBA", (W, H))
    ImageDraw.Draw(wm).text((W / 2, 24), WATERMARK, font=ImageFont.truetype(fonts["serif"], 24), anchor="mm", fill=(200, 160, 90, 110))
    return layers, wm


def title_chars(fonts):
    f = ImageFont.truetype(fonts["title"], 96)
    total = f.getlength(TITLE)
    x = W / 2 - total / 2
    out = []
    for ch in TITLE:
        out.append((x + f.getlength(ch) / 2, ch))
        x += f.getlength(ch)
    return f, out


def draw_title(canvas, f, chars, t):
    if t < 0.1 or t > 4.4:
        return
    fade_out = 1 - smooth(4.0, 4.35, t)
    whiten = smooth(0.3, 1.2, t)
    lay = Image.new("RGBA", (W, H))
    sh = Image.new("RGBA", (W, H))
    for i, (x, ch) in enumerate(chars):
        a = smooth(0.1 + i * 0.07, 0.4 + i * 0.07, t) * fade_out
        if a <= 0:
            continue
        g = int(120 + 135 * whiten)
        ImageDraw.Draw(sh).text((x + 3, 262 + 4), ch, font=f, anchor="mm", fill=(0, 0, 0, int(150 * a)))
        ImageDraw.Draw(lay).text((x, 262), ch, font=f, anchor="mm", fill=(g, g, min(255, g + 8), int(255 * a)))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(4)))
    canvas.alpha_composite(lay)


# ---------- 音频 ----------
def make_audio(path, shards):
    sr = 44100
    n = int(DUR * sr)
    t = np.arange(n) / sr
    pad = sum(np.sin(2 * np.pi * f * t + i) for i, f in enumerate([110, 164.8, 220, 261.6, 329.6]))
    pad *= 0.045 * np.minimum(1, t / 1.5) * (1 + 0.15 * np.sin(2 * np.pi * 0.25 * t))
    noise = np.random.default_rng(1).normal(0, 1, n)
    k = np.ones(40) / 40
    whoosh = np.convolve(noise, k, "same") - np.convolve(noise, np.ones(400) / 400, "same")
    env = np.exp(-((t - 0.6) / 0.35) ** 2) * 0.9 + np.exp(-((t - 5.0) / 0.4) ** 2) * 0.5
    sig = pad + whoosh * env * 0.6
    for s in shards:  # 玻璃落位的清脆声
        t0 = s["start"] + s["dur"] * 0.85
        f = rng.uniform(2200, 5200)
        m = t >= t0
        tt = t[m] - t0
        sig[m] += 0.05 * np.sin(2 * np.pi * f * tt) * np.exp(-tt * 18)
    sig = np.tanh(sig * 1.3) * 0.8
    pcm = (np.stack([sig, sig], 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--out", default="opening_demo.mp4")
    ap.add_argument("--shatter-frames", default="", help="shatter3d.py 渲染出的 3D 碎片帧目录；不给则用 2D 碎片")
    args = ap.parse_args()
    fonts = dict(
        serif=os.path.join(args.fonts, "NotoSerifSC-Black.otf"),
        title=os.path.join(args.fonts, "MaShanZheng.ttf"),
        en="/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    )
    scene = night_scene()
    paper = paper_texture().convert("RGBA")
    cage, fig, flowers = birdcage(), figure(), flower_patch()
    shards, lab = make_shards(scene)
    cracks = crack_layer(lab)
    subs, wm = text_layer(fonts)
    tf, tchars = title_chars(fonts)
    scene_rgba = scene.convert("RGBA")
    washed = Image.blend(scene, Image.new("RGB", (W, H), (205, 210, 218)), 0.7).convert("RGBA")

    wav = args.out + ".wav"
    make_audio(wav, shards)
    ff = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "-", "-i", wav, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", args.out,
    ], stdin=subprocess.PIPE)
    land = max(s["start"] + s["dur"] for s in shards)
    s3d = sorted(os.listdir(args.shatter_frames)) if args.shatter_frames else []
    if s3d:
        land = len(s3d) / FPS
    for fi in range(int(DUR * FPS)):
        t = fi / FPS
        if t < land:
            canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
            if s3d:
                canvas = Image.open(os.path.join(args.shatter_frames, s3d[fi])).convert("RGBA")
                # 最后几帧淡入 2D 背景，保证接缝无跳变
                canvas = Image.blend(canvas, scene_rgba, smooth(land - 0.3, land, t))
            else:
                draw_shards(canvas, shards, t)
                ca = 0.3 * smooth(0.8, 1.1, t)
                canvas.paste((220, 230, 255), (0, 0), cracks.point(lambda v: int(v * ca)))
        elif t < 5.6:
            z = 1 + 0.035 * smooth(land, 5.0, t)  # 慢推镜
            sw, shh = int(W / z), int(H / z)
            canvas = scene_rgba.crop(((W - sw) // 2, (H - shh) // 2, (W - sw) // 2 + sw, (H - shh) // 2 + shh)).resize((W, H), Image.BILINEAR)
            ca = 0 if s3d else 0.3 * (1 - smooth(land, land + 0.5, t))
            if ca > 0:
                canvas.paste((220, 230, 255), (0, 0), cracks.point(lambda v: int(v * ca)))
            canvas = Image.blend(canvas, washed, smooth(4.8, 5.25, t))
            canvas = Image.blend(canvas, paper, smooth(5.15, 5.6, t))
        else:
            canvas = paper.copy()
        if t >= 5.4:
            if t >= 9.45:  # 撕纸花丛弹入
                p = smooth(9.45, 9.7, t)
                k = 0.9 + 0.1 * ease_out(min(1, (t - 9.45) / 0.25))
                fl = flowers.resize((int(flowers.width * k), int(flowers.height * k)))
                fl.putalpha(fl.split()[3].point(lambda v: int(v * p)))
                canvas.alpha_composite(fl, (int(W / 2 - fl.width / 2), int(H / 2 - fl.height / 2) - 10))
            a = smooth(5.4, 5.9, t)
            c = cage.copy(); c.putalpha(c.split()[3].point(lambda v: int(v * a)))
            canvas.alpha_composite(c, (W - c.width - 70, 40 + int(4 * math.sin(t * 1.5))))
            if t >= 6.1:
                a = smooth(6.1, 6.6, t)
                g = fig.copy(); g.putalpha(g.split()[3].point(lambda v: int(v * a)))
                canvas.alpha_composite(g, (W // 2 - g.width // 2, H - g.height + 30))
        draw_title(canvas, tf, tchars, t)
        canvas.alpha_composite(wm)
        for a, b, im in subs:
            if a <= t < b:
                canvas.alpha_composite(im)
        ff.stdin.write(canvas.convert("RGB").tobytes())
    ff.stdin.close()
    ff.wait()
    os.remove(wav)
    print("done", args.out)


if __name__ == "__main__":
    main()
