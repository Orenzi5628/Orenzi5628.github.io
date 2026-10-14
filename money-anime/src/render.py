"""お金の2Dアニメ「ユイとフクロウ先生 〜お金と72の法則〜」のレンダラー。

- 音声: tts.py が VOICEVOX で作った line*.wav と visemes.json（母音タイミング）
- 絵: Pillow で 1 コマずつ描画（カメラのズーム・カット、口パク、エフェクト）
- 音: sound.py で合成した BGM と効果音をミックス
- 出力: ffmpeg で ../money-72.mp4（1920x1080 / 30fps）

使い方: python3 render.py            # 本番
        python3 render.py 3 12.5    # その秒数のコマを preview_*.png に保存
"""
import json
import math
import os
import subprocess
import sys
import wave
from functools import lru_cache
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import sound

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "money-72.mp4")
OW, OH = 1920, 1080          # 出力解像度
SS = 2                       # スーパーサンプリング
K = OW / 1280 * SS           # 設計座標(1280x720) → 描画ピクセル
FPS = 30
SR = 44100

# ---------- 台本・音声・タイムライン ----------
LINES = []
VIS = json.load(open(os.path.join(HERE, "visemes.json")))
for i, row in enumerate(open(os.path.join(HERE, "lines.tsv"), encoding="utf-8")):
    who, text = row.rstrip("\n").split("\t")
    with wave.open(os.path.join(HERE, f"line{i}.wav")) as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    LINES.append({"who": who, "text": text, "pcm": pcm, "vis": VIS[i]})

INTRO, OUTRO = 1.6, 3.0
GAPS = {1: 0.85, 5: 0.15}      # セリフ前の間（1: フクロウ登場, 5: 「待った！」は食い気味）
t = INTRO
for i, ln in enumerate(LINES):
    t += GAPS.get(i, 0.25) if i else 0
    ln["start"] = t
    ln["dur"] = len(ln["pcm"]) / SR
    t += ln["dur"]
END = t
TOTAL = END + OUTRO
NFRAMES = int(TOTAL * FPS)
ST = [ln["start"] for ln in LINES]

SFX = [  # (秒, 種類)
    (0.15, "whoosh"), (0.5, "coin"), (0.8, "coin"), (1.1, "coin"),
    (ST[0] + 1.25, "coin"),
    (ST[1] - 1.0, "whoosh"),
    (ST[2] - 0.05, "gaan"),
    (ST[3] + 3.0, "pop"),
    (ST[4] - 0.05, "kira"),
    (ST[5] - 0.1, "stop"),
    (ST[5] + 1.7, "pop"), (ST[5] + 2.5, "pop"), (ST[5] + 3.3, "pop"), (ST[5] + 5.3, "kira"),
    (ST[6] - 0.1, "grow"), (ST[6] + 1.3, "coin"),
    (END + 0.4, "whoosh"), (END + 1.1, "kira"),
]


def scene_at(tm):
    """(セリフ番号, そのセリフ内の時間)。前の間はそのセリフの場面として扱う。-1=タイトル, 7=まとめ"""
    if tm < INTRO:
        return -1, tm
    if tm >= END + 0.3:
        return len(LINES), tm - END - 0.3
    idx = 0
    for i, s in enumerate(ST):
        pre = GAPS.get(i, 0.25) if i else 0
        if tm >= s - pre:
            idx = i
    return idx, tm - ST[idx]


def mouth_of(who, tm):
    """いま話している母音（a,i,u,e,o）か None。"""
    for ln in LINES:
        if ln["who"] == who and ln["start"] <= tm < ln["start"] + ln["dur"]:
            lt = tm - ln["start"]
            for a, b, v in ln["vis"]:
                if a - 0.02 <= lt < b:
                    return v.lower() if v.lower() in "aiueo" else None
            return None
    return None


def talking(who, tm):
    return any(ln["who"] == who and ln["start"] <= tm < ln["start"] + ln["dur"] for ln in LINES)


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def back(x):  # ちょっと行き過ぎて戻るイージング
    x = max(0.0, min(1.0, x))
    c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def lerp(a, b, k):
    return a + (b - a) * k


def mix(c1, c2, k):
    return tuple(int(lerp(a, b, k)) for a, b in zip(c1, c2))


# ---------- カメラ ----------
WIDE = (640, 360, 1.0)
BOARD_CAM = (672, 300, 1.12)
CAMS = {  # 場面ごとの (中心x, 中心y, ズーム, 切り替え方)
    -1: (WIDE, "cut"),
    0: ((560, 345, 1.12), "ease"),
    1: (BOARD_CAM, "ease"),
    2: ((330, 330, 2.05), "cut"),
    3: (BOARD_CAM, "cut"),
    4: ((330, 330, 2.05), "cut"),
    5: ((1120, 300, 2.0), "cut"),
    6: (WIDE, "ease"),
    7: (WIDE, "cut"),
}


def camera(tm, idx, lt):
    target, how = CAMS[idx]
    if idx == 5 and lt > 1.25:  # 「待った！」の後、ボードへ引く
        prev, target, k = CAMS[5][0], BOARD_CAM, ease((lt - 1.25) / 0.6)
        return tuple(lerp(a, b, k) for a, b in zip(prev, target))
    if how == "ease" and idx > -1:
        prev = CAMS[idx - 1][0] if idx - 1 in CAMS else WIDE
        if idx == 6:  # 5 の終わりはボードへ引いた構図
            prev = BOARD_CAM
        pre = GAPS.get(idx, 0.25) if idx else INTRO * 0.5
        k = ease((lt + pre) / 0.8)
        cam = tuple(lerp(a, b, k) for a, b in zip(prev, target))
    else:
        cam = target
    # ゆっくり寄り続ける（静止画っぽさを消す）
    cx, cy, z = cam
    return cx, cy, z * (1 + 0.012 * math.sin(tm * 0.5))


class Canvas:
    def __init__(self, cam, shake=(0, 0)):
        self.img = Image.new("RGB", (int(1280 * K), int(720 * K)))
        self.d = ImageDraw.Draw(self.img, "RGBA")
        self.cx, self.cy, self.z = cam
        self.sx, self.sy = shake

    # 世界座標 → ピクセル
    def P(self, *v):
        out = []
        for i in range(0, len(v), 2):
            out.append(((v[i] - self.cx) * self.z + 640 + self.sx) * K)
            out.append(((v[i + 1] - self.cy) * self.z + 360 + self.sy) * K)
        return out

    def L(self, n):
        return max(1, int(round(n * self.z * K)))

    def font(self, size, world=True):
        return _font(int(size * (self.z if world else 1) * K))

    # 図形（世界座標）
    def ell(self, x0, y0, x1, y1, fill=None, outline=None, w=0):
        self.d.ellipse(self.P(x0, y0, x1, y1), fill=fill, outline=outline, width=self.L(w) if w else 0)

    def circ(self, x, y, r, **kw):
        self.ell(x - r, y - r, x + r, y + r, **kw)

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, w=0, r=0):
        if r:
            self.d.rounded_rectangle(self.P(x0, y0, x1, y1), radius=self.L(r), fill=fill, outline=outline, width=self.L(w) if w else 0)
        else:
            self.d.rectangle(self.P(x0, y0, x1, y1), fill=fill, outline=outline, width=self.L(w) if w else 0)

    def poly(self, pts, fill=None, outline=None, w=0):
        flat = [c for p in pts for c in p]
        self.d.polygon(self.P(*flat), fill=fill)
        if outline and w:
            self.d.line(self.P(*(flat + flat[:2])), fill=outline, width=self.L(w), joint="curve")

    def line(self, pts, fill, w):
        flat = [c for p in pts for c in p]
        self.d.line(self.P(*flat), fill=fill, width=self.L(w), joint="curve")
        r = w / 2  # 丸い端
        for p in (pts[0], pts[-1]):
            self.circ(p[0], p[1], r * 0.95, fill=fill)

    def arc(self, box, a0, a1, fill, w):
        self.d.arc(self.P(*box), a0, a1, fill=fill, width=self.L(w))

    def chord(self, box, a0, a1, fill):
        self.d.chord(self.P(*box), a0, a1, fill=fill)

    def text(self, x, y, s, size, fill=None, stroke=0, sfill=(255, 255, 255), anchor="mm"):
        self.d.text(self.P(x, y), s, font=self.font(size), fill=fill or INK, anchor=anchor,
                    stroke_width=self.L(stroke) if stroke else 0, stroke_fill=sfill)

    # 画面座標（カメラの影響を受けない）
    def stext(self, x, y, s, size, fill, stroke=0, sfill=(0, 0, 0), anchor="mm", spacing=6):
        self.d.multiline_text((x * K, y * K), s, font=_font(int(size * K)), fill=fill, anchor=anchor, align="center",
                              stroke_width=int(stroke * K), stroke_fill=sfill, spacing=int(spacing * K))


FONT_DIR = "/usr/share/fonts/opentype/noto/"


@lru_cache(maxsize=256)
def _font(px):
    name = "NotoSansCJK-Black.ttc" if os.path.exists(FONT_DIR + "NotoSansCJK-Black.ttc") else "NotoSansCJK-Bold.ttc"
    return ImageFont.truetype(FONT_DIR + name, max(6, px), index=0)


INK = (58, 42, 40)
SKIN = (255, 228, 208)
SKIN_SH = (245, 200, 180)


# ---------- 背景 ----------
def room(c, tm, idx):
    sun = ease((tm - ST[6] + 0.3) / 2.5) if idx >= 6 else 0
    wall_top, wall_bot = mix((255, 246, 228), (255, 232, 205), sun), mix((250, 230, 200), (255, 214, 175), sun)
    for i in range(12):  # 壁のグラデーション
        y0 = -200 + i * 70
        c.rect(-400, y0, 1700, y0 + 72, fill=mix(wall_top, wall_bot, i / 11))
    for y in range(0, 560, 56):  # 壁紙の柄
        for x in range(-280 + (y // 56 % 2) * 28, 1600, 56):
            c.circ(x, y + 20, 3.5, fill=(240, 212, 178, 150))
    c.rect(-400, 520, 1700, 532, fill=(225, 190, 150))  # 腰板
    # 窓
    sky1 = mix((150, 205, 245), (255, 170, 120), sun)
    sky2 = mix((205, 235, 255), (255, 225, 160), sun)
    c.rect(60, 50, 310, 270, fill=(255, 255, 255), outline=INK, w=4, r=10)
    for i in range(8):
        c.rect(72, 62 + i * 25.5, 298, 62 + (i + 1) * 25.5 + 1, fill=mix(sky1, sky2, i / 7))
    if sun > 0:
        sy = 268 - 120 * sun
        c.circ(185, sy, 58, fill=(255, 210, 120, 120))
        c.circ(185, sy, 38, fill=(255, 150, 70))
    else:
        for k, (x, y) in enumerate([(120, 110), (240, 150)]):  # 流れる雲
            x = 72 + (x - 72 + tm * 6) % 230
            c.circ(x, y, 14, fill=(255, 255, 255)); c.circ(x + 16, y - 6, 16, fill=(255, 255, 255)); c.circ(x + 32, y, 13, fill=(255, 255, 255))
    c.rect(60, 50, 310, 270, outline=INK, w=5, r=10)
    c.line([(185, 52), (185, 268)], INK, 4)
    c.line([(62, 160), (308, 160)], INK, 4)
    c.rect(48, 268, 322, 284, fill=(200, 150, 110), outline=INK, w=3, r=4)
    # 観葉植物
    c.rect(-10, 470, 60, 560, fill=(230, 140, 90), outline=INK, w=3, r=8)
    for a in range(-60, 61, 30):
        r = math.radians(a - 90 + 4 * math.sin(tm * 1.3 + a))
        c.line([(25, 475), (25 + math.cos(r) * 90, 475 + math.sin(r) * 100)], (90, 170, 100), 14)
    # 床
    c.rect(-400, 560, 1700, 900, fill=(206, 160, 115))
    for x in range(-400, 1700, 110):
        c.line([(x, 560), (x - 60, 900)], (190, 144, 100), 3)
    c.rect(-400, 556, 1700, 566, fill=(170, 120, 80))
    # ラグ
    c.ell(60, 590, 560, 690, fill=(255, 190, 170, 200))
    c.ell(100, 600, 520, 680, outline=(255, 255, 255, 160), w=3)
    # 本棚（フクロウの止まり木）
    c.rect(1030, 320, 1250, 560, fill=(165, 110, 72), outline=INK, w=4, r=4)
    cols = [(232, 96, 96), (96, 150, 225), (245, 205, 85), (112, 192, 122), (198, 122, 200), (255, 150, 90)]
    for i, col in enumerate(cols):
        h = 70 + (i * 13) % 20
        c.rect(1046 + i * 32, 432 - h, 1072 + i * 32, 432, fill=col, outline=INK, w=2, r=3)
    c.rect(1030, 432, 1250, 444, fill=(130, 85, 55))
    for i in range(3):
        c.circ(1070 + i * 60, 500, 22, fill=(250, 200, 60), outline=(170, 120, 20), w=3)  # 貯金の壺っぽいコイン
    c.rect(1030, 320, 1250, 332, fill=(130, 85, 55))


def effect_bg(c, tm, kind, k=1.0):
    """漫画的な効果背景（画面全体）。"""
    W, H = 1280 * K, 720 * K
    if kind == "gloom":
        c.d.rectangle((0, 0, W, H), fill=(60, 80, 140, int(235 * k)))
        rng = np.random.default_rng(3)
        for i in range(46):
            x = rng.uniform(0, 1280)
            ln = rng.uniform(200, 560)
            c.d.line((x * K, 0, x * K, ln * K * k), fill=(140, 160, 210, 200), width=int(rng.uniform(2, 6) * K))
    elif kind == "burst":
        cols = [(255, 214, 80), (255, 236, 150)]
        cx, cy = 640 * K, 330 * K
        n = 28
        rot = tm * 0.6
        for i in range(n):
            a0 = rot + i * 2 * math.pi / n
            a1 = a0 + math.pi / n
            R = 2000 * K
            c.d.polygon([(cx, cy), (cx + math.cos(a0) * R, cy + math.sin(a0) * R), (cx + math.cos(a1) * R, cy + math.sin(a1) * R)],
                        fill=cols[i % 2] + (int(255 * k),))
    elif kind == "impact":
        c.d.rectangle((0, 0, W, H), fill=(255, 90, 80, int(220 * k)))
        cx, cy = 900 * K, 300 * K
        rng = np.random.default_rng(5)
        for i in range(60):
            a = rng.uniform(0, 2 * math.pi)
            r0 = rng.uniform(200, 400) * K
            c.d.line((cx + math.cos(a) * r0, cy + math.sin(a) * r0, cx + math.cos(a) * 2000 * K, cy + math.sin(a) * 2000 * K),
                     fill=(255, 255, 255, 170), width=int(rng.uniform(2, 8) * K))


# ---------- 小物 ----------
def coin(c, x, y, r, face=True):
    c.circ(x, y + r * 0.12, r, fill=(200, 140, 30))
    c.circ(x, y, r, fill=(255, 205, 60), outline=(175, 120, 20), w=max(1.5, r / 9))
    c.circ(x, y, r * 0.72, outline=(235, 170, 35), w=max(1, r / 14))
    if face and r * c.z > 7:
        c.text(x, y + r * 0.04, "¥", int(r * 1.05), fill=(185, 120, 15))
    c.ell(x - r * 0.55, y - r * 0.62, x - r * 0.1, y - r * 0.35, fill=(255, 245, 200, 200))


def sparkle(c, x, y, r, col=(255, 215, 60)):
    c.poly([(x, y - r), (x + r * .28, y - r * .28), (x + r, y), (x + r * .28, y + r * .28),
            (x, y + r), (x - r * .28, y + r * .28), (x - r, y), (x - r * .28, y - r * .28)], fill=col)


def bill(c, cx, cy, s, fade=0.0):
    w, h = 230 * s, 115 * s
    col = mix((205, 232, 205), (225, 225, 225), fade)
    ink = mix((60, 115, 75), (150, 150, 150), fade)
    c.rect(cx - w / 2, cy - h / 2 + 4 * s, cx + w / 2, cy + h / 2 + 4 * s, fill=(0, 0, 0, 40), r=8 * s)
    c.rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, fill=col, outline=ink, w=3 * s, r=8 * s)
    c.rect(cx - w / 2 + 8 * s, cy - h / 2 + 8 * s, cx + w / 2 - 8 * s, cy + h / 2 - 8 * s, outline=ink, w=1.5 * s, r=5 * s)
    c.circ(cx + w * 0.27, cy, h * 0.3, fill=mix((230, 245, 230), (240, 240, 240), fade), outline=ink, w=2 * s)
    c.text(cx - w * 0.13, cy - h * 0.05, "10000", int(30 * s), fill=ink)
    c.text(cx - w * 0.13, cy + h * 0.28, "壱万円", int(14 * s), fill=ink)


def piggy(c, x, y, s=1.0, wob=0.0):
    pink, dk, lt = (255, 175, 195), (215, 110, 140), (255, 210, 222)
    c.ell(x - 75 * s, y + 52 * s, x + 75 * s, y + 70 * s, fill=(0, 0, 0, 35))
    for lx in (-48, -18, 18, 40):
        c.rect(x + lx * s, y + 25 * s, x + (lx + 20) * s, y + 62 * s, fill=pink, outline=dk, w=3 * s, r=6 * s)
    c.ell(x - 80 * s, y - 55 * s + wob, x + 80 * s, y + 50 * s + wob, fill=pink, outline=dk, w=4 * s)
    c.ell(x - 55 * s, y - 40 * s + wob, x + 10 * s, y - 5 * s + wob, fill=lt)
    c.ell(x + 62 * s, y - 18 * s + wob, x + 100 * s, y + 22 * s + wob, fill=pink, outline=dk, w=4 * s)
    for nx in (74, 87):
        c.ell(x + (nx - 3) * s, y - 2 * s + wob, x + (nx + 3) * s, y + 8 * s + wob, fill=dk)
    c.poly([(x + 20 * s, y - 48 * s + wob), (x + 34 * s, y - 82 * s + wob), (x + 52 * s, y - 42 * s + wob)], fill=pink, outline=dk, w=3 * s)
    c.ell(x + 30 * s, y - 20 * s + wob, x + 42 * s, y - 6 * s + wob, fill=INK)
    c.circ(x + 34 * s, y - 16 * s + wob, 2.5 * s, fill=(255, 255, 255))
    c.ell(x + 22 * s, y + 4 * s + wob, x + 46 * s, y + 14 * s + wob, fill=(255, 140, 160, 160))
    c.rect(x - 30 * s, y - 57 * s + wob, x + 14 * s, y - 47 * s + wob, fill=dk, r=4 * s)
    c.arc((x - 108 * s, y - 20 * s, x - 76 * s, y + 10 * s), 90, 330, dk, 4 * s)  # しっぽ


# ---------- キャラクター ----------
def eye(c, x, y, s, mood, blink, look=(0, 0)):
    """アニメ風の目。"""
    if blink or mood in ("happy", "excited"):
        c.arc((x - 22 * s, y - 8 * s, x + 22 * s, y + 26 * s), 200, 340, INK, 5.5 * s)
        if mood == "excited":
            sparkle(c, x, y - 24 * s, 9 * s)
        return
    if mood == "shock":
        c.ell(x - 22 * s, y - 28 * s, x + 22 * s, y + 28 * s, fill=(255, 255, 255), outline=INK, w=4 * s)
        c.circ(x, y, 6 * s, fill=INK)
        return
    lx, ly = look
    c.ell(x - 20 * s, y - 27 * s, x + 20 * s, y + 27 * s, fill=(255, 255, 255))
    ix, iy = x + lx * 4 * s, y + ly * 3 * s + 2 * s
    c.ell(ix - 16 * s, iy - 23 * s, ix + 16 * s, iy + 23 * s, fill=(120, 70, 50))
    c.ell(ix - 13 * s, iy - 8 * s, ix + 13 * s, iy + 21 * s, fill=(185, 110, 70))
    c.ell(ix - 8 * s, iy - 12 * s, ix + 8 * s, iy + 12 * s, fill=(45, 25, 25))
    c.ell(ix - 12 * s, iy - 18 * s, ix - 1 * s, iy - 5 * s, fill=(255, 255, 255))
    c.circ(ix + 8 * s, iy + 12 * s, 3.5 * s, fill=(255, 255, 255, 220))
    c.arc((x - 23 * s, y - 31 * s, x + 23 * s, y + 31 * s), 195, 345, INK, 6 * s)  # まつげ
    c.line([(x + 18 * s, y - 20 * s), (x + 27 * s, y - 27 * s)], INK, 4 * s)


def mouth(c, x, y, s, v, mood):
    red, tongue = (190, 70, 80), (240, 130, 130)
    if v == "a":
        c.ell(x - 14 * s, y - 6 * s, x + 14 * s, y + 20 * s, fill=red, outline=INK, w=3 * s)
        c.ell(x - 8 * s, y + 8 * s, x + 8 * s, y + 18 * s, fill=tongue)
    elif v == "i":
        c.ell(x - 15 * s, y - 2 * s, x + 15 * s, y + 8 * s, fill=red, outline=INK, w=3 * s)
        c.rect(x - 11 * s, y - 1 * s, x + 11 * s, y + 3 * s, fill=(255, 255, 255))
    elif v == "u":
        c.ell(x - 7 * s, y - 3 * s, x + 7 * s, y + 10 * s, fill=red, outline=INK, w=3 * s)
    elif v == "e":
        c.ell(x - 13 * s, y - 3 * s, x + 13 * s, y + 12 * s, fill=red, outline=INK, w=3 * s)
        c.ell(x - 7 * s, y + 4 * s, x + 7 * s, y + 11 * s, fill=tongue)
    elif v == "o":
        c.ell(x - 10 * s, y - 5 * s, x + 10 * s, y + 16 * s, fill=red, outline=INK, w=3 * s)
    elif mood == "shock":
        c.ell(x - 8 * s, y - 2 * s, x + 8 * s, y + 16 * s, fill=red, outline=INK, w=3 * s)
    elif mood in ("happy", "excited"):
        c.chord((x - 15 * s, y - 12 * s, x + 15 * s, y + 14 * s), 0, 180, red)
        c.arc((x - 15 * s, y - 12 * s, x + 15 * s, y + 14 * s), 0, 180, INK, 3 * s)
    else:
        c.arc((x - 13 * s, y - 10 * s, x + 13 * s, y + 8 * s), 25, 155, INK, 3.5 * s)


def yui(c, tm, mood, idx):
    x = 235
    speaking = talking("yui", tm)
    breathe = math.sin(tm * 2.2) * 2.5
    hop = 0
    if mood == "excited":
        hop = -abs(math.sin(tm * 8)) * 22
    if mood == "shock":
        k = max(0, tm - ST[2])
        hop = -14 * math.exp(-k * 4) * abs(math.sin(k * 30))
    nod = math.sin(tm * 9) * 2.5 if speaking else 0
    y = 330 + hop  # 頭の中心
    hy = y + breathe * 0.5 + nod
    # 影
    c.ell(x - 75, 588, x + 75, 606, fill=(0, 0, 0, 45))
    # 後ろ髪
    hair, hair_sh, hair_hi = (88, 58, 48), (64, 40, 34), (140, 98, 80)
    c.rect(x - 95, hy - 40, x + 95, hy + 135, fill=hair, r=40)
    c.ell(x - 100, hy - 105, x + 100, hy + 80, fill=hair)
    # 脚
    c.rect(x - 40, y + 200, x - 14, 594, fill=SKIN, outline=INK, w=3)
    c.rect(x + 14, y + 200, x + 40, 594, fill=SKIN, outline=INK, w=3)
    c.rect(x - 46, 580, x - 10, 600, fill=(150, 70, 60), outline=INK, w=3, r=8)
    c.rect(x + 10, 580, x + 46, 600, fill=(150, 70, 60), outline=INK, w=3, r=8)
    # スカート
    by = y + 95 + breathe
    c.poly([(x - 62, by + 75), (x + 62, by + 75), (x + 88, by + 150), (x - 88, by + 150)], fill=(60, 75, 130), outline=INK, w=4)
    for k in (-40, 0, 40):
        c.line([(x + k * 0.7, by + 80), (x + k, by + 146)], (45, 58, 105), 3)
    # 腕（ポーズ）
    sl, sr = (x - 52, by + 10), (x + 52, by + 10)
    if mood == "excited":
        hl, hr = (x - 120, by - 95 + math.sin(tm * 8) * 8), (x + 120, by - 95 - math.sin(tm * 8) * 8)
    elif mood == "shock":
        hl, hr = (x - 62, by - 70), (x + 62, by - 70)
    elif speaking:
        hr = (x + 108, by + 30 + math.sin(tm * 6) * 10)
        hl = (x - 70, by + 100)
    elif mood == "happy":
        hl, hr = (x - 40, by + 70), (x + 40, by + 70)
    else:
        hl, hr = (x - 72, by + 100), (x + 72, by + 100)
    for s0, h in ((sl, hl), (sr, hr)):
        mid = ((s0[0] + h[0]) / 2 + (8 if h[0] > x else -8), (s0[1] + h[1]) / 2)
        c.line([s0, mid, h], INK, 26)
        c.line([s0, mid, h], (255, 255, 255), 19)
        c.circ(h[0], h[1], 13, fill=SKIN, outline=INK, w=3)
    # 胴体（セーラー服）
    c.rect(x - 62, by, x + 62, by + 85, fill=(255, 255, 255), outline=INK, w=4, r=26)
    c.poly([(x - 60, by + 4), (x + 60, by + 4), (x + 40, by + 40), (x, by + 58), (x - 40, by + 40)], fill=(60, 75, 130), outline=INK, w=3)
    c.poly([(x - 30, by + 6), (x + 30, by + 6), (x, by + 44)], fill=(255, 255, 255))
    c.poly([(x, by + 44), (x - 26, by + 30), (x - 30, by + 58)], fill=(230, 70, 80), outline=INK, w=2.5)
    c.poly([(x, by + 44), (x + 26, by + 30), (x + 30, by + 58)], fill=(230, 70, 80), outline=INK, w=2.5)
    c.circ(x, by + 44, 7, fill=(210, 50, 65), outline=INK, w=2)
    # 首・顔
    c.rect(x - 14, hy + 60, x + 14, by + 8, fill=SKIN_SH)
    c.ell(x - 82, hy - 88, x + 82, hy + 82, fill=SKIN, outline=INK, w=4)
    # 前髪
    bangs = [(x - 92, hy - 10), (x - 86, hy - 70), (x - 50, hy - 105), (x, hy - 112), (x + 50, hy - 105), (x + 86, hy - 70), (x + 92, hy - 10),
             (x + 74, hy - 30), (x + 60, hy - 14), (x + 46, hy - 46), (x + 22, hy - 20), (x + 6, hy - 50), (x - 16, hy - 18),
             (x - 34, hy - 48), (x - 52, hy - 16), (x - 66, hy - 40), (x - 80, hy - 8)]
    c.poly(bangs, fill=hair, outline=INK, w=3)
    c.arc((x - 60, hy - 100, x + 40, hy - 50), 200, 290, hair_hi, 6)  # 天使の輪
    c.arc((x - 20, hy - 104, x + 70, hy - 54), 250, 330, hair_hi, 6)
    # アホ毛
    sway = math.sin(tm * 3) * 6
    c.line([(x + 4, hy - 110), (x + 18 + sway, hy - 140), (x + 36 + sway, hy - 136)], hair, 6)
    # サイドの髪
    for sgn in (-1, 1):
        c.poly([(x + sgn * 82, hy - 40), (x + sgn * 98, hy + 30), (x + sgn * 88, hy + 110), (x + sgn * 72, hy + 40)], fill=hair, outline=INK, w=3)
    # コインの髪飾り
    coin(c, x + 70, hy - 82, 16)
    # 眉
    by_ = hy - 30
    if mood == "shock":
        c.line([(x - 50, by_ - 6), (x - 18, by_ - 14)], hair_sh, 5); c.line([(x + 18, by_ - 14), (x + 50, by_ - 6)], hair_sh, 5)
    elif mood == "excited" or mood == "happy":
        c.arc((x - 52, by_ - 14, x - 16, by_ + 4), 200, 340, hair_sh, 4.5); c.arc((x + 16, by_ - 14, x + 52, by_ + 4), 200, 340, hair_sh, 4.5)
    else:
        c.line([(x - 50, by_ - 6), (x - 20, by_ - 9)], hair_sh, 4.5); c.line([(x + 20, by_ - 9), (x + 50, by_ - 6)], hair_sh, 4.5)
    blink = (tm % 3.4) < 0.11 or (tm % 7.9) < 0.11
    look = (1, 0) if idx in (1, 3, 5) else (0.4, 0)
    for ex in (-33, 33):
        eye(c, x + ex, hy + 4, 1.0, mood, blink, look)
    # ほっぺ
    for ex in (-54, 54):
        c.ell(x + ex - 16, hy + 30, x + ex + 16, hy + 44, fill=(255, 140, 140, 110))
    if mood == "shock":
        for ex in (-36, -22, -8):  # 顔の縦線
            c.line([(x + ex, hy - 70), (x + ex, hy - 38)], (90, 110, 170), 3)
        c.poly([(x + 92, hy - 52), (x + 82, hy - 22), (x + 102, hy - 22)], fill=(130, 195, 255))
        c.circ(x + 92, hy - 16, 11, fill=(130, 195, 255))
    v = mouth_of("yui", tm)
    mouth(c, x, hy + 46, 1.0, v, mood)


def owl(c, tm, pose, idx):
    arrive = ST[1] - 1.0
    k = ease((tm - arrive) / 0.9)
    if k <= 0:
        return
    x = 1140 + (1 - k) ** 2 * 420
    y = 250 - (1 - k) * 230 + math.sin(tm * 2.0) * 3
    speaking = talking("owl", tm)
    if speaking:
        y += math.sin(tm * 8) * 2
    flap = math.sin(tm * 26) * 40 * (1 - k)
    br, br_dk, belly, face = (150, 100, 66), (115, 75, 48), (240, 215, 175), (238, 205, 160)
    c.ell(x - 70, 318, x + 70, 332, fill=(0, 0, 0, 40))
    # しっぽ
    c.poly([(x - 30, y + 95), (x + 30, y + 95), (x, y + 130)], fill=br_dk, outline=INK, w=3)
    # 左の翼
    c.poly([(x - 66, y - 5), (x - 108 - flap / 2, y + 50 - flap), (x - 92, y + 92), (x - 52, y + 96)], fill=br_dk, outline=INK, w=3)
    # 体
    c.ell(x - 78, y - 85, x + 78, y + 112, fill=br, outline=INK, w=5)
    c.ell(x - 52, y + 5, x + 52, y + 104, fill=belly)
    for r in range(3):  # 胸のうろこ模様
        for q in range(-2, 3):
            px, py = x + q * 20 + (r % 2) * 10, y + 30 + r * 22
            if abs(px - x) < 44 - r * 4:
                c.arc((px - 9, py - 6, px + 9, py + 8), 20, 160, (200, 165, 120), 2.5)
    # 顔のディスク
    c.ell(x - 70, y - 64, x + 2, y + 12, fill=face)
    c.ell(x - 2, y - 64, x + 70, y + 12, fill=face)
    # 耳
    c.poly([(x - 62, y - 55), (x - 74, y - 112), (x - 28, y - 74)], fill=br, outline=INK, w=3)
    c.poly([(x + 62, y - 55), (x + 74, y - 112), (x + 28, y - 74)], fill=br, outline=INK, w=3)
    # 目＋メガネ
    blink = (tm % 4.1) < 0.12
    for ex in (-33, 33):
        ex_ = x + ex
        c.circ(ex_, y - 26, 27, fill=(255, 255, 255))
        if blink:
            c.line([(ex_ - 15, y - 26), (ex_ + 15, y - 26)], INK, 4)
        elif pose == "stop":
            c.line([(ex_ - 14, y - 34 + (6 if ex < 0 else -6)), (ex_ + 14, y - 34 - (6 if ex < 0 else -6))], INK, 5)  # キリッ
            c.circ(ex_, y - 22, 12, fill=(250, 190, 40)); c.circ(ex_, y - 22, 6, fill=INK)
        else:
            lx = -4 if idx in (1, 3, 5) else -2
            c.circ(ex_ + lx, y - 24, 15, fill=(250, 190, 40))
            c.circ(ex_ + lx, y - 24, 8, fill=INK)
            c.circ(ex_ + lx - 5, y - 30, 4, fill=(255, 255, 255))
        c.circ(ex_, y - 26, 29, outline=(70, 60, 60), w=4.5)
        c.arc((ex_ - 22, y - 50, ex_ + 22, y - 6), 200, 250, (255, 255, 255, 200), 3)  # レンズの反射
    c.line([(x - 5, y - 28), (x + 5, y - 28)], (70, 60, 60), 4.5)
    # 眉毛の羽
    c.line([(x - 58, y - 62), (x - 14, y - 52)], br_dk, 7)
    c.line([(x + 14, y - 52), (x + 58, y - 62)], br_dk, 7)
    # くちばし（母音で開閉）
    v = mouth_of("owl", tm)
    open_ = {"a": 14, "o": 11, "e": 9, "u": 6, "i": 5}.get(v, 0)
    c.poly([(x - 12, y + 2), (x + 12, y + 2), (x, y + 18)], fill=(250, 180, 50), outline=INK, w=2.5)
    if open_:
        c.poly([(x - 10, y + 16), (x + 10, y + 16), (x, y + 18 + open_)], fill=(220, 140, 30), outline=INK, w=2.5)
        c.rect(x - 9, y + 13, x + 9, y + 17, fill=(150, 50, 60))
    # 右の翼（ジェスチャー）
    if pose == "stop":
        c.poly([(x + 62, y + 10), (x + 70, y - 70), (x + 100, y - 110), (x + 118, y - 95), (x + 105, y - 60), (x + 82, y + 50)],
               fill=br_dk, outline=INK, w=3)
        for f in range(3):
            c.line([(x + 82 + f * 8, y - 70 + f * 5), (x + 104 + f * 8, y - 100 + f * 6)], INK, 2.5)
    elif pose == "point":  # ボードを指す
        wob = math.sin(tm * 4) * 5
        c.poly([(x - 50, y + 5), (x - 120, y - 20 + wob), (x - 150, y - 34 + wob), (x - 128, y - 4 + wob), (x - 60, y + 50)],
               fill=br_dk, outline=INK, w=3)
        c.poly([(x + 66, y - 5), (x + 104 + flap / 2, y + 50 - flap), (x + 90, y + 92), (x + 52, y + 96)], fill=br_dk, outline=INK, w=3)
    else:
        c.poly([(x + 66, y - 5), (x + 108 + flap / 2, y + 50 - flap), (x + 92, y + 92), (x + 52, y + 96)], fill=br_dk, outline=INK, w=3)
    # 博士帽
    tas = math.sin(tm * 2.6) * 8
    c.poly([(x - 62, y - 92), (x, y - 120), (x + 62, y - 92), (x, y - 66)], fill=(45, 45, 65), outline=INK, w=3)
    c.rect(x - 30, y - 92, x + 30, y - 72, fill=(45, 45, 65))
    c.circ(x, y - 93, 5, fill=(240, 200, 60))
    c.line([(x, y - 93), (x + 46, y - 82), (x + 48 + tas, y - 48)], (240, 200, 60), 3.5)
    c.ell(x + 42 + tas, y - 52, x + 56 + tas, y - 36, fill=(240, 200, 60))
    # 足
    for fx in (-22, 22):
        for t_ in (-8, 0, 8):
            c.line([(x + fx, y + 108), (x + fx + t_, y + 120)], (245, 175, 50), 5)


# ---------- ホワイトボード ----------
BX0, BY0, BX1, BY1 = 360, 40, 960, 410
BCX = (BX0 + BX1) / 2


def board(c, title, col=(90, 150, 225)):
    c.rect(BX0 + 8, BY0 + 10, BX1 + 8, BY1 + 10, fill=(0, 0, 0, 40), r=20)
    c.rect(BX0, BY0, BX1, BY1, fill=(253, 253, 250), outline=INK, w=5, r=20)
    c.rect(BX0 + 3, BY0 + 3, BX1 - 3, BY0 + 64, fill=col, r=18)
    c.rect(BX0 + 3, BY0 + 40, BX1 - 3, BY0 + 64, fill=col)
    c.text(BCX, BY0 + 34, title, 30, fill=(255, 255, 255))
    for x in (420, 900):  # ボードのマグネット
        c.circ(x, BY0 + 2, 8, fill=(230, 80, 80), outline=INK, w=2)


def pill(c, x, y, s, size, fill=(255, 236, 140), ink=INK, k=1.0):
    if k <= 0:
        return
    sc = back(k)
    w = len(s) * size * 0.62 + 40
    h = size + 26
    c.rect(x - w / 2 * sc, y - h / 2 * sc, x + w / 2 * sc, y + h / 2 * sc, fill=fill, outline=INK, w=3.5, r=h / 2 * sc)
    if sc > 0.5:
        c.text(x, y, s, int(size * min(1, sc)), fill=ink)


def panel_piggy(c, lt):
    board(c, "お年玉 1万円", (240, 120, 150))
    drop = ease((lt - 0.3) / 1.0)
    landed = lt > 1.3
    wob = math.sin((lt - 1.3) * 25) * 5 * math.exp(-(lt - 1.3) * 4) if landed else 0
    piggy(c, BCX, 300, 1.25, wob)
    if not landed:
        bill(c, BCX - 10, 140 + drop * 110, 0.55 * (1 - drop * 0.75))
    else:
        for i in range(3):
            a = (lt - 1.3) * 2
            if a < 1:
                sparkle(c, BCX - 60 + i * 60, 180 - a * 40 - i * 8, 10 * (1 - a) + 3)
        c.text(BCX, 155, "ちょきん！", 28, fill=(230, 90, 130), stroke=3)


def panel_inflation(c, lt, dur):
    board(c, "物価が上がると…（インフレ）", (240, 140, 60))
    k = ease((lt - 1.2) / (dur - 3.0))
    years = 36 * k
    c.text(BCX, 135, f"{int(years)}年後", 44, fill=(220, 80, 60))
    # 左：お札の価値
    val = 1 / 1.02 ** years
    s = 0.62 * math.sqrt(val) + 0.12
    bill(c, 510, 230, s, fade=1 - val)
    c.rect(430, 290, 590, 306, fill=(230, 230, 230), r=8)
    c.rect(430, 290, 430 + 160 * val, 306, fill=(90, 170, 110), r=8)
    c.text(510, 330, f"1万円の価値 {int(10000 * val):,}円分", 19, fill=(70, 120, 80))
    # 右：アイスの値段
    ix, iy = 810, 215
    c.poly([(ix - 30, iy + 5), (ix + 30, iy + 5), (ix, iy + 85)], fill=(230, 180, 110), outline=INK, w=3)
    for j in range(3):
        c.line([(ix - 22 + j * 15, iy + 10), (ix - 5 + j * 12, iy + 60)], (200, 145, 80), 2)
    c.circ(ix, iy - 15, 36, fill=(255, 190, 210), outline=INK, w=3)
    c.circ(ix - 12, iy - 25, 7, fill=(255, 230, 240))
    price = int(round(100 * 1.02 ** years))
    c.text(ix, 330, f"アイス {price}円", 22, fill=(220, 80, 60))
    a = (lt * 2) % 1
    c.poly([(ix + 60, iy + 10 - a * 20), (ix + 75, iy - 10 - a * 20), (ix + 90, iy + 10 - a * 20)], fill=(230, 80, 60, int(255 * (1 - a))))
    pill(c, BCX, 380, "72 ÷ 2 ＝ 36年で 価値が半分", 24, k=ease((lt - 4.2) / 0.4))


def panel_compound(c, lt, dur):
    board(c, "複利でふえると…", (70, 170, 110))
    k = ease((lt - 0.5) / (dur - 3.2))
    years = 14.4 * k
    val = 10000 * 1.05 ** years
    c.text(BCX, 132, f"年利5% … {int(years)}年後  {int(val):,}円", 28, fill=(40, 120, 70))
    ox, oy, gw, gh = 430, 380, 480, 200
    c.line([(ox, oy), (ox + gw, oy)], INK, 3)
    c.line([(ox, oy), (ox, oy - gh - 10)], INK, 3)
    for v, lab in ((1, "1万"), (2, "2万")):
        yy = oy - gh * (v / 2)
        for xx in range(ox, ox + gw, 18):
            c.line([(xx, yy), (xx + 8, yy)], (200, 200, 200), 2)
        c.text(ox - 30, yy, lab, 18, fill=(130, 130, 130))
    n = 15
    bw = gw / n
    for i in range(n):
        if i > years:
            break
        h = gh / 2 * 1.05 ** min(i, years)
        grow = ease(years - i + 0.3)
        c.rect(ox + i * bw + 5, oy - h * grow, ox + (i + 1) * bw - 5, oy, fill=(60, 170, 100), r=4)
        c.rect(ox + i * bw + 5, oy - min(h, gh / 2) * grow, ox + (i + 1) * bw - 5, oy, fill=(175, 220, 185), r=4)
    top_i = min(int(years), n - 1)
    hc = gh / 2 * 1.05 ** years
    coin(c, ox + (top_i + 0.5) * bw, oy - hc - 20, 16 + 8 * k)
    for j, (lab, col) in enumerate((("元本", (175, 220, 185)), ("増えた分", (60, 170, 100)))):
        c.rect(ox + 20 + j * 90, 168, ox + 36 + j * 90, 184, fill=col, r=3)
        c.text(ox + 42 + j * 90, 176, lab, 16, fill=(90, 90, 90), anchor="lm")
    pill(c, 760, 205, "72 ÷ 5 ＝ 約14年で 2倍！", 24, fill=(200, 235, 255), k=ease((lt - 3.0) / 0.4))


def panel_rules(c, lt):
    board(c, "投資のコツ", (90, 130, 220))
    items = [("少しずつ", (90, 160, 230)), ("長く", (90, 185, 120)), ("分散", (240, 150, 60))]
    for i, (s, col) in enumerate(items):
        k = back((lt - 1.7 - i * 0.8) / 0.35) if lt > 1.7 + i * 0.8 else 0
        if k <= 0:
            continue
        cx, cy = 500 + i * 160, 200
        w, h = 66 * k, 80 * k
        c.rect(cx - w, cy - h, cx + w, cy + h, fill=(255, 255, 255), outline=col, w=5, r=16)
        if k > 0.7:
            if i == 0:  # 階段状のコイン
                for j in range(3):
                    for q in range(j + 1):
                        coin(c, cx - 30 + j * 30, cy + 10 - q * 12, 11, face=False)
            elif i == 1:  # 時計
                c.circ(cx, cy - 5, 30, fill=(240, 255, 240), outline=INK, w=3)
                a = lt * 3
                c.line([(cx, cy - 5), (cx + math.cos(a) * 22, cy - 5 + math.sin(a) * 22)], INK, 3)
                c.line([(cx, cy - 5), (cx, cy - 22)], INK, 4)
            else:  # かごに分けた卵
                c.rect(cx - 42, cy - 2, cx + 42, cy + 28, fill=(200, 150, 90), outline=INK, w=3, r=8)
                for j, ec in enumerate([(255, 120, 120), (120, 180, 255), (255, 220, 100)]):
                    c.ell(cx - 34 + j * 24, cy - 26, cx - 14 + j * 24, cy + 2, fill=ec, outline=INK, w=2)
            c.text(cx, cy + 56, s, 26, fill=col)
    k = (lt - 5.1) / 0.45
    if k > 0:
        sc = back(k)
        r = 8 * math.sin(min(1, k) * math.pi) * (1 - min(1, k))
        c.rect(BCX - 190 * sc, 340 - 32 * sc + r, BCX + 190 * sc, 340 + 32 * sc + r, fill=(255, 225, 90), outline=(200, 60, 60), w=4, r=12)
        if sc > 0.6:
            c.text(BCX, 340 + r, "NISA ＝ 利益が非課税！", 28, fill=(200, 50, 50))


def panel_tree(c, lt):
    board(c, "時間を味方に！", (70, 170, 110))
    g = ease(lt / 1.8)
    gx, gy = BCX, 395
    c.ell(gx - 120 * g, gy - 10, gx + 120 * g, gy + 10, fill=(150, 110, 70))
    c.poly([(gx - 14, gy), (gx + 14, gy), (gx + 8, gy - 170 * g), (gx - 8, gy - 170 * g)], fill=(140, 95, 60), outline=INK, w=3)
    for sgn in (-1, 1):
        c.line([(gx, gy - 100 * g), (gx + sgn * 60 * g, gy - 150 * g)], (140, 95, 60), 10)
    if g > 0.1:
        for (dx, dy, r) in [(0, -200, 95), (-80, -160, 70), (80, -160, 70), (-45, -240, 60), (45, -240, 60)]:
            c.circ(gx + dx * g, gy + dy * g, r * g, fill=(105, 185, 105))
        for (dx, dy, r) in [(-20, -215, 40), (60, -175, 30)]:
            c.circ(gx + dx * g, gy + dy * g, r * g, fill=(140, 210, 130))
    rng = np.random.default_rng(11)
    for i in range(9):
        t0 = 0.9 + i * 0.12
        if lt > t0:
            kk = back((lt - t0) / 0.3)
            px, py = gx + rng.uniform(-110, 110), gy - 170 + rng.uniform(-70, 40)
            coin(c, px, py + math.sin(lt * 3 + i) * 3, 15 * kk)
    if lt > 1.4:
        for i in range(4):
            a = lt * 2 + i * 1.6
            sparkle(c, gx + math.cos(a) * 150, gy - 190 + math.sin(a) * 90, 8 + 4 * math.sin(lt * 6 + i))


# ---------- 画面の重ね要素 ----------
def subtitle(c, idx, tm):
    if not (0 <= idx < len(LINES)):
        return
    ln = LINES[idx]
    if tm < ln["start"] - 0.1 or tm > ln["start"] + ln["dur"] + 0.25:
        return
    name, col = ("ユイ", (240, 100, 110)) if ln["who"] == "yui" else ("フクロウ先生", (150, 100, 66))
    d = c.d
    d.rounded_rectangle((70 * K, 598 * K, 1210 * K, 704 * K), radius=int(22 * K), fill=(255, 255, 255, 236), outline=INK, width=int(4 * K))
    nw = 34 + 25 * len(name)
    d.rounded_rectangle((92 * K, 578 * K, (92 + nw) * K, 616 * K), radius=int(14 * K), fill=col, outline=INK, width=int(3 * K))
    c.stext(92 + nw / 2, 597, name, 22, (255, 255, 255))
    txt = ln["text"]
    if len(txt) > 28:
        mid = len(txt) / 2
        cands = [i for i, ch in enumerate(txt) if ch in "、。！" and i < len(txt) - 2]
        cut = min(cands, key=lambda i: abs(i - mid)) if cands else int(mid)
        txt = txt[:cut + 1] + "\n" + txt[cut + 1:]
    c.stext(640, 653, txt, 32 if "\n" not in txt else 27, INK, spacing=5)


def title_card(c, tm):
    if tm > INTRO + 0.5:
        return
    rng = np.random.default_rng(2)
    for i in range(26):  # コインの雨
        x = rng.uniform(40, 1240)
        sp = rng.uniform(380, 620)
        y = -60 + (tm - rng.uniform(0, 0.8)) * sp
        if -60 < y < 800:
            c.d.ellipse(((x - 20) * K, (y - 20) * K, (x + 20) * K, (y + 20) * K), fill=(255, 205, 60), outline=(175, 120, 20), width=int(3 * K))
            c.stext(x, y, "¥", 22, (185, 120, 15))
    a = ease(tm / 0.45) * (1 - ease((tm - INTRO) / 0.5))
    y = 330 + (1 - a) * -450 if tm < 1 else 330 + (1 - a) * 500
    if a <= 0.01:
        return
    d = c.d
    d.rounded_rectangle((230 * K, (y - 125) * K, 1050 * K, (y + 125) * K), radius=int(36 * K), fill=(255, 214, 90), outline=INK, width=int(6 * K))
    d.rounded_rectangle((246 * K, (y - 109) * K, 1034 * K, (y + 109) * K), radius=int(28 * K), outline=(255, 255, 255), width=int(3 * K))
    c.stext(640, y - 35, "ユイと フクロウ先生", 70, INK, stroke=6, sfill=(255, 255, 255))
    c.stext(640, y + 58, "〜 お金と 72の法則 〜", 40, (200, 70, 50))


def ending(c, lt):
    """円形ワイプでまとめ画面へ。"""
    k = ease(lt / 0.6)
    W, H = int(1280 * K), int(720 * K)
    mask = Image.new("L", (W, H), 255)
    md = ImageDraw.Draw(mask)
    r = (1 - k) * 800 * K
    md.ellipse((235 * K - r, 330 * K - r, 235 * K + r, 330 * K + r), fill=0)
    card = Image.new("RGB", (W, H))
    cd = ImageDraw.Draw(card, "RGBA")
    for i in range(30):
        y0 = H * i / 30
        cd.rectangle((0, y0, W, y0 + H / 30 + 1), fill=mix((35, 55, 95), (60, 40, 90), i / 29))
    cc = Canvas((640, 360, 1.0))
    cc.img, cc.d = card, cd
    rng = np.random.default_rng(4)
    for i in range(40):
        x, y = rng.uniform(0, 1280), rng.uniform(0, 720)
        tw = 0.5 + 0.5 * math.sin(lt * 3 + i)
        cd.ellipse(((x - 2) * K, (y - 2) * K, (x + 2) * K, (y + 2) * K), fill=(255, 255, 255, int(160 * tw)))
    cc.stext(640, 130, "今日のまとめ", 44, (255, 214, 90))
    cd.rounded_rectangle((180 * K, 200 * K, 1100 * K, 330 * K), radius=int(24 * K), fill=(255, 255, 255, 30), outline=(255, 214, 90), width=int(3 * K))
    cc.stext(640, 265, "72 ÷ 年利(%) ＝ お金が2倍になる年数(約)", 44, (255, 255, 255))
    cc.stext(640, 390, "72 ÷ インフレ率(%) ＝ お金の価値が半分になる年数(約)", 28, (200, 220, 255))
    cc.stext(640, 450, "少しずつ・長く・分散して ／ NISAなら利益が非課税", 28, (200, 255, 210))
    cc.stext(640, 545, "※投資には元本割れのリスクがあります。数値は概算です。", 22, (255, 180, 180))
    cc.stext(1240, 700, "VOICEVOX:春日部つむぎ / VOICEVOX:ちび式じい", 17, (200, 200, 220), anchor="rm")
    for i in range(5):
        x, y = 360 + i * 140, 625 + math.sin(lt * 4 + i) * 8
        cd.ellipse(((x - 24) * K, (y - 24) * K, (x + 24) * K, (y + 24) * K), fill=(255, 205, 60), outline=(175, 120, 20), width=int(3 * K))
        cc.stext(x, y, "¥", 26, (185, 120, 15))
    c.img.paste(card, (0, 0), mask)


def frame(n):
    tm = n / FPS
    idx, lt = scene_at(tm)
    shake = (0, 0)
    if idx == 2 and 0 <= lt < 0.4:
        shake = (math.sin(lt * 90) * 8 * (1 - lt / 0.4), 0)
    if idx == 5 and 0 <= lt < 0.35:
        shake = (math.sin(lt * 110) * 10 * (1 - lt / 0.35), math.cos(lt * 90) * 5 * (1 - lt / 0.35))
    cam = camera(tm, min(idx, 7), lt)
    c = Canvas(cam, shake)
    room(c, tm, idx)
    # ボード
    dur = LINES[idx]["dur"] if 0 <= idx < len(LINES) else 1
    if idx <= 0:
        panel_piggy(c, max(0, tm - ST[0]))
    elif idx == 1:
        panel_inflation(c, lt, dur)
    elif idx in (2, 3):
        panel_compound(c, lt if idx == 3 else 0, LINES[3]["dur"])
    elif idx in (4, 5):
        panel_rules(c, lt if idx == 5 else 0)
    else:
        panel_tree(c, tm - ST[6])
    # 場面ごとの効果背景
    if idx == 2:
        effect_bg(c, tm, "gloom", ease((lt + 0.25) / 0.2))
    if idx == 4:
        effect_bg(c, tm, "burst", ease((lt + 0.25) / 0.2))
    if idx == 5 and lt < 1.25:
        effect_bg(c, tm, "impact", 1 - ease((lt - 0.9) / 0.35))
    mood = {2: "shock", 4: "excited", 6: "happy"}.get(idx, "normal")
    if idx == 5 and lt < 1.25:
        pose = "stop"
    elif talking("owl", tm) and idx in (1, 3, 5):
        pose = "point"
    else:
        pose = "idle"
    owl(c, tm, pose, idx)
    yui(c, tm, mood, idx)
    # 画面上の文字エフェクト
    if idx == 2 and lt > -0.1:
        k = back((lt + 0.1) / 0.3)
        c.stext(1010 + math.sin(tm * 30) * 3, 190, "ガーン！", int(100 * k) + 1, (255, 255, 255), stroke=8, sfill=(40, 50, 100))
    if idx == 4 and lt > -0.1:
        k = back((lt + 0.1) / 0.3)
        c.stext(1020, 200, "ぜんぶ\n投資！？", int(76 * k) + 1, (230, 80, 40), stroke=8, sfill=(255, 255, 255))
        for i in range(5):
            a = tm * 2 + i * 1.25
            x, y = 1020 + math.cos(a) * 170, 330 + math.sin(a) * 150
            c.d.ellipse(((x - 26) * K, (y - 26) * K, (x + 26) * K, (y + 26) * K), fill=(255, 205, 60), outline=(175, 120, 20), width=int(3 * K))
            c.stext(x, y, "¥", 28, (185, 120, 15))
    if idx == 5 and 0 <= lt < 1.25:
        k = back(lt / 0.25)
        c.stext(330, 200, "待った！", int(130 * k) + 1, (255, 255, 255), stroke=10, sfill=(180, 30, 40))
    subtitle(c, idx, tm)
    title_card(c, tm)
    if idx == len(LINES):
        ending(c, lt)
    return c.img.resize((OW, OH), Image.LANCZOS)


def render_chunk(rng_):
    a, b = rng_
    path = os.path.join(HERE, f"_part{a:05d}.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                           "-preset", "medium", path], stdin=subprocess.PIPE)
    for n in range(a, b):
        ff.stdin.write(frame(n).tobytes())
    ff.stdin.close()
    ff.wait()
    return path


def mix_audio():
    n = int(TOTAL * SR)
    voice = np.zeros(n, dtype=np.float32)
    for ln in LINES:
        s = int(ln["start"] * SR)
        voice[s:s + len(ln["pcm"])] += ln["pcm"]
    # BGM（セリフ中は小さく）
    music = sound.bgm(TOTAL)
    duck = np.ones(n)
    for ln in LINES:
        a, b = int((ln["start"] - 0.15) * SR), int((ln["start"] + ln["dur"] + 0.15) * SR)
        duck[max(0, a):b] = 0.28
    duck = np.convolve(duck, np.ones(4410) / 4410, mode="same")
    fade = np.minimum(1, np.minimum(np.arange(n) / (0.3 * SR), (n - np.arange(n)) / (1.2 * SR)))
    out = voice * 1.0 + music * duck * fade * 1.1
    for t0, kind in SFX:
        x = sound.sfx(kind)
        s = int(t0 * SR)
        e = min(n, s + len(x))
        out[s:e] += x[:e - s]
    out = out / max(1.0, np.abs(out).max() / 0.95)
    path = os.path.join(HERE, "_mix.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    return path


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for s in sys.argv[1:]:
            frame(int(float(s) * FPS)).save(os.path.join(HERE, f"preview_{s}.png"))
        sys.exit()
    wav = mix_audio()
    jobs = os.cpu_count() or 4
    step = math.ceil(NFRAMES / jobs)
    with Pool(jobs) as p:
        parts = p.map(render_chunk, [(a, min(NFRAMES, a + step)) for a in range(0, NFRAMES, step)])
    lst = os.path.join(HERE, "_parts.txt")
    open(lst, "w").write("".join(f"file '{q}'\n" for q in parts))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", OUT], check=True)
    for q in parts + [lst, wav]:
        os.remove(q)
    print(f"done: {OUT}  {TOTAL:.1f}s  {NFRAMES} frames")
