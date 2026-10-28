"""分阶段制作：稿件确认 → 显式配音 → 截图确认 → 成片。

    python3 -m video.episode episodes/present/episode.json --status  # 查看当前阶段和稿件ID
    python3 -m video.episode episodes/present/episode.json --shots   # 确认稿件、显式配音后出正文截图
    python3 -m video.episode episodes/present/episode.json           # 截图确认后出完整视频

配置见 episodes/present/episode.json：
- lines：每条字幕一行（zh 带标点用于配音，显示时去掉句末标点；en 为英文字幕）
- opening.lines：前几行放在碎片开场里念，其余进入正文
- scenes：正文场景，from/to 为行号（从 1 开始）；元素用 at/until 行号 + delay 秒数定时，
  其余字段同 video/body/build.py 的元素
"""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

from .config import OUTPUT, ROOT, WATERMARK
from . import review

XFADE = 0.5   # 开场到正文的提亮溶解时长
TAIL = 1.2    # 配音结束后画面多停留的秒数
SKILL_TTS = ROOT / ".claude" / ".skills" / "minimax-speech" / "scripts" / "client.py"


def _sub_text(zh):
    return zh.rstrip("，。；、：,.;:")


def _audio_len(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def generate_voice(ep, work):
    """唯一会调用付费 TTS 的整期制作入口；不删除旧版本。"""
    review.require_script(ep, work)
    settings = review.voice_settings()
    folder, audio, receipt = review.voice_paths(ep, work, settings)
    if receipt.exists():
        review.require_voice(ep, work, settings)
        print(f"复用已完成配音 {audio}")
        return audio
    folder.mkdir(parents=True, exist_ok=True)
    pending = folder / 'request.json'
    if pending.exists() or audio.exists():
        raise ValueError(f'该配音存在未完成请求，禁止自动重试。先核实服务端结果及 {folder} 内文件，再人工清理失败记录或恢复完成记录。')
    text = folder / 'narration.txt'
    script = ''.join(line['zh'] for line in ep['lines'])
    text.write_text(script, encoding='utf-8')
    # Exclusive creation prevents two local processes from starting the same paid request.
    with pending.open('x', encoding='utf-8') as file:
        json.dump({'text': script, 'settings': settings}, file, ensure_ascii=False, indent=2)
    subprocess.run([sys.executable, str(SKILL_TTS), 'tts', '--text-file', str(text),
                    '--output', str(audio), '--voice-id', settings['voice_id'],
                    '--model', settings['model'], '--speed', str(settings['speed']),
                    '--vol', str(settings['vol']), '--pitch', str(settings['pitch'])], check=True)
    total = _audio_len(audio)
    if not math.isfinite(total) or total <= 0:
        raise ValueError('生成音频时长无效；保留请求记录，请检查。')
    review.write_json(receipt, {'voice_id': review.voice_id(ep, settings),
                               'audio_sha256': review.file_digest(audio), 'duration': total})
    print(f'配音已生成 {audio}（{total:.2f} 秒），可试听后执行 --shots。')
    return audio


def narration(ep, work):
    """仅读取匹配的配音并做本地字幕对齐，绝不调用 TTS。"""
    settings = review.voice_settings()
    folder, audio = review.require_voice(ep, work, settings)
    total = _audio_len(audio)
    # Line splitting affects alignment even when concatenated narration stays identical.
    key = review.digest({'lines': [line['zh'] for line in ep['lines']],
                         'audio': review.file_digest(audio)})
    times = folder / f'line_times-{key}.json'
    if not times.exists():
        from .align import align_lines, char_times
        tl = align_lines([line['zh'] for line in ep['lines']], char_times(audio), total)
        review.write_json(times, tl)
    return audio, total, review.read_json(times)


def load_episode(path):
    ep = review.read_json(path)
    name = ep.get('name', '')
    if not name or '/' in name or '\\' in name or name in ('.', '..'):
        raise ValueError('episode.name 必须是单层目录名。')
    work = (OUTPUT / name).resolve()
    if not work.is_relative_to(OUTPUT.resolve()):
        raise ValueError('输出目录必须位于 output 内。')
    if not ep.get('lines') or any(not isinstance(line.get('zh'), str) or not line['zh'].strip() for line in ep['lines']):
        raise ValueError('lines 必须包含非空中文逐字稿。')
    return ep, work


def status(ep, work):
    result = {'script_id': review.script_id(ep),
              'script_approved': review.is_approved(work, 'script', review.script_id(ep)),
              'voice_ready': False, 'shots_ready': False, 'shots_approved': False}
    try:
        settings = review.voice_settings()
        _, audio = review.require_voice(ep, work, settings)
        result.update(voice_ready=True, audio=str(audio))
        revision = review.shots_revision(ep, work, settings)
        result.update(shots_ready=True, shots_id=revision,
                      shots_approved=review.is_approved(work, 'shots', revision))
    except ValueError as exc:
        result['next_step'] = str(exc)
    return result


def _subs(ep, tl, idx, offset=0.0):
    return [{"start": round(tl[i][0] - offset, 3), "end": round(tl[i][1] - offset, 3),
             "zh": _sub_text(ep["lines"][i]["zh"]), "en": ep["lines"][i].get("en", "")} for i in idx]


def plan(ep, work, tl, total):
    """生成开场与正文的配置（时间换算成各自的本地秒数）。"""
    n_open = ep["opening"]["lines"]
    open_dur = round(tl[n_open - 1][1] + 0.25, 2)
    opening = {
        "name": f"{ep['name']}_opening", "title": ep["title"], "watermark": ep.get("watermark", WATERMARK),
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
            if e.get("items"):  # 清单 / 循环图：每一项可用 at/delay 指定出现的行，默认依次跟随元素出现
                items = []
                for k, it in enumerate(e["items"]):
                    it = dict(it)
                    if "at" in it:
                        it["t"] = round(tl[it.pop("at") - 1][0] + it.pop("delay", 0) - t0, 3)
                    else:
                        it["t"] = round(e["start"] + k * float(e.get("step", 0.8)), 3)
                    items.append(it)
                e["items"] = items
            end = tl[until][1] - t0 + 0.15
            e["end"] = round(body_dur + 1 if until == len(tl) - 1 else end, 3)
            elements.append(e)
        shots.append(round(tl[last][1] - t0 - 0.2, 2))   # 每个场景元素到齐时
    body = {
        "name": f"{ep['name']}_body", "duration": body_dur, "watermark": ep.get("watermark", WATERMARK),
        "background": "paper", "assets_dir": str((work / "assets").relative_to(ROOT)),
        "assets": ep["assets"], "subtitles": _subs(ep, tl, range(n_open, len(tl)), offset=t0),
        "elements": elements, "shots": shots,
    }
    return opening, body, open_dur


def build(path, shots=False):
    ep, work = load_episode(path)
    review.require_script(ep, work)
    if not shots:
        revision = review.shots_revision(ep, work, review.voice_settings())
        if not review.is_approved(work, 'shots', revision):
            raise ValueError('当前正文截图尚未确认。展示截图并等待用户确认，再执行 --approve-shots 截图ID。')
    work.mkdir(parents=True, exist_ok=True)
    audio, total, tl = narration(ep, work)
    opening, body, open_dur = plan(ep, work, tl, total)
    (work / "opening_gen.json").write_text(json.dumps(opening, ensure_ascii=False, indent=1), encoding="utf-8")
    (work / "body_gen.json").write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")

    from .body.build import build as build_body
    if shots:
        preview = Path(build_body(work / "body_gen.json", shots=True)).resolve()
        revision = review.visual_id(ep, work, audio)
        review.write_json(work / 'reviews' / 'shots-produced.json',
                          {'revision': revision, 'preview': str(preview),
                           'preview_sha256': review.file_digest(preview)})
        # Every newly produced preview must be reviewed, including regenerated pixels.
        (work / 'reviews' / 'shots.json').unlink(missing_ok=True)
        print(f'截图待确认，审核ID：{revision}')
        return preview
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
    actions = ap.add_mutually_exclusive_group()
    actions.add_argument('--status', action='store_true', help='查看内容ID、审核与配音状态，不调用接口')
    actions.add_argument('--approve-script', metavar='ID', help='用户确认后记录对应稿件ID；不生成配音')
    actions.add_argument('--voice', action='store_true', help='为已确认稿件显式生成配音（可能计费）')
    actions.add_argument('--approve-shots', metavar='ID', help='用户确认后记录对应截图ID；不渲染')
    actions.add_argument("--shots", action="store_true", help="读取已完成配音，出正文截图；不调用TTS")
    a = ap.parse_args()
    try:
        ep, work = load_episode(a.config)
        if a.status:
            print(json.dumps(status(ep, work), ensure_ascii=False, indent=2))
        elif a.approve_script:
            review.approve(work, 'script', a.approve_script, review.script_id(ep))
            print('当前稿件确认已记录；尚未生成配音。')
        elif a.voice:
            generate_voice(ep, work)
        elif a.approve_shots:
            revision = review.shots_revision(ep, work, review.voice_settings())
            review.approve(work, 'shots', a.approve_shots, revision)
            print('当前截图确认已记录；尚未渲染成片。')
        else:
            build(a.config, shots=a.shots)
    except ValueError as exc:
        ap.exit(1, f'{exc}\n')


if __name__ == "__main__":
    main()
