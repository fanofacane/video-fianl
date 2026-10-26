"""全片通用参数：画面尺寸、帧率、字体、输出目录。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"            # 成片与缓存（已在 .gitignore 中忽略）
FONT_DIR = ROOT / "assets" / "fonts"  # 由 scripts/fetch_fonts.sh 下载（不入库）

W, H, FPS = 1280, 720, 30
WATERMARK = "@好想一口吃掉"  # 顶部居中账号水印；配置里写 "watermark": "" 可关闭

FONTS = {
    "serif": FONT_DIR / "NotoSerifSC-Black.otf",   # 中文字幕、水印：粗宋
    "title": FONT_DIR / "MaShanZheng.ttf",         # 开场标题：毛笔字
    "en": Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"),  # 英文字幕：衬线
}


def check_fonts():
    missing = [str(p) for p in FONTS.values() if not p.exists()]
    if missing:
        raise SystemExit("缺少字体，请先运行 scripts/fetch_fonts.sh：\n  " + "\n  ".join(missing))
