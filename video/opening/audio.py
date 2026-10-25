"""开场音效：低音铺底 + 碎片飞入的风声 + 每片玻璃落位时的清脆声。"""
import wave

import numpy as np


def make_opening_sfx(path, duration, lands, seed=7):
    sr = 44100
    t = np.arange(int(duration * sr)) / sr
    rng = np.random.default_rng(seed)
    pad = sum(np.sin(2 * np.pi * f * t + i) for i, f in enumerate([110, 164.8, 220, 261.6, 329.6]))
    pad *= 0.045 * np.minimum(1, t / 1.5) * (1 + 0.15 * np.sin(2 * np.pi * 0.25 * t))
    noise = rng.normal(0, 1, len(t))
    whoosh = np.convolve(noise, np.ones(40) / 40, "same") - np.convolve(noise, np.ones(400) / 400, "same")
    sig = pad + whoosh * np.exp(-((t - 0.6) / 0.35) ** 2) * 0.55
    for t0 in lands:
        m = t >= t0
        tt = t[m] - t0
        sig[m] += 0.05 * np.sin(2 * np.pi * rng.uniform(2200, 5200) * tt) * np.exp(-tt * 18)
    sig = np.tanh(sig * 1.3) * 0.8
    pcm = (np.stack([sig, sig], 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
