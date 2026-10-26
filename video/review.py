"""Content-bound approvals and narration artifacts; no network or rendering."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

from .config import ROOT


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def script_id(ep):
    return digest({key: ep.get(key) for key in ('lines', 'title', 'publish')})


def voice_settings():
    env = {**dotenv_values(ROOT / '.env'), **os.environ}
    voice = env.get('MINIMAX_VOICE_ID')
    if not voice:
        raise ValueError('缺少 MINIMAX_VOICE_ID，先配置音色。')
    speed = env.get('MINIMAX_SPEED')
    if speed:
        speed = float(speed)
        speed = int(speed) if speed.is_integer() else speed
        if not 0.5 <= speed <= 2:
            raise ValueError('MINIMAX_SPEED 须在 0.5–2 之间。')
    else:
        speed = 1  # 未配置时保持整数 1，旧配音版本 ID 不变
    return {'voice_id': voice, 'model': env.get('MINIMAX_MODEL') or 'speech-2.8-hd',
            'base_url': env.get('MINIMAX_BASE_URL') or 'https://api.minimax.cn/v1',
            'speed': speed, 'vol': 1, 'pitch': 0}


def voice_id(ep, settings):
    return digest({'text': ''.join(line['zh'] for line in ep['lines']), 'settings': settings})


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def is_approved(work, stage, revision):
    path = work / 'reviews' / f'{stage}.json'
    return path.exists() and read_json(path).get('revision') == revision


def require_script(ep, work):
    if not is_approved(work, 'script', script_id(ep)):
        raise ValueError('当前逐字稿尚未确认或已修改。先展示稿件，用户确认后执行 --approve-script 当前稿件ID。不会自动配音。')


def approve(work, stage, supplied, current):
    if supplied != current:
        raise ValueError('审核ID与当前内容不一致，请重新展示并确认当前版本。')
    write_json(work / 'reviews' / f'{stage}.json',
               {'revision': current, 'confirmed_at': datetime.now(timezone.utc).isoformat()})


def voice_paths(ep, work, settings):
    folder = work / 'voices' / voice_id(ep, settings)
    return folder, folder / 'narration.mp3', folder / 'complete.json'


def require_voice(ep, work, settings):
    require_script(ep, work)
    folder, audio, receipt = voice_paths(ep, work, settings)
    if not audio.exists() or not receipt.exists():
        raise ValueError('当前文案/音色没有已完成配音。请显式执行 --voice；截图和成片不会自动调用配音接口。')
    saved = read_json(receipt)
    if saved.get('voice_id') != voice_id(ep, settings) or saved.get('audio_sha256') != file_digest(audio):
        raise ValueError('配音文件与完成记录不符，请检查音频；不会自动重配。')
    return folder, audio


def visual_id(ep, work, audio):
    # Include generated/local input asset bytes as well as configuration.
    assets = {}
    for folder in (work / 'assets',):
        if folder.exists():
            for path in sorted(folder.rglob('*')):
                if path.is_file():
                    assets[str(path.relative_to(work))] = file_digest(path)
    def visit(value):
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str) and len(value) < 512:
            candidate = Path(value)
            candidate = candidate if candidate.is_absolute() else ROOT / candidate
            try:
                if candidate.is_file():
                    assets[str(candidate)] = file_digest(candidate)
            except OSError:
                pass
    visit(ep)
    return digest({'episode': ep, 'audio': file_digest(audio), 'assets': assets})


def shots_revision(ep, work, settings):
    _, audio = require_voice(ep, work, settings)
    receipt = work / 'reviews' / 'shots-produced.json'
    if not receipt.exists():
        raise ValueError('尚未生成待审核截图，请先执行 --shots。')
    saved = read_json(receipt)
    revision = visual_id(ep, work, audio)
    preview = Path(saved['preview'])
    if (saved.get('revision') != revision or not preview.is_file()
            or saved.get('preview_sha256') != file_digest(preview)):
        raise ValueError('配置、素材、配音或截图已变化，请重新执行 --shots 并确认。')
    return revision
