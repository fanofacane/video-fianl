"""逐句截图：每条字幕结束前一帧，4 列排版，用来审元素是否逐句叠加、画面是否饱满。

    python3 scripts/perline_shots.py <episode.name>   # 需先跑过 video.episode --shots
"""
import json, sys, math
from pathlib import Path
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from video.body.build import build
name = sys.argv[1]
cfg = json.load(open(f"output/{name}/body_gen.json"))
subs = cfg["subtitles"]
cfg["shots"] = [round(s["end"] - 0.15, 2) for s in subs]
cfg["name"] = f"{name}_perline"
Path(f"output/{name}/perline_gen.json").write_text(json.dumps(cfg, ensure_ascii=False))
build(f"output/{name}/perline_gen.json", shots=True)
# 重新排成 4 列小图
src = Image.open(f"output/{name}_perline/shots.jpg")
n = len(cfg["shots"]); tiles = []
for i in range(n):
    x, y = (i % 2) * 640, (i // 2) * 360
    tiles.append(src.crop((x, y, x + 640, y + 360)).resize((400, 225)))
cols = 4; rows = math.ceil(n / cols)
sheet = Image.new("RGB", (cols * 400, rows * 225), "white")
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % cols) * 400, (i // cols) * 225))
sheet.save(f"output/{name}_perline/perline.jpg", quality=88)
print(f"output/{name}_perline/perline.jpg", n)
