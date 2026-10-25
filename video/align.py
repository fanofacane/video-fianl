"""口播与字幕行对齐：本地 Whisper 识别出逐字时间，再与已知文案逐字匹配，得到每行字幕的起止时间。

MiniMax 返回的字幕时间只到大段落（十几秒一段），不够做逐行字幕，所以在这里细化。
"""
import difflib
import re
import subprocess

import numpy as np

_PUNCT = re.compile(r"[\s，。？！；：、,.?!;:“”\"'‘’（）()《》…—-]")


def _norm(s):
    return _PUNCT.sub("", s)


def _load_audio(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def char_times(audio_path, model="medium"):
    """返回 [(字, 开始秒, 结束秒)]，每个识别出的汉字一项。"""
    from faster_whisper import WhisperModel

    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(_load_audio(audio_path), language="zh", word_timestamps=True, beam_size=5,
                           initial_prompt="以下是普通话的句子，使用简体中文。")
    out = []
    for s in segs:
        for w in s.words:
            chars = _norm(w.word)
            if not chars:
                continue
            step = (w.end - w.start) / len(chars)
            out += [(c, w.start + i * step, w.start + (i + 1) * step) for i, c in enumerate(chars)]
    return out


def align_lines(lines, ct, total):
    """lines: 每行文案；ct: char_times 结果；total: 音频总长。返回每行 (start, end)。"""
    ref = "".join(_norm(s) for s in lines)
    hyp = "".join(c for c, _, _ in ct)
    starts = np.full(len(ref), np.nan)
    ends = np.full(len(ref), np.nan)
    for a, b, size in difflib.SequenceMatcher(None, ref, hyp, autojunk=False).get_matching_blocks():
        for k in range(size):
            starts[a + k], ends[a + k] = ct[b + k][1], ct[b + k][2]
    # 没匹配上的字按前后已知时间线性插值
    idx = np.arange(len(ref))
    ok = ~np.isnan(starts)
    if ok.sum() < 2:
        raise RuntimeError("识别结果与文案几乎对不上，请检查音频")
    starts = np.interp(idx, idx[ok], starts[ok])
    ends = np.interp(idx, idx[ok], ends[ok])
    out, pos = [], 0
    for s in lines:
        n = len(_norm(s))
        out.append([float(starts[pos]), float(ends[pos + n - 1])])
        pos += n
    # 相邻行之间的停顿分给前一行字幕，最后一行延续到音频结束
    for i in range(len(out) - 1):
        out[i][1] = max(out[i][1], out[i + 1][0] - 0.05)
    out[0][0] = 0.0
    out[-1][1] = total
    return [tuple(x) for x in out]
