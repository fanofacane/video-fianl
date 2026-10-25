"""正文段生成：配置 JSON → 正文 mp4（或关键帧截图）。

    python3 -m video.body.build episodes/hedgehog/body_sample.json --shots   # 先出截图
    python3 -m video.body.build episodes/hedgehog/body_sample.json           # 出视频（无声）

配置结构：
{
  "name": "hedgehog_sample",           # 输出到 output/<name>/
  "duration": 15,
  "background": "paper",               # 背景素材 id（纸纹底）
  "assets": {                          # 素材：没有就按 prompt 生图，生成后复用
    "paper":    {"prompt": "...", "size": "1536x864"},
    "hedgehog": {"prompt": "...", "transparent": true}
  },
  "subtitles": [{"start": 0, "end": 1.6, "zh": "...", "en": "..."}],
  "elements": [                        # 按顺序叠加；每个元素在 [start, end) 内显示，首尾淡入淡出
    {"type": "image",  "asset": "hedgehog", "x": 900, "y": 500, "h": 260, "start": 4, "end": 6, "flip": false},
    {"type": "strip",  "asset": "snow", "top": 380, "start": 6, "end": 15},     # 底部撕边照片带
    {"type": "text",   "text": "“刺猬法则”", "size": 64, "color": "black", "x": 640, "y": 150, "start": 3.4, "end": 6.2},
    {"type": "bubble", "text": "疼！", "style": "white", "x": 500, "y": 300, "start": 8.6, "end": 10.4}
  ]
}
坐标均为 1280x720 画面上的元素中心点（strip 用 top 指定上沿；photo 为全屏照片，无需坐标）。
可选 "assets_dir" 指定素材目录（默认 output/<name>/assets）。
"""
import argparse
import json
import math
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from ..config import FPS, H, OUTPUT, ROOT, W, check_fonts
from ..text import Subtitles, bubble, screen_text, smooth, watermark_layer

FADE = 0.4  # 元素淡入淡出时长（秒）


# ---------- 素材 ----------
def _ensure_assets(cfg, adir):
    """缺的素材并行生图；返回 {id: 路径}。"""
    from ..imagegen import generate

    adir.mkdir(parents=True, exist_ok=True)
    jobs = {}
    for aid, a in cfg.get("assets", {}).items():
        p = adir / f"{aid}.png"
        src = ROOT / a["image_from"] if a.get("image_from") else None
        if not p.exists() and src and src.exists():  # 复用已有图片（例如开场封面）
            import shutil
            shutil.copy(src, p)
        if not p.exists():
            jobs[aid] = (a["prompt"], p, a.get("size", "1024x1024"), "transparent" if a.get("transparent") else "opaque")
    if jobs:
        with ThreadPoolExecutor(4) as ex:
            list(ex.map(lambda j: generate(j[0], j[1], size=j[2], background=j[3]), jobs.values()))
    return {aid: adir / f"{aid}.png" for aid in cfg.get("assets", {})}


def _load_cutout(path):
    """透明底素材：裁掉四周透明区域，并去掉过淡的半透明杂边。"""
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im)[..., 3]
    if a.min() == 255:
        raise SystemExit(f"{path} 没有透明背景，请重新生成（transparent: true）")
    box = Image.fromarray(np.where(a > 24, 255, 0).astype(np.uint8)).getbbox()
    return im.crop(box)


def _torn_strip(path, top):
    """照片带：铺满画面宽度，上沿做成撕纸边。"""
    im = Image.open(path).convert("RGB")
    h = H - top
    scale = max(W / im.width, h / im.height)
    im = im.resize((math.ceil(im.width * scale), math.ceil(im.height * scale)), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, im.height - h, (im.width - W) // 2 + W, im.height))
    rng = np.random.default_rng(3)
    edge = np.cumsum(rng.normal(0, 1.6, W))
    edge = edge - np.linspace(edge[0], edge[-1], W)
    edge = 10 + np.clip(edge, -8, 8) + rng.normal(0, 1.2, W)
    yy = np.arange(h)[:, None]
    mask = (yy > edge[None, :]).astype(np.uint8) * 255
    out = im.convert("RGBA")
    out.putalpha(Image.fromarray(mask).filter(ImageFilter.GaussianBlur(0.8)))
    return out


# ---------- 元素 ----------
class Element:
    def __init__(self, e, assets):
        self.start, self.end = float(e["start"]), float(e.get("end", 1e9))
        t = e["type"]
        if t == "image":
            im = _load_cutout(assets[e["asset"]])
            if e.get("flip"):
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
            hh = int(e["h"])
            im = im.resize((max(1, int(im.width * hh / im.height)), hh), Image.LANCZOS)
            self.pos = (int(e["x"] - im.width / 2), int(e["y"] - im.height / 2))
        elif t == "photo":  # 全屏照片，铺满画面
            src = Image.open(assets[e["asset"]]).convert("RGB")
            sc = max(W / src.width, H / src.height)
            src = src.resize((math.ceil(src.width * sc), math.ceil(src.height * sc)), Image.LANCZOS)
            im = src.crop(((src.width - W) // 2, (src.height - H) // 2, (src.width - W) // 2 + W, (src.height - H) // 2 + H)).convert("RGBA")
            self.pos = (0, 0)
        elif t == "strip":
            im = _torn_strip(assets[e["asset"]], int(e["top"]))
            self.pos = (0, int(e["top"]))
        elif t == "text":
            im = screen_text(e["text"], e.get("size", 56), e.get("color", "red"))
            self.pos = (int(e["x"] - im.width / 2), int(e["y"] - im.height / 2))
        elif t == "bubble":
            im = bubble(e["text"], e.get("style", "green"), e.get("size", 30))
            if e.get("rotate"):
                im = im.rotate(e["rotate"], resample=Image.BICUBIC, expand=True)
            self.pos = (int(e["x"] - im.width / 2), int(e["y"] - im.height / 2))
        else:
            raise SystemExit(f"未知元素类型 {t}")
        self.im = im
        self._alpha = im.split()[3]

    def draw(self, canvas, t):
        if not (self.start <= t < self.end):
            return
        a = smooth(self.start, self.start + FADE, t) * (1 - smooth(self.end - FADE, self.end, t))
        if a <= 0:
            return
        im = self.im
        if a < 1:
            im = im.copy()
            im.putalpha(self._alpha.point(lambda v: int(v * a)))
        x, y = self.pos
        x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + im.width), min(H, y + im.height)
        if x1 > x0 and y1 > y0:
            canvas.alpha_composite(im.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


# ---------- 合成 ----------
def build(cfg_path, shots=False):
    cfg_path = Path(cfg_path)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    check_fonts()
    name = cfg.get("name") or cfg_path.stem
    work = OUTPUT / name
    work.mkdir(parents=True, exist_ok=True)
    adir = Path(cfg["assets_dir"]) if cfg.get("assets_dir") else OUTPUT / name / "assets"
    assets = _ensure_assets(cfg, adir if adir.is_absolute() else ROOT / adir)
    bg = Image.open(assets[cfg["background"]]).convert("RGB").resize((W, H), Image.LANCZOS).convert("RGBA")
    elements = [Element(e, assets) for e in cfg["elements"]]
    subs = Subtitles(cfg.get("subtitles", []))
    wm = watermark_layer(cfg.get("watermark", ""))
    duration = float(cfg["duration"])

    def frame(t):
        c = bg.copy()
        for el in elements:
            el.draw(c, t)
        c.alpha_composite(wm)
        subs.draw(c, t)
        return c.convert("RGB")

    if shots:
        times = cfg.get("shots") or [round(duration * (i + 0.5) / 8, 2) for i in range(8)]
        sheet = Image.new("RGB", (1280, 360 * math.ceil(len(times) / 2)))
        for i, t in enumerate(times):
            sheet.paste(frame(t).resize((640, 360)), ((i % 2) * 640, (i // 2) * 360))
        out = work / "shots.jpg"
        sheet.save(out, quality=90)
        print(f"关键帧截图 {out}（{', '.join(f'{t}s' for t in times)}）")
        return out

    out = work / "body.mp4"
    ff = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
        "-movflags", "+faststart", str(out),
    ], stdin=subprocess.PIPE)
    for fi in range(int(duration * FPS)):
        ff.stdin.write(frame(fi / FPS).tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        raise SystemExit("ffmpeg 合成失败")
    print(f"正文视频 {out}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--shots", action="store_true", help="只出关键帧截图")
    a = ap.parse_args()
    build(a.config, shots=a.shots)


if __name__ == "__main__":
    main()
