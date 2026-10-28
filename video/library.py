"""参考库与成品库。

    # 研究一个对标视频：解析标题/简介 → 下载 → 转写 → 场景帧截图（只存本地 output/library/<slug>/，不入库）
    python3 -m video.library ref <slug> <分享链接>
    # 归档我们做好的一期（按发布标题建目录）
    python3 -m video.library ours episodes/<slug>/episode.json

入库内容（library/，提交到仓库）：
  four_transcripts.md           对标口播全文（写稿必读）
  reference/<发布标题>.md        用户认可的逐字稿（手动添加）
  ours/<发布标题>/              我们的成片：meta.md、script.md、cover.jpg、frames.jpg
不入库：对标视频研究结果全部在 output/library/<slug>/（video.mp4、transcript.txt、meta.md、frames.jpg）。
"""
import argparse
import math
import json
import re
import subprocess
from pathlib import Path

from .config import OUTPUT, ROOT

LIB = ROOT / "library"
PARSER = ROOT / ".claude" / ".skills" / "media-parser" / "scripts" / "client.mjs"


def _run_json(args):
    return json.loads(subprocess.run(args, capture_output=True, text=True, check=True).stdout)


def _duration(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(path)], capture_output=True, text=True, check=True).stdout)


def frames_sheet(video, out, every=3, cols=6):
    """每 every 秒取一帧，拼成 cols 列的场景帧截图，左上角标时间。"""
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf",
        f"fps=1/{every},scale=320:-1,drawtext=text='%{{pts\\:hms}}':x=4:y=4:fontcolor=yellow:fontsize=14:"
        f"box=1:boxcolor=black@0.5,tile={cols}x{math.ceil(_duration(video) / every / cols)}",
        "-frames:v", "1", "-q:v", "4", str(out)], check=True)


def _split_hashtags(desc):
    tags = re.findall(r"#\s*([^#\s]+)", desc)
    title = re.split(r"\s*#", desc, maxsplit=1)[0].strip()
    return title, tags


def add_reference(slug, link):
    local = OUTPUT / "library" / slug
    d = local
    local.mkdir(parents=True, exist_ok=True)
    info = _run_json(["node", str(PARSER), "parse", "--url", link])["data"]
    video = local / "video.mp4"
    if not video.exists():
        subprocess.run(["node", str(PARSER), "download", "--url", link, "--kind", "video", "--output", str(video)],
                       check=True, capture_output=True)
    tr = local / "transcript.json"
    if not tr.exists():
        res = _run_json(["node", str(PARSER), "transcribe", "--url", link, "--wait-seconds", "900", "--timeout", "300"])
        tr.write_text(json.dumps(res, ensure_ascii=False))
    job = json.loads(tr.read_text())["data"]["jobs"][0]
    (d / "transcript.txt").write_text(job["text"], encoding="utf-8")
    dur = _duration(video)
    chars = len(re.sub(r"[\s，。？！；：、,.?!;:“”\"'（）()…]", "", job["text"]))
    title, tags = _split_hashtags(info.get("desc") or info.get("title", ""))
    frames_sheet(video, d / "frames.jpg")
    (d / "meta.md").write_text(f"""# {title}

| 项 | 内容 |
| --- | --- |
| 作者 | {info['author']['nickname']} |
| 链接 | {link} |
| 发布标题 | {title} |
| 简介 | 无单独简介，即“标题 + 话题” |
| 话题 | {' '.join('#' + t for t in tags)} |
| 时长 | {dur:.0f} 秒 |
| 口播字数 | 约 {chars} 字 |
| 语速 | 约 {chars / dur:.1f} 字/秒 |

- 场景帧：[frames.jpg](frames.jpg)（每 3 秒一帧）
- 完整转写稿：[transcript.txt](transcript.txt)（语音自动转写，未校对）
""", encoding="utf-8")
    print(f"已下载到本地 {d}（{title}，{dur:.0f}s，{chars} 字）")


def add_ours(ep_path):
    ep = json.loads(Path(ep_path).read_text(encoding="utf-8"))
    pub = ep["publish"]
    work = OUTPUT / ep["name"]
    final = work / "final.mp4"
    d = LIB / "ours" / re.sub(r'[\\/:*?"<>|]', "", pub["title"]).strip()
    d.mkdir(parents=True, exist_ok=True)
    if final.exists():
        frames_sheet(final, d / "frames.jpg")
    cover = work / "cover.jpg"
    if cover.exists():
        (d / "cover.jpg").write_bytes(cover.read_bytes())
    lines = "\n".join(l["zh"] for l in ep["lines"])
    (d / "script.md").write_text(f"# {pub['title']}（逐字稿）\n\n```\n{lines}\n```\n", encoding="utf-8")
    dur = _duration(final) if final.exists() else 0
    tags = " ".join("#" + t for t in pub["hashtags"])
    (d / "meta.md").write_text(f"""# {pub['title']}

| 项 | 内容 |
| --- | --- |
| 发布标题 | {pub['title']} |
| 简介（直接复制） | {pub['title']} {tags} |
| 概念 | {ep['title']} |
| 时长 | {dur:.0f} 秒 |
| 口播字数 | {sum(len(re.sub(r'[，。？！；：、“”]', '', l['zh'])) for l in ep['lines'])} 字 |
| 配置 | `{Path(ep_path).as_posix()}` |
| 成片（不入库） | `output/{ep['name']}/final.mp4` |

- 封面：[cover.jpg](cover.jpg)
- 场景帧：[frames.jpg](frames.jpg)
- 逐字稿：[script.md](script.md)
""", encoding="utf-8")
    print(f"已归档 {d}")





def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("ref")
    r.add_argument("slug")
    r.add_argument("link")
    o = sub.add_parser("ours")
    o.add_argument("episode")
    a = ap.parse_args()
    add_reference(a.slug, a.link) if a.cmd == "ref" else add_ours(a.episode)


if __name__ == "__main__":
    main()
