"""MiniMax non-streaming speech synthesis and voice cloning CLI."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[4]
EMOTIONS = ('happy', 'sad', 'angry', 'fearful', 'disgusted', 'surprised', 'calm')


def save_json(path, value):
    with Path(path).open('x', encoding='utf-8') as file:
        json.dump(value, file, ensure_ascii=False, indent=2)


def check_response(data):
    if not isinstance(data, dict) or data.get('base_resp', {}).get('status_code') != 0:
        status = data.get('base_resp', {}) if isinstance(data, dict) else {}
        raise ValueError(f"MiniMax error {status.get('status_code', 'unknown')}: {status.get('status_msg', 'invalid response')}")
    return data


def post(base, key, route, **kwargs):
    try:
        response = requests.post(base + route, headers={'Authorization': 'Bearer ' + key},
                                 timeout=(15, 300), allow_redirects=False, **kwargs)
        if response.status_code != 200:
            raise ValueError(f'HTTP {response.status_code}; request was not retried')
        return check_response(response.json())
    except requests.RequestException as exc:
        raise ValueError('Network error/timeout; server result may be unknown; no automatic retry') from exc


def decode_audio(data):
    check_response(data)
    result = data.get('data') or {}
    if result.get('status') != 2 or not result.get('audio'):
        raise ValueError('Missing completed audio result')
    try:
        audio = bytes.fromhex(result['audio'])
    except (ValueError, TypeError) as exc:
        raise ValueError('Audio is not valid hex data') from exc
    if not audio:
        raise ValueError('Empty audio result')
    return audio


def read_text(args):
    text = Path(args.text_file).read_text(encoding='utf-8-sig') if args.text_file else args.text
    if not text or not text.strip() or len(text) >= 10000:
        raise ValueError('Text must contain 1–9999 characters')
    return text


def tts_payload(args):
    voice = args.voice_id or os.getenv('MINIMAX_VOICE_ID')
    if not voice:
        raise ValueError('Set MINIMAX_VOICE_ID or --voice-id')
    if not .5 <= args.speed <= 2 or not 0 < args.vol <= 10 or not -12 <= args.pitch <= 12:
        raise ValueError('speed: 0.5–2; vol: (0,10]; pitch: -12–12')
    payload = {
        'model': args.model or os.getenv('MINIMAX_MODEL', 'speech-2.8-hd'),
        'text': read_text(args), 'stream': False, 'output_format': 'hex',
        'voice_setting': {'voice_id': voice, 'speed': args.speed, 'vol': args.vol, 'pitch': args.pitch},
        'audio_setting': {'sample_rate': args.sample_rate, 'format': args.format, 'channel': args.channel},
        'subtitle_enable': args.subtitles,
    }
    if args.format == 'mp3':
        payload['audio_setting']['bitrate'] = args.bitrate
    if args.emotion:
        payload['voice_setting']['emotion'] = args.emotion
    if args.settings:
        settings = json.loads(Path(args.settings).read_text(encoding='utf-8-sig'))
        allowed = {'pronunciation_dict', 'language_boost', 'text_normalization_mode',
                   'voice_modify', 'subtitle_type', 'aigc_watermark'}
        if not isinstance(settings, dict) or set(settings) - allowed:
            raise ValueError('Unsupported settings key; see references/api.md')
        if settings.get('subtitle_type') == 'word_streaming':
            raise ValueError('word_streaming requires streaming; this CLI is non-streaming')
        payload.update(settings)
    return payload


def synthesize(args, base, key):
    payload = tts_payload(args)
    if args.dry_run:
        return {'dry_run': True, 'request': payload}
    target = Path(args.output).resolve()
    if target.suffix.lower() != '.' + args.format:
        raise ValueError('Output extension must match --format')
    meta = target.with_suffix(target.suffix + '.json')
    if target.exists() or meta.exists():
        raise ValueError('Output or metadata already exists; choose a new filename')
    target.parent.mkdir(parents=True, exist_ok=True)
    # Reserve both paths before making a billable request.
    with target.open('xb') as audio_file, meta.open('x', encoding='utf-8') as meta_file:
        try:
            result = post(base, key, '/t2a_v2', json=payload)
            audio = decode_audio(result)
            audio_file.write(audio)
            clean = {**result, 'data': {k: v for k, v in result['data'].items() if k != 'audio'}}
            json.dump({'request': payload, 'response': clean}, meta_file, ensure_ascii=False, indent=2)
        except Exception:
            # Empty reserved files are retained to mark an uncertain paid request.
            raise
    return {'audio': str(target), 'metadata': str(meta), 'voice_id': payload['voice_setting']['voice_id'],
            'extra_info': result.get('extra_info'), 'subtitle_url': result['data'].get('subtitle_file')}


def inspect_audio(path):
    path = Path(path)
    if path.suffix.lower() not in {'.mp3', '.m4a', '.wav'} or not 0 < path.stat().st_size <= 20_000_000:
        raise ValueError('Clone audio must be mp3/m4a/wav and no larger than 20 MB')
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                            '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    duration = float(json.loads(probe.stdout)['format']['duration'])
    if not math.isfinite(duration) or not 10 <= duration <= 300:
        raise ValueError('Clone audio duration must be 10–300 seconds')
    return path


def clone(args, base, key):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{6,254}[A-Za-z0-9]', args.voice_id):
        raise ValueError('voice-id: 8–256 chars; first letter; last alphanumeric; only letters/digits/_/-')
    if args.demo_text and len(args.demo_text) > 1000:
        raise ValueError('Demo text must not exceed 1000 characters')
    source = inspect_audio(args.audio) if args.audio else None
    if args.file_id is not None and args.file_id <= 0:
        raise ValueError('file-id must be positive')
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=False)
    file_id = args.file_id
    if source:
        with source.open('rb') as file:
            uploaded = post(base, key, '/files/upload', data={'purpose': 'voice_clone'},
                            files={'file': (source.name, file, 'application/octet-stream')})
        save_json(out / 'upload.json', uploaded)
        file_id = uploaded['file']['file_id']
    payload = {'file_id': file_id, 'voice_id': args.voice_id,
               'need_noise_reduction': args.noise_reduction,
               'need_volume_normalization': args.normalize}
    if args.demo_text:
        payload.update(text=args.demo_text, model=args.model or os.getenv('MINIMAX_MODEL', 'speech-2.8-hd'))
    save_json(out / 'request.json', payload)
    result = post(base, key, '/voice_clone', json=payload)
    save_json(out / 'result.json', result)
    return {'voice_id': args.voice_id, 'file_id': file_id, 'result_dir': str(out),
            'demo_audio': result.get('demo_audio'), 'base_resp': result['base_resp']}


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument('--env-file', default=str(ROOT / '.env'))
    commands = root.add_subparsers(dest='command', required=True)
    tts = commands.add_parser('tts', help='Synthesize using the configured cloned voice')
    text = tts.add_mutually_exclusive_group(required=True)
    text.add_argument('--text')
    text.add_argument('--text-file')
    tts.add_argument('--output', required=True)
    tts.add_argument('--voice-id')
    tts.add_argument('--model')
    tts.add_argument('--speed', type=float, default=1)
    tts.add_argument('--vol', type=float, default=1)
    tts.add_argument('--pitch', type=int, default=0)
    tts.add_argument('--emotion', choices=EMOTIONS)
    tts.add_argument('--format', choices=['mp3', 'wav', 'flac', 'pcm'], default='mp3')
    tts.add_argument('--sample-rate', type=int, choices=[8000,16000,22050,24000,32000,44100], default=32000)
    tts.add_argument('--bitrate', type=int, choices=[32000,64000,128000,256000], default=128000)
    tts.add_argument('--channel', type=int, choices=[1,2], default=1)
    tts.add_argument('--subtitles', action='store_true')
    tts.add_argument('--settings', help='Advanced settings JSON file')
    tts.add_argument('--dry-run', action='store_true')
    cloning = commands.add_parser('clone', help='Upload and clone, or reuse an uploaded file ID')
    source = cloning.add_mutually_exclusive_group(required=True)
    source.add_argument('--audio')
    source.add_argument('--file-id', type=int)
    cloning.add_argument('--voice-id', required=True)
    cloning.add_argument('--output-dir', required=True)
    cloning.add_argument('--demo-text')
    cloning.add_argument('--model')
    cloning.add_argument('--noise-reduction', action='store_true')
    cloning.add_argument('--normalize', action='store_true')
    return root


def main():
    args = parser().parse_args()
    try:
        load_dotenv(args.env_file, override=False)
        key = os.getenv('MINIMAX_API_KEY')
        dry_run = getattr(args, 'dry_run', False)
        if not key and not dry_run:
            raise ValueError('MINIMAX_API_KEY is missing')
        base = os.getenv('MINIMAX_BASE_URL', 'https://api.minimax.cn/v1').rstrip('/')
        # This skill is intentionally scoped to the verified MiniMax China API.
        if base != 'https://api.minimax.cn/v1':
            raise ValueError('This client supports https://api.minimax.cn/v1 only')
        result = synthesize(args, base, key) if args.command == 'tts' else clone(args, base, key)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        message = str(exc)
        secret = os.getenv('MINIMAX_API_KEY')
        if secret:
            message = message.replace(secret, '[REDACTED]')
        print(json.dumps({'error': message}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
