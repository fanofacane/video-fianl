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
