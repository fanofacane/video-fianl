"""全片通用的文字样式：黄色中英双语字幕、顶部水印、开场毛笔标题。"""
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import FONTS, H, W


def smooth(a, b, t):
    p = min(1.0, max(0.0, (t - a) / (b - a)))
    return p * p * (3 - 2 * p)


def subtitle_layer(zh, en):
    """底部居中：亮黄粗宋中文 + 白色衬线英文，带深色描边和柔和投影。"""
    f_zh = ImageFont.truetype(str(FONTS["serif"]), 36)
    f_en = ImageFont.truetype(str(FONTS["en"]), 21)
    y_zh, y_en = 628, 668
    im = Image.new("RGBA", (W, H))
    sh = Image.new("RGBA", (W, H))
    sd = ImageDraw.Draw(sh)
    sd.text((W / 2 + 2, y_zh + 3), zh, font=f_zh, anchor="mm", fill=(0, 0, 0, 200), stroke_width=4, stroke_fill=(0, 0, 0, 200))
    if en:
        sd.text((W / 2 + 1, y_en + 2), en, font=f_en, anchor="mm", fill=(0, 0, 0, 200))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(2)))
    d = ImageDraw.Draw(im)
    d.text((W / 2, y_zh), zh, font=f_zh, anchor="mm", fill=(255, 212, 0), stroke_width=3, stroke_fill=(70, 34, 0))
    if en:
        d.text((W / 2, y_en), en, font=f_en, anchor="mm", fill=(250, 250, 250), stroke_width=1, stroke_fill=(20, 20, 20))
    return im


class Subtitles:
    """按时间轴切换字幕。items: [{"start","end","zh","en"}]"""

    def __init__(self, items):
        self.items = [(s["start"], s["end"], subtitle_layer(s["zh"], s.get("en", ""))) for s in items]

    def draw(self, canvas, t):
        for a, b, im in self.items:
            if a <= t < b:
                canvas.alpha_composite(im)


def watermark_layer(text):
    im = Image.new("RGBA", (W, H))
    if text:
        f = ImageFont.truetype(str(FONTS["serif"]), 24)
        ImageDraw.Draw(im).text((W / 2, 24), text, font=f, anchor="mm", fill=(200, 160, 90, 110))
    return im


class Title:
    """开场大标题：逐字淡入、由灰变白，fade_out 时刻开始淡出。"""

    def __init__(self, text, y=262, size=96, fade_out=4.0):
        self.font = ImageFont.truetype(str(FONTS["title"]), size)
        self.y, self.fade_out = y, fade_out
        x = W / 2 - self.font.getlength(text) / 2
        self.chars = []
        for ch in text:
            self.chars.append((x + self.font.getlength(ch) / 2, ch))
            x += self.font.getlength(ch)

    def draw(self, canvas, t):
        if t < 0.1 or t > self.fade_out + 0.4:
            return
        out = 1 - smooth(self.fade_out, self.fade_out + 0.35, t)
        g = int(120 + 135 * smooth(0.3, 1.2, t))
        lay = Image.new("RGBA", (W, H))
        sh = Image.new("RGBA", (W, H))
        for i, (x, ch) in enumerate(self.chars):
            a = smooth(0.1 + i * 0.07, 0.4 + i * 0.07, t) * out
            if a <= 0:
                continue
            ImageDraw.Draw(sh).text((x + 3, self.y + 4), ch, font=self.font, anchor="mm", fill=(0, 0, 0, int(150 * a)))
            ImageDraw.Draw(lay).text((x, self.y), ch, font=self.font, anchor="mm", fill=(g, g, min(255, g + 8), int(255 * a)))
        canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(4)))
        canvas.alpha_composite(lay)


# ---------- 正文段的屏幕文字（字幕之外） ----------
COLORS = {
    "red": (176, 30, 35),     # 主概念
    "blue": (43, 63, 122),    # 对比 / 误解
    "gold": (232, 163, 23),   # 连接符号、点缀
    "black": (30, 30, 30),    # 概念词、金句
}


def _color(c):
    return COLORS.get(c, c) if isinstance(c, str) else tuple(c)


def screen_text(text, size=56, color="red", reveal=None):
    """粗宋屏幕文字（关键词、概念词、公式、定义、金句），返回裁好边的 RGBA 图。支持多行。
    reveal：只画前 n 个字（逐字打出用）；版面按全文排好，字出现在最终位置，不会跳动。"""
    f = ImageFont.truetype(str(FONTS["serif"]), size)
    lines = text.split("\n")
    widths = [f.getlength(s) for s in lines]
    lh = int(size * 1.25)
    im = Image.new("RGBA", (int(max(widths)) + 20, lh * len(lines) + 20))
    d = ImageDraw.Draw(im)
    full = Image.new("L", im.size)
    left = len(text.replace("\n", "")) if reveal is None else reveal
    for i, s in enumerate(lines):
        x = 10 + (max(widths) - widths[i]) / 2
        ImageDraw.Draw(full).text((x, 10 + i * lh), s, font=f, fill=255)
        part = s[:max(0, left)]
        left -= len(s)
        if part:
            d.text((x, 10 + i * lh), part, font=f, fill=_color(color) + (255,))
    return im.crop(full.getbbox())


def concept_list(items, upto, size=44):
    """概念清单：每条 红字标题 + 括号黑字说明，从上往下叠加；upto = 显示前几条。"""
    ft = ImageFont.truetype(str(FONTS["serif"]), size)
    fn = ImageFont.truetype(str(FONTS["serif"]), int(size * 0.5))
    gap, note_h = int(size * 0.35), int(size * 0.75)
    w = int(max(max(ft.getlength(it["title"]), fn.getlength(f"（{it.get('note', '')}）")) for it in items)) + 10
    h = len(items) * (size + note_h + gap) + 10
    im = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(im)
    y = 0
    for it in items[:upto]:
        d.text((0, y), it["title"], font=ft, fill=_color(it.get("color", "red")) + (255,))
        if it.get("note"):
            d.text((0, y + size + 4), f"（{it['note']}）", font=fn, fill=_color("black") + (255,))
        y += size + note_h + gap
    return im


def cycle_diagram(items, upto, r=150, size=44):
    """循环示意图：几个词绕一圈（从正上方顺时针），之间用红色弧形箭头相连。
    upto = 显示前几个词；第 k 个词出现时，画出指向它的箭头；最后一个词出现时补上回到第一个的箭头。"""
    import math as _m
    f = ImageFont.truetype(str(FONTS["serif"]), size)
    n = len(items)
    pad = size * 2
    S = 2 * (r + pad)
    im = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(im)
    cx = cy = S / 2
    ang = [-_m.pi / 2 + 2 * _m.pi * i / n for i in range(n)]
    red = _color("red") + (255,)

    def arrow(a0, a1):
        span = (a1 - a0) % (2 * _m.pi)
        m = 0.24 * 2 * _m.pi / n            # 两端留出文字的位置
        pts = [(cx + r * _m.cos(a0 + m + (span - 2 * m) * k / 24), cy + r * _m.sin(a0 + m + (span - 2 * m) * k / 24))
               for k in range(25)]
        d.line(pts, fill=red, width=5, joint="curve")
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        th = _m.atan2(y2 - y1, x2 - x1)
        L = 18
        d.polygon([(x2 + 4 * _m.cos(th), y2 + 4 * _m.sin(th)),
                   (x2 - L * _m.cos(th - 0.45), y2 - L * _m.sin(th - 0.45)),
                   (x2 - L * _m.cos(th + 0.45), y2 - L * _m.sin(th + 0.45))], fill=red)

    for k in range(min(upto, n)):
        if k > 0:
            arrow(ang[k - 1], ang[k])
        if k == n - 1:
            arrow(ang[k], ang[0])
        it = items[k]
        tx, ty = cx + r * _m.cos(ang[k]), cy + r * _m.sin(ang[k])
        d.text((tx, ty), it["text"], font=f, anchor="mm", fill=_color(it.get("color", "black")) + (255,))
    return im


def bubble(text, style="green", size=30):
    """对话气泡：green = 绿底方框（聊天消息），white = 白底黑边圆角带尾巴（漫画）。"""
    f = ImageFont.truetype(str(FONTS["serif"]), size)
    lines = text.split("\n")
    tw = int(max(f.getlength(s) for s in lines))
    lh = int(size * 1.3)
    pad_x, pad_y = int(size * 0.6), int(size * 0.4)
    bw, bh = tw + pad_x * 2, lh * len(lines) + pad_y * 2 - int(size * 0.3)
    tail = int(size * 0.7) if style == "white" else 0
    im = Image.new("RGBA", (bw + 8, bh + tail + 8))
    d = ImageDraw.Draw(im)
    if style == "white":
        d.rounded_rectangle((4, 4, 4 + bw, 4 + bh), radius=int(size * 0.8), fill=(255, 255, 255, 255), outline=(20, 20, 20, 255), width=3)
        tx = 4 + bw // 4
        d.polygon([(tx, 4 + bh - 3), (tx + size * 0.7, 4 + bh - 3), (tx - size * 0.1, 4 + bh + tail)], fill=(255, 255, 255, 255))
        d.line([(tx, 4 + bh - 1), (tx - size * 0.1, 4 + bh + tail), (tx + size * 0.7, 4 + bh - 1)], fill=(20, 20, 20, 255), width=3)
    else:
        d.rectangle((4, 4, 4 + bw, 4 + bh), fill=(149, 236, 105, 255))
    for i, s in enumerate(lines):
        d.text((4 + pad_x, 4 + pad_y + i * lh), s, font=f, fill=(20, 20, 20, 255))
    return im
