"""碎片切分：按裂纹遮罩图（黑底白线）把画面分成若干块碎片。

默认遮罩 assets/cuts_mask.png：中间一大块托住标题，四周逐渐变小。
想换切法：在任意截图上用红笔画裂纹线，运行
    python3 -m video.opening.cuts 标注图.png 新遮罩.png
再在配置里把 "cuts" 指向新遮罩即可。
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from ..config import H, W

DEFAULT_MASK = Path(__file__).resolve().parent / "assets" / "cuts_mask.png"
PW, PH = 16.0, 9.0  # 3D 场景里画面板的尺寸（Blender 单位），与 16:9 画面对应


def extract_red_lines(src, out_mask):
    """从手绘标注图里只提取红色线，存成黑底白线遮罩（不保留原图内容）。"""
    a = np.asarray(Image.open(src).convert("RGB").resize((W, H), Image.LANCZOS)).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    red = (r > 170) & (g < 120) & (b < 120) & (r - g > 80)
    Image.fromarray((red * 255).astype(np.uint8)).save(out_mask)


def close_line_gaps(lines, max_ext=140, back=18):
    """手绘线头常差一点没碰到别的线或画面边缘：顺着走向延长线头，碰到就停，让区域真正封闭。"""
    from skimage.morphology import skeletonize

    h, w = lines.shape
    n, lab, stats, _ = cv2.connectedComponentsWithStats(lines, connectivity=8)
    keep = np.zeros_like(lines)
    for i in range(1, n):  # 去掉零星噪点
        if stats[i, cv2.CC_STAT_AREA] >= 120:
            keep[lab == i] = 1
    sk = skeletonize(keep > 0).astype(np.uint8)
    nb = cv2.filter2D(sk, -1, np.ones((3, 3), np.float32), borderType=cv2.BORDER_CONSTANT) - sk
    ends = np.argwhere((sk == 1) & (nb == 1))
    _, sklab = cv2.connectedComponents(sk, connectivity=8)
    out = keep.copy()
    for y, x in ends:
        y0, y1, x0, x1 = max(0, y - back), min(h, y + back + 1), max(0, x - back), min(w, x + back + 1)
        win = np.argwhere(sklab[y0:y1, x0:x1] == sklab[y, x]) + [y0, x0]
        if len(win) < 4:
            continue
        d = np.array([y, x], float) - win.mean(0)
        if np.linalg.norm(d) < 1e-3:
            continue
        d /= np.linalg.norm(d)
        for t in range(3, max_ext):
            py, px = int(round(y + d[0] * t)), int(round(x + d[1] * t))
            if not (0 <= px < w and 0 <= py < h):
                cv2.line(out, (int(x), int(y)), (min(max(px, 0), w - 1), min(max(py, 0), h - 1)), 1, 2)
                break
            hit_other = t > 6 and keep[py, px] and sklab[py, px] != sklab[y, x]
            if hit_other or (t > 12 and keep[py, px]):
                cv2.line(out, (int(x), int(y)), (px, py), 1, 2)
                break
    return out


def cells_from_mask(mask_path=DEFAULT_MASK, min_area_px=1500):
    """返回碎片多边形列表，坐标为画面板坐标（中心为原点，y 轴向上）。"""
    m = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if m is None:
        raise FileNotFoundError(mask_path)
    m = cv2.resize(m, (W, H), interpolation=cv2.INTER_NEAREST)
    lines = cv2.dilate(close_line_gaps((m > 127).astype(np.uint8)), np.ones((5, 5), np.uint8))
    n, lab = cv2.connectedComponents((1 - lines).astype(np.uint8), connectivity=4)
    markers = np.zeros((H, W), np.int32)
    k = 0
    for i in range(1, n):
        if (lab == i).sum() >= min_area_px:
            k += 1
            markers[lab == i] = k
    # 分水岭把线条像素分给相邻区域，碎片之间无缝拼合
    ws = cv2.watershed(np.zeros((H, W, 3), np.uint8), markers)
    for _ in range(3):
        hole = ws <= 0
        if not hole.any():
            break
        grown = cv2.dilate(np.where(hole, 0, ws).astype(np.float32), np.ones((3, 3), np.uint8)).astype(np.int32)
        ws = np.where(hole, grown, ws)
    cells = []
    for i in range(1, k + 1):
        cs, _ = cv2.findContours((ws == i).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cs:
            continue
        c = cv2.approxPolyDP(max(cs, key=cv2.contourArea), 2.0, True)[:, 0, :]
        if len(c) >= 3:
            cells.append([(x / W * PW - PW / 2, PH / 2 - y / H * PH) for x, y in c][::-1])
    return cells


def preview(mask_path, bg_path, out_path):
    """把切分轮廓画在背景图上，用来核对切法。"""
    from PIL import ImageDraw

    im = Image.open(bg_path).convert("RGB").resize((W, H))
    d = ImageDraw.Draw(im)
    for c in cells_from_mask(mask_path):
        d.polygon([((x + PW / 2) / PW * W, (PH / 2 - y) / PH * H) for x, y in c], outline=(255, 60, 60), width=3)
    im.save(out_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("用法: python3 -m video.opening.cuts 红线标注图.png 输出遮罩.png")
    extract_red_lines(sys.argv[1], sys.argv[2])
    print(f"已生成遮罩 {sys.argv[2]}，共 {len(cells_from_mask(sys.argv[2]))} 块碎片")
