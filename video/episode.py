"""整期成片：逐字稿配置 → 配音 → 对齐字幕 → 碎片开场 + 正文 → 拼接混音。

    python3 -m video.episode episodes/hedgehog/episode.json --shots   # 先出正文各场景截图（开场看封面即可）
    python3 -m video.episode episodes/hedgehog/episode.json           # 出完整视频 output/<name>/final.mp4

配置见 episodes/hedgehog/episode.json：
- lines：每条字幕一行（zh 带标点用于配音，显示时去掉句末标点；en 为英文字幕）
- opening.lines：前几行放在碎片开场里念，其余进入正文
- scenes：正文场景，from/to 为行号（从 1 开始）；元素用 at/until 行号 + delay 秒数定时，
  其余字段同 video/body/build.py 的元素
"""
import argparse
import json
import subprocess
from pathlib import Path

from .config import OUTPUT, ROOT

XFADE = 0.5   # 开场到正文的提亮溶解时长
TAIL = 1.2    # 配音结束后画面多停留的秒数
SKILL_TTS = ROOT / ".claude" / ".skills" / "minimax-speech" / "scripts" / "client.py"


def _sub_text(zh):
    return zh.rstrip("，。；、：,.;:")


def _audio_len(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def narration(ep, work):
    """配音（MiniMax，已复刻音色）+ 逐行时间。结果缓存在 output/<name>/。"""
    audio = work / "narration.mp3"
    if not audio.exists():
        text = work / "narration.txt"
        text.write_text("".join(l["zh"] for l in ep["lines"]), encoding="utf-8")
        subprocess.run(["python3", str(SKILL_TTS), "tts", "--text-file", str(text), "--output", str(audio)], check=True)
    total = _audio_len(audio)
    times = work / "line_times.json"
    if not times.exists():
        from .align import align_lines, char_times
        tl = align_lines([l["zh"] for l in ep["lines"]], char_times(audio), total)
        times.write_text(json.dumps(tl))
    return audio, total, json.loads(times.read_text())


def _subs(ep, tl, idx, offset=0.0):
    return [{"start": round(tl[i][0] - offset, 3), "end": round(tl[i][1] - offset, 3),
             "zh": _sub_text(ep["lines"][i]["zh"]), "en": ep["lines"][i].get("en", "")} for i in idx]


def plan(ep, work, tl, total):
    """生成开场与正文的配置（时间换算成各自的本地秒数）。"""
    n_open = ep["opening"]["lines"]
    open_dur = round(tl[n_open - 1][1] + 0.25, 2)
    opening = {
        "name": f"{ep['name']}_opening", "title": ep["title"], "watermark": ep.get("watermark", ""),
        "duration": open_dur, "background": ep["opening"]["background"],
        "subtitles": _subs(ep, tl, range(n_open)),
    }
    t0 = open_dur - XFADE                      # 正文在全片里的起点
    body_dur = round(total + TAIL - t0, 2)
    elements, shots = [], []
    for sc in ep["scenes"]:
        last = sc["to"] - 1
        for e in sc["elements"]:
            e = dict(e)
            at, until = e.pop("at") - 1, e.pop("until", sc["to"]) - 1
            e["start"] = round(tl[at][0] + e.pop("delay", 0) - t0, 3)
            end = tl[until][1] - t0 + 0.15
            e["end"] = round(body_dur + 1 if until == len(tl) - 1 else end, 3)
            elements.append(e)
        shots.append(round(tl[last][1] - t0 - 0.2, 2))   # 每个场景元素到齐时
    body = {
        "name": f"{ep['name']}_body", "duration": body_dur, "watermark": ep.get("watermark", ""),
        "background": "paper", "assets_dir": str((work / "assets").relative_to(ROOT)),
        "assets": ep["assets"], "subtitles": _subs(ep, tl, range(n_open, len(tl)), offset=t0),
        "elements": elements, "shots": shots,
    }
    return opening, body, open_dur


def build(path, shots=False):
    ep = json.loads(Path(path).read_text(encoding="utf-8"))
    work = OUTPUT / ep["name"]
    work.mkdir(parents=True, exist_ok=True)
    audio, total, tl = narration(ep, work)
    opening, body, open_dur = plan(ep, work, tl, total)
    (work / "opening_gen.json").write_text(json.dumps(opening, ensure_ascii=False, indent=1), encoding="utf-8")
    (work / "body_gen.json").write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")

    from .body.build import build as build_body
    if shots:
        return build_body(work / "body_gen.json", shots=True)
    from .opening.build import build as build_opening
    op = build_opening(work / "opening_gen.json")
    bd = build_body(work / "body_gen.json")
    out = work / "final.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(op), "-i", str(bd), "-i", str(audio),
        "-filter_complex", f"[0:v][1:v]xfade=transition=fadewhite:duration={XFADE}:offset={open_dur - XFADE}[v]",
        "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out),
    ], check=True)
    print(f"成片 {out}（{total + TAIL:.1f} 秒）")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--shots", action="store_true", help="只出正文各场景截图")
    a = ap.parse_args()
    build(a.config, shots=a.shots)


if __name__ == "__main__":
    main()
