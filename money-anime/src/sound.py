"""BGMと効果音を numpy で合成する（素材の権利を気にしなくてよいように全部自作）。"""
import numpy as np

SR = 44100


def env(n, a=0.005, d=0.3):
    t = np.arange(n) / SR
    e = np.minimum(1, t / a) * np.exp(-t / d)
    return e


def tone(freq, dur, harm=(1, .5, .25), a=0.005, d=0.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    w = sum(h * np.sin(2 * np.pi * freq * (i + 1) * t) for i, h in enumerate(harm))
    return w * env(n, a, d)


def midi(m):
    return 440 * 2 ** ((m - 69) / 12)


def bgm(total, bpm=104):
    """C-Am-F-G のほのぼのループ。エレピ＋ベース＋軽いハイハット。"""
    out = np.zeros(int(total * SR) + SR)
    beat = 60 / bpm
    chords = [(60, 64, 67, 72), (57, 60, 64, 69), (53, 57, 60, 65), (55, 59, 62, 67)]
    melody = [72, 74, 76, 79, 76, 74, 72, 69, 69, 72, 74, 72, 71, 72, 74, 79]
    rng = np.random.default_rng(1)
    t, i = 0.0, 0
    while t < total:
        ch = chords[(i // 4) % 4]
        s = int(t * SR)
        def add(x, at=s):
            e = min(len(out), at + len(x))
            out[at:e] += x[:e - at]
        if i % 2 == 0:  # 和音（2拍ごと）
            for m in ch[:3]:
                add(0.05 * tone(midi(m), beat * 2.2, (1, .3, .1), 0.01, 0.9))
        add(0.10 * tone(midi(ch[0] - 24), beat * 1.0, (1, .2), 0.01, 0.35))  # ベース
        if i % 2 == 1:  # 裏拍のメロディ
            add(0.045 * tone(midi(melody[(i // 2) % 16]), beat * 1.2, (1, .15, .05), 0.003, 0.35))
        hh = rng.standard_normal(int(0.04 * SR)) * env(int(0.04 * SR), 0.001, 0.012)
        add(0.03 * hh, s + int(beat / 2 * SR))
        t += beat
        i += 1
    return out[:int(total * SR)]


def sfx(kind):
    rng = np.random.default_rng(7)
    if kind == "coin":  # チャリン
        return 0.25 * (tone(1975, 0.5, (1, .3), 0.001, 0.12) + np.pad(tone(2637, 0.6, (1, .3), 0.001, 0.25), (int(0.07 * SR), 0))[:int(0.5 * SR)])
    if kind == "pop":
        n = int(0.18 * SR); t = np.arange(n) / SR
        return 0.35 * np.sin(2 * np.pi * (300 + 900 * t / 0.18) * t) * env(n, 0.002, 0.05)
    if kind == "whoosh":
        n = int(0.6 * SR)
        x = rng.standard_normal(n)
        k = np.hanning(n)
        y = np.convolve(x, np.ones(30) / 30, mode="same")
        return 0.35 * y * k
    if kind == "gaan":  # ガーン
        return 0.22 * sum(tone(midi(m), 1.6, (1, .6, .4, .2), 0.002, 0.7) for m in (36, 42, 48))
    if kind == "kira":  # キラキラ
        out = np.zeros(int(1.0 * SR))
        for j, m in enumerate((84, 88, 91, 96, 100)):
            x = tone(midi(m), 0.5, (1, .2), 0.001, 0.15)
            s = int(j * 0.07 * SR)
            out[s:s + len(x)] += 0.12 * x[:len(out) - s]
        return out
    if kind == "stop":  # 待った！のドン
        n = int(0.5 * SR); t = np.arange(n) / SR
        return 0.5 * np.sin(2 * np.pi * (120 * np.exp(-t * 6) + 40) * t) * env(n, 0.001, 0.15) + 0.15 * rng.standard_normal(n) * env(n, 0.001, 0.03)
    if kind == "grow":  # にょきにょき
        n = int(1.2 * SR); t = np.arange(n) / SR
        return 0.12 * np.sin(2 * np.pi * (400 + 500 * t) * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 9 * t)) * np.hanning(n)
    raise ValueError(kind)
