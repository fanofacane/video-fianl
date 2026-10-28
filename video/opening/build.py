"""碎片开场一键生成：配置 JSON → 开场 mp4。

    python3 -m video.opening.build output/<name>/opening_gen.json            # 出视频
    python3 -m video.opening.build output/<name>/opening_gen.json --shots    # 只出关键帧截图，先确认效果

流程：背景图（没有就按 prompt 生图）→ Blender 渲染碎片帧（按内容缓存，改文字不用重渲）
     → 叠加标题 / 水印 / 双语字幕 → 输出 output/<name>/opening.mp4（无声，配乐与口播在整片阶段加）
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from PIL import Image

from ..config import WATERMARK, FPS, H, OUTPUT, ROOT, W, check_fonts
from ..text import Subtitles, Title, smooth, watermark_layer
from .cuts import DEFAULT_MASK

SHATTER_FRAMES = 60   # 碎片段 2 秒；约 1.5 秒全部落位
SHATTER_VERSION = "v2"  # 改动 shatter.py 的效果后加一，旧缓存自动失效


def _resolve_background(cfg, work):
    bg = cfg.get("background", {})
    src = Path(bg["image"]) if bg.get("image") else None
    if src and not src.is_absolute():
        src = ROOT / src
    if not src or not src.exists():
        if not bg.get("prompt"):
            raise SystemExit("配置里需要 background.image（已有图片）或 background.prompt（生图提示词）")
        src = work / "background.png"
        if not src.exists():
            from ..imagegen import generate
            generate(bg["prompt"], src, size="1536x864", background="opaque")
    out = work / "background_1280.png"
    Image.open(src).convert("RGB").resize((W, H), Image.LANCZOS).save(out)
    return out


def _shatter_frames(bg, cuts, samples, only=None):
    """渲染（或复用缓存的）碎片帧，返回 (帧目录, 落位时间列表)。"""
    key = hashlib.sha1()
    for p in (bg, cuts):
        key.update(Path(p).read_bytes())
    key.update(f"{SHATTER_VERSION}-{samples}-{SHATTER_FRAMES}".encode())
    d = OUTPUT / "cache" / f"shatter_{key.hexdigest()[:12]}"
    meta = d / "meta.json"
    if not only and meta.exists() and len(list(d.glob("*.png"))) == SHATTER_FRAMES:
        print(f"复用缓存的碎片帧 {d}")
        return d, json.loads(meta.read_text())["lands"]
    from .shatter import render_frames  # bpy 较重，用到时再加载
    lands = render_frames(bg, d, cuts=cuts, frames=SHATTER_FRAMES, samples=samples, only=only)
    if not only:
        meta.write_text(json.dumps({"lands": lands}))
    return d, lands


def _frame(fi, t, shatter_dir, scene, land, duration, title, wm, subs):
    if fi < SHATTER_FRAMES:
        canvas = Image.open(shatter_dir / f"{fi + 1:04d}.png").convert("RGBA")
        canvas = Image.blend(canvas, scene, smooth(land - 0.3, land, t))  # 接缝无跳变
    else:
        z = 1 + 0.035 * smooth(land, duration, t)  # 拼合后慢推镜
        sw, sh = int(W / z), int(H / z)
        x0, y0 = (W - sw) // 2, (H - sh) // 2
        canvas = scene.crop((x0, y0, x0 + sw, y0 + sh)).resize((W, H), Image.BILINEAR)
    title.draw(canvas, t)
    canvas.alpha_composite(wm)
    subs.draw(canvas, t)
    return canvas.convert("RGB")


def build(cfg_path, shots=False, samples=48):
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    check_fonts()
    name = cfg.get("name") or Path(cfg_path).stem
    work = OUTPUT / name
    work.mkdir(parents=True, exist_ok=True)
    duration = float(cfg.get("duration", 4.6))
    cuts = Path(cfg["cuts"]) if cfg.get("cuts") else DEFAULT_MASK
    bg = _resolve_background(cfg, work)
    scene = Image.open(bg).convert("RGBA")
    land = SHATTER_FRAMES / FPS
    title = Title(cfg["title"], fade_out=duration - 0.6)
    wm = watermark_layer(cfg.get("watermark", WATERMARK))
    subs = Subtitles(cfg.get("subtitles", []))

    if shots:  # 只渲染 8 个关键帧（0.3–1.7 秒），拼成一张对照图
        picks = [10, 16, 22, 28, 34, 40, 46, 52]
        tiles = []
        for f in picks:
            d, _ = _shatter_frames(bg, cuts, samples=24, only=f)
            tiles.append(_frame(f - 1, (f - 1) / FPS, d, scene, land, duration, title, wm, subs).resize((640, 360)))
        sheet = Image.new("RGB", (1280, 360 * math.ceil(len(tiles) / 2)))
        for i, im in enumerate(tiles):
            sheet.paste(im, ((i % 2) * 640, (i // 2) * 360))
        out = work / "shots.jpg"
        sheet.save(out, quality=90)
        print(f"关键帧截图 {out}")
        return out

    shatter_dir, _ = _shatter_frames(bg, cuts, samples)
    out = work / "opening.mp4"
    ff = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
        "-movflags", "+faststart", str(out),
    ], stdin=subprocess.PIPE)
    for fi in range(int(duration * FPS)):
        ff.stdin.write(_frame(fi, fi / FPS, shatter_dir, scene, land, duration, title, wm, subs).tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        raise SystemExit("ffmpeg 合成失败")
    print(f"开场视频 {out}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--shots", action="store_true", help="只出关键帧截图")
    ap.add_argument("--samples", type=int, default=48, help="Blender 采样数，越高越干净越慢")
    a = ap.parse_args()
    build(a.config, shots=a.shots, samples=a.samples)


if __name__ == "__main__":
    main()
