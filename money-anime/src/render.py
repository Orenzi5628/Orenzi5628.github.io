"""お金の2Dアニメ「ユイとネコ先生 〜大学生のためのお金と72の法則〜」のレンダラー。

- 音声: tts.py が VOICEVOX で作った line*.wav と visemes.json（母音タイミング）
- 絵: Pillow で 1 コマずつ描画（カメラのズーム・カット、口パク、エフェクト）
- 音: sound.py で合成した BGM と効果音をミックス
- 出力: ffmpeg で ../money-72-shorts.mp4（1080x1920 縦 / 30fps）

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

import cat
import sound

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "money-72-shorts.mp4")
OW, OH = 1080, 1920          # 出力解像度（ショート動画用の縦 9:16）
VW, VH = 720, 1280           # 設計座標の画面サイズ
SS = 2                       # スーパーサンプリング
K = OW / VW * SS             # 設計座標 → 描画ピクセル
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
GAPS = {1: 0.85, 5: 0.15}      # セリフ前の間（1: ネコ先生登場, 5: 「待った！」は食い気味）
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
    (ST[3] + 3.0, "pop"), (ST[3] + 5.6, "pop"),
    (ST[4] - 0.05, "kira"),
    (ST[5] - 0.1, "stop"),
    (ST[5] + 2.3, "pop"), (ST[5] + 3.3, "pop"), (ST[5] + 3.9, "pop"), (ST[5] + 4.5, "pop"), (ST[5] + 6.0, "kira"),
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


OPEN = {"a": 1.0, "o": 0.85, "e": 0.7, "u": 0.5, "i": 0.45, "n": 0.12}


def mouth_level(who, tm):
    """口の開き具合 (0..1) をなめらかに返す。母音ごとの山を重ねてから、少しぼかす。"""
    for ln in LINES:
        if ln["who"] == who and ln["start"] - 0.1 <= tm < ln["start"] + ln["dur"] + 0.1:
            def at(lt):
                best, shape = 0.0, None
                for a, b, raw in ln["vis"]:
                    v = raw.lower()
                    peak = OPEN.get(v, 0.0) * (0.3 if raw in "AIUEO" else 1.0)  # 大文字は無声化した母音
                    mid, half = (a + b) / 2, (b - a) / 2 + 0.05
                    k = 1 - abs(lt - mid) / half
                    if k > 0 and peak * math.sin(k * math.pi / 2) > best:
                        best, shape = peak * math.sin(k * math.pi / 2), v
                return best, shape
            lt = tm - ln["start"]
            vals = [at(lt + d)[0] for d in (-0.033, -0.016, 0, 0.016, 0.033)]
            return sum(vals) / len(vals), at(lt)[1]
    return 0.0, None


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
WIDE = (360, 640, 1.0)
BOARD_CAM = (360, 575, 1.07)
YUI_CLOSE = (195, 760, 1.75)
CAT_CLOSE = (565, 680, 1.62)
CAMS = {  # 場面ごとの (中心x, 中心y, ズーム, 切り替え方)
    -1: (WIDE, "cut"),
    0: ((360, 610, 1.03), "ease"),
    1: (BOARD_CAM, "ease"),
    2: (YUI_CLOSE, "cut"),
    3: (BOARD_CAM, "cut"),
    4: (YUI_CLOSE, "cut"),
    5: (CAT_CLOSE, "cut"),
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
        self.img = Image.new("RGB", (int(VW * K), int(VH * K)))
        self.d = ImageDraw.Draw(self.img, "RGBA")
        self.cx, self.cy, self.z = cam
        self.sx, self.sy = shake
        self.tx, self.ty, self.ts = 0.0, 0.0, 1.0   # 部品を置くための平行移動・拡大

    def at(self, dx, dy, sc=1.0):
        """with c.at(dx, dy): の中では、元の座標で描いた部品が (dx, dy) ずれて置かれる。"""
        canvas = self

        class _Ctx:
            def __enter__(self_):
                self_.prev = (canvas.tx, canvas.ty, canvas.ts)
                canvas.tx, canvas.ty, canvas.ts = dx, dy, sc

            def __exit__(self_, *a):
                canvas.tx, canvas.ty, canvas.ts = self_.prev
        return _Ctx()

    # 世界座標 → ピクセル
    def P(self, *v):
        out = []
        for i in range(0, len(v), 2):
            out.append(((v[i] * self.ts + self.tx - self.cx) * self.z + VW / 2 + self.sx) * K)
            out.append(((v[i + 1] * self.ts + self.ty - self.cy) * self.z + VH / 2 + self.sy) * K)
        return out

    def L(self, n):
        return max(1, int(round(n * self.ts * self.z * K)))

    def font(self, size, world=True):
        return _font(int(size * (self.z * self.ts if world else 1) * K))

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
    """縦画面用の部屋。床は y=1010。"""
    sun = ease((tm - ST[6] + 0.3) / 2.5) if idx >= 6 else 0
    wall_top, wall_bot = mix((255, 246, 228), (255, 232, 205), sun), mix((250, 230, 200), (255, 214, 175), sun)
    for i in range(16):
        y0 = -300 + i * 85
        c.rect(-500, y0, 1300, y0 + 87, fill=mix(wall_top, wall_bot, i / 15))
    for y in range(0, 1000, 56):
        for x in range(-480 + (y // 56 % 2) * 28, 1300, 56):
            c.circ(x, y + 20, 3.5, fill=(240, 212, 178, 150))
    c.rect(-500, 960, 1300, 972, fill=(225, 190, 150))  # 腰板
    # 窓（ふたりの間）
    wx0, wy0, wx1, wy1 = 285, 560, 445, 760
    sky1 = mix((150, 205, 245), (255, 170, 120), sun)
    sky2 = mix((205, 235, 255), (255, 225, 160), sun)
    c.rect(wx0, wy0, wx1, wy1, fill=(255, 255, 255), outline=INK, w=4, r=10)
    for i in range(8):
        c.rect(wx0 + 10, wy0 + 10 + i * 22.5, wx1 - 10, wy0 + 10 + (i + 1) * 22.5 + 1, fill=mix(sky1, sky2, i / 7))
    if sun > 0:
        sy = wy1 - 10 - 110 * sun
        c.circ(365, sy, 50, fill=(255, 210, 120, 120))
        c.circ(365, sy, 32, fill=(255, 150, 70))
    else:
        for k, (x, y) in enumerate([(300, 610), (360, 680)]):
            x = wx0 + 10 + (x - wx0 - 10 + tm * 6) % 140
            c.circ(x, y, 11, fill=(255, 255, 255)); c.circ(x + 12, y - 5, 13, fill=(255, 255, 255)); c.circ(x + 25, y, 10, fill=(255, 255, 255))
    c.rect(wx0, wy0, wx1, wy1, outline=INK, w=5, r=10)
    c.line([(365, wy0 + 2), (365, wy1 - 2)], INK, 4)
    c.line([(wx0 + 2, 660), (wx1 - 2, 660)], INK, 4)
    c.rect(wx0 - 10, wy1 - 2, wx1 + 10, wy1 + 12, fill=(200, 150, 110), outline=INK, w=3, r=4)
    # 本棚（ネコ先生の後ろ）
    c.rect(560, 700, 780, 1010, fill=(165, 110, 72), outline=INK, w=4, r=4)
    cols = [(232, 96, 96), (96, 150, 225), (245, 205, 85), (112, 192, 122), (198, 122, 200), (255, 150, 90)]
    for j, shelf in enumerate((800, 900)):
        for i, col in enumerate(cols):
            h = 60 + ((i + j) * 13) % 20
            c.rect(574 + i * 30, shelf - h, 598 + i * 30, shelf, fill=col, outline=INK, w=2, r=3)
        c.rect(560, shelf, 780, shelf + 10, fill=(130, 85, 55))
    c.rect(560, 700, 780, 712, fill=(130, 85, 55))
    # 観葉植物
    c.rect(-20, 900, 40, 1000, fill=(230, 140, 90), outline=INK, w=3, r=8)
    for a in range(-60, 61, 30):
        r = math.radians(a - 90 + 4 * math.sin(tm * 1.3 + a))
        c.line([(10, 905), (10 + math.cos(r) * 80, 905 + math.sin(r) * 95)], (90, 170, 100), 13)
    # 床
    c.rect(-500, 1000, 1300, 1700, fill=(206, 160, 115))
    for x in range(-500, 1300, 110):
        c.line([(x, 1000), (x - 80, 1700)], (190, 144, 100), 3)
    c.rect(-500, 996, 1300, 1006, fill=(170, 120, 80))
    c.ell(20, 1030, 400, 1120, fill=(255, 190, 170, 200))
    c.ell(50, 1042, 370, 1108, outline=(255, 255, 255, 160), w=3)


def effect_bg(c, tm, kind, k=1.0):
    """漫画的な効果背景（画面全体）。"""
    W, H = VW * K, VH * K
    if kind == "gloom":
        c.d.rectangle((0, 0, W, H), fill=(60, 80, 140, int(235 * k)))
        rng = np.random.default_rng(3)
        for i in range(40):
            x = rng.uniform(0, VW)
            ln = rng.uniform(300, 900)
            c.d.line((x * K, 0, x * K, ln * K * k), fill=(140, 160, 210, 200), width=int(rng.uniform(2, 6) * K))
    elif kind == "burst":
        cols = [(255, 214, 80), (255, 236, 150)]
        cx, cy = 360 * K, 620 * K
        n = 28
        rot = tm * 0.6
        for i in range(n):
            a0 = rot + i * 2 * math.pi / n
            a1 = a0 + math.pi / n
            R = 2500 * K
            c.d.polygon([(cx, cy), (cx + math.cos(a0) * R, cy + math.sin(a0) * R), (cx + math.cos(a1) * R, cy + math.sin(a1) * R)],
                        fill=cols[i % 2] + (int(255 * k),))
    elif kind == "impact":
        c.d.rectangle((0, 0, W, H), fill=(255, 90, 80, int(220 * k)))
        cx, cy = 360 * K, 450 * K
        rng = np.random.default_rng(5)
        for i in range(60):
            a = rng.uniform(0, 2 * math.pi)
            r0 = rng.uniform(260, 420) * K
            c.d.line((cx + math.cos(a) * r0, cy + math.sin(a) * r0, cx + math.cos(a) * 2500 * K, cy + math.sin(a) * 2500 * K),
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
    by = y + 95 + breathe
    denim, denim_dk = (80, 110, 160), (60, 85, 130)
    # ジーンズ
    c.rect(x - 58, by + 70, x + 58, by + 118, fill=denim, outline=INK, w=4, r=10)
    c.poly([(x - 56, by + 100), (x - 4, by + 100), (x - 8, 590), (x - 50, 590)], fill=denim, outline=INK, w=3)
    c.poly([(x + 4, by + 100), (x + 56, by + 100), (x + 50, 590), (x + 8, 590)], fill=denim, outline=INK, w=3)
    c.line([(x - 30, by + 120), (x - 30, 584)], denim_dk, 2)
    c.line([(x + 30, by + 120), (x + 30, 584)], denim_dk, 2)
    # スニーカー
    for sx in (-30, 30):
        c.rect(x + sx - 26, 578, x + sx + 26, 602, fill=(255, 255, 255), outline=INK, w=3, r=10)
        c.rect(x + sx - 26, 594, x + sx + 26, 602, fill=(230, 100, 90), r=3)
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
        c.line([s0, mid, h], (238, 196, 120), 19)
        c.circ(h[0], h[1], 13, fill=SKIN, outline=INK, w=3)
    # 胴体（白Tシャツ＋カーディガン）
    card, card_dk = (238, 196, 120), (210, 165, 90)
    c.rect(x - 62, by, x + 62, by + 92, fill=card, outline=INK, w=4, r=26)
    c.poly([(x - 26, by + 2), (x + 26, by + 2), (x + 16, by + 92), (x - 16, by + 92)], fill=(255, 255, 255))
    c.line([(x - 26, by + 4), (x - 16, by + 90)], card_dk, 3)
    c.line([(x + 26, by + 4), (x + 16, by + 90)], card_dk, 3)
    c.arc((x - 18, by - 6, x + 18, by + 14), 0, 180, INK, 2.5)  # Tシャツの襟
    c.line([(x - 10, by + 10), (x, by + 30), (x + 10, by + 10)], (200, 160, 60), 1.5)  # ネックレス
    coin(c, x, by + 34, 6, face=False)
    for k in range(3):
        c.circ(x - 34, by + 30 + k * 22, 3.5, fill=card_dk)
    # トートバッグ（肩掛け）
    c.line([(x + 40, by + 4), (x + 70, by + 70)], (120, 90, 70), 6)
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


CAT_X, CAT_FEET, CAT_H = 585, 1010, 530


def cat_teacher(c, tm, idx, lt):
    """ネコ先生（ユーザー提供のキャラクター画像を動かす）。"""
    t0 = ST[1] - 1.05
    k = (tm - t0) / 0.95
    if k <= 0:
        return
    walk = k < 1
    x = CAT_X + (1 - ease(k)) * 420
    bob = -abs(math.sin(tm * 11)) * 9 if walk else math.sin(tm * 1.9) * 1.5
    speaking = talking("cat", tm)
    stop = idx == 5 and lt < 1.25
    explaining = idx in (1, 3, 5) and not stop
    nod = math.sin(tm * 6.5) * 1.6 if speaking else math.sin(tm * 0.9) * 0.6
    lean = (1.4 if explaining else 0) + (math.sin(tm * 11) * 1.5 if walk else 0)
    glint = max(0.0, 1 - abs(lt - 0.25) / 0.25) if stop else 0
    blink = ((tm % 3.9) < 0.12 or (tm % 9.1) < 0.12) and not stop
    cat.draw(c, c.z * K, x, CAT_FEET, CAT_H, tm, bob=bob, mouth=mouth_level("cat", tm), blink=blink,
             glint=glint, stern=stop, nod=nod, lean=lean)
    if stop and lt < 0.6:  # メガネのキラーン
        for i, (dx, dy) in enumerate(((-30, -400), (22, -404))):
            sparkle(c, x + dx * CAT_H / 470 + 18, CAT_FEET + dy * CAT_H / 470 - 6, 16 * (1 - lt / 0.6) + 2, (255, 255, 255))


# ---------- ホワイトボード ----------
# パネルは横長版の座標 (360..960, 40..410) で描き、縦画面ではこのぶんずらして置く
BOARD_AT = (-300, 95)
YUI_SC = 1.12
YUI_AT = (185 - 235 * YUI_SC, 1010 - 600 * YUI_SC, YUI_SC)   # 足元が (185, 1010) に来るように
YUI_X = 185
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


def bank(c, x, y, s=1.0):
    c.ell(x - 120 * s, y + 92 * s, x + 120 * s, y + 108 * s, fill=(0, 0, 0, 35))
    c.poly([(x - 120 * s, y - 40 * s), (x, y - 100 * s), (x + 120 * s, y - 40 * s)], fill=(120, 150, 200), outline=INK, w=4)
    c.text(x, y - 58 * s, "BANK", int(24 * s), fill=(255, 255, 255))
    c.rect(x - 110 * s, y - 40 * s, x + 110 * s, y - 24 * s, fill=(225, 230, 240), outline=INK, w=3)
    for i in range(4):
        px = x - 80 * s + i * 53 * s
        c.rect(px - 10 * s, y - 24 * s, px + 10 * s, y + 80 * s, fill=(245, 245, 250), outline=INK, w=3)
    c.rect(x - 22 * s, y + 20 * s, x + 22 * s, y + 80 * s, fill=(90, 110, 150), outline=INK, w=3, r=6 * s)
    c.rect(x - 125 * s, y + 80 * s, x + 125 * s, y + 98 * s, fill=(210, 215, 228), outline=INK, w=3)


def panel_bank(c, lt):
    board(c, "バイト代 10万円 → 銀行へ", (240, 120, 150))
    bank(c, BCX + 120, 280, 1.0)
    drop = ease((lt - 0.3) / 1.0)
    landed = lt > 1.3
    if not landed:
        for j in range(3):
            bill(c, lerp(BCX - 150, BCX + 120, drop) - j * 8, lerp(220, 300, drop) - j * 8, 0.5 * (1 - drop * 0.7))
    else:
        for i in range(3):
            a = (lt - 1.3) * 2
            if a < 1:
                sparkle(c, BCX + 60 + i * 60, 190 - a * 40 - i * 8, 10 * (1 - a) + 3)
        c.text(BCX - 150, 230, "預金", 34, fill=(230, 90, 130), stroke=3)
        c.text(BCX - 150, 280, "100,000円", 26, fill=INK)
    if lt > 3.0:
        c.text(BCX - 150, 335, "金利は とても低い…", 20, fill=(150, 150, 150))


def panel_inflation(c, lt, dur):
    board(c, "物価が上がると…（インフレ）", (240, 140, 60))
    k = ease((lt - 1.2) / (dur - 3.0))
    years = 36 * k
    c.text(BCX, 135, f"{int(years)}年後", 44, fill=(220, 80, 60))
    # 左：お札の価値
    val = 1 / 1.02 ** years
    s = 0.62 * math.sqrt(val) + 0.12
    for j in (2, 1, 0):
        bill(c, 510 - j * 6 * s, 230 - j * 6 * s, s, fade=1 - val)
    c.rect(430, 290, 590, 306, fill=(230, 230, 230), r=8)
    c.rect(430, 290, 430 + 160 * val, 306, fill=(90, 170, 110), r=8)
    c.text(510, 330, f"10万円の価値 {int(100000 * val):,}円分", 19, fill=(70, 120, 80))
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
    val = 100000 * 1.05 ** years
    c.text(BCX, 132, f"年利5% … {int(years)}年後  {int(val):,}円", 28, fill=(40, 120, 70))
    ox, oy, gw, gh = 430, 380, 480, 200
    c.line([(ox, oy), (ox + gw, oy)], INK, 3)
    c.line([(ox, oy), (ox, oy - gh - 10)], INK, 3)
    for v, lab in ((1, "10万"), (2, "20万")):
        yy = oy - gh * (v / 2)
        for xx in range(ox, ox + gw, 18):
            c.line([(xx, yy), (xx + 8, yy)], (200, 200, 200), 2)
        c.text(ox - 34, yy, lab, 17, fill=(130, 130, 130))
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
    pill(c, 575, 198, "72 ÷ 5 ＝ 約14年で 2倍！", 24, fill=(200, 235, 255), k=ease((lt - 3.0) / 0.4))
    pill(c, 575, 246, "利息にも 利息がつく！", 20, fill=(255, 236, 140), k=ease((lt - 5.6) / 0.4))


def panel_rules(c, lt):
    board(c, "投資のコツ", (90, 130, 220))
    k0 = ease((lt - 2.3) / 0.3)
    if k0 > 0:
        c.rect(BCX - 150, 112, BCX + 150, 142, fill=(255, 240, 240), outline=(220, 90, 90), w=2.5, r=15)
        c.text(BCX, 127, "まずは 生活費を残す", 18, fill=(200, 60, 60))
    items = [("少額から", (90, 160, 230)), ("長く", (90, 185, 120)), ("分散", (240, 150, 60))]
    for i, (s, col) in enumerate(items):
        k = back((lt - 3.3 - i * 0.6) / 0.35) if lt > 3.3 + i * 0.6 else 0
        if k <= 0:
            continue
        cx, cy = 500 + i * 160, 215
        w, h = 66 * k, 72 * k
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
            c.text(cx, cy + 50, s, 24, fill=col)
    k = (lt - 5.9) / 0.45
    if k > 0:
        sc = back(k)
        r = 8 * math.sin(min(1, k) * math.pi) * (1 - min(1, k))
        c.rect(BCX - 200 * sc, 340 - 32 * sc + r, BCX + 200 * sc, 340 + 32 * sc + r, fill=(255, 225, 90), outline=(200, 60, 60), w=4, r=12)
        if sc > 0.6:
            c.text(BCX, 340 + r, "新NISA ＝ 利益が非課税！", 28, fill=(200, 50, 50))


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
def wrap(txt, n):
    """句読点で区切りながら、1行 n 文字以内に折り返す。"""
    parts, cur = [], ""
    for ch in txt:
        cur += ch
        if ch in "、。！？":
            parts.append(cur); cur = ""
    if cur:
        parts.append(cur)
    lines, line = [], ""
    for p in parts:
        while len(p) > n:
            if line:
                lines.append(line); line = ""
            lines.append(p[:n]); p = p[n:]
        if len(line) + len(p) > n:
            lines.append(line); line = p
        else:
            line += p
    if line:
        lines.append(line)
    return lines


def subtitle(c, idx, tm):
    if not (0 <= idx < len(LINES)):
        return
    ln = LINES[idx]
    if tm < ln["start"] - 0.1 or tm > ln["start"] + ln["dur"] + 0.25:
        return
    name, col = ("ユイ", (240, 100, 110)) if ln["who"] == "yui" else ("ネコ先生", (90, 110, 160))
    lines = wrap(ln["text"], 18)
    size, lh = 32, 46
    h = len(lines) * lh + 34
    cy = 1050
    y0, y1 = cy - h / 2, cy + h / 2
    d = c.d
    d.rounded_rectangle((22 * K, y0 * K, 698 * K, y1 * K), radius=int(24 * K), fill=(255, 255, 255, 240), outline=INK, width=int(4 * K))
    nw = 34 + 26 * len(name)
    d.rounded_rectangle((44 * K, (y0 - 22) * K, (44 + nw) * K, (y0 + 18) * K), radius=int(14 * K), fill=col, outline=INK, width=int(3 * K))
    c.stext(44 + nw / 2, y0 - 2, name, 23, (255, 255, 255))
    c.stext(360, cy + 4, "\n".join(lines), size, INK, spacing=lh - size)


def header(c, tm):
    """上部の見出し（ショート動画で何の話か分かるように）。"""
    if tm < INTRO or tm > END + 0.3:
        return
    d = c.d
    d.rounded_rectangle((60 * K, 44 * K, 660 * K, 108 * K), radius=int(32 * K), fill=(58, 42, 40, 230))
    c.stext(360, 76, "大学生のお金入門｜72の法則", 30, (255, 214, 90))


def title_card(c, tm):
    if tm > INTRO + 0.5:
        return
    rng = np.random.default_rng(2)
    for i in range(34):  # コインの雨
        x = rng.uniform(30, 690)
        sp = rng.uniform(700, 1100)
        y = -60 + (tm - rng.uniform(0, 0.8)) * sp
        if -60 < y < 1350:
            c.d.ellipse(((x - 22) * K, (y - 22) * K, (x + 22) * K, (y + 22) * K), fill=(255, 205, 60), outline=(175, 120, 20), width=int(3 * K))
            c.stext(x, y, "¥", 24, (185, 120, 15))
    a = ease(tm / 0.45) * (1 - ease((tm - INTRO) / 0.5))
    y = 560 + (1 - a) * -700 if tm < 1 else 560 + (1 - a) * 800
    if a <= 0.01:
        return
    d = c.d
    d.rounded_rectangle((40 * K, (y - 190) * K, 680 * K, (y + 190) * K), radius=int(40 * K), fill=(255, 214, 90), outline=INK, width=int(6 * K))
    d.rounded_rectangle((56 * K, (y - 174) * K, 664 * K, (y + 174) * K), radius=int(32 * K), outline=(255, 255, 255), width=int(3 * K))
    c.stext(360, y - 70, "ユイと\nネコ先生", 84, INK, stroke=6, sfill=(255, 255, 255), spacing=4)
    c.stext(360, y + 120, "大学生のための\nお金と72の法則", 40, (200, 70, 50), spacing=8)


def ending(c, lt):
    """円形ワイプでまとめ画面へ。"""
    k = ease(lt / 0.6)
    W, H = int(VW * K), int(VH * K)
    mask = Image.new("L", (W, H), 255)
    md = ImageDraw.Draw(mask)
    r = (1 - k) * 1400 * K
    cx, cy = c.P(YUI_X, 710)
    md.ellipse((cx - r, cy - r, cx + r, cy + r), fill=0)
    card = Image.new("RGB", (W, H))
    cd = ImageDraw.Draw(card, "RGBA")
    for i in range(40):
        y0 = H * i / 40
        cd.rectangle((0, y0, W, y0 + H / 40 + 1), fill=mix((35, 55, 95), (60, 40, 90), i / 39))
    cc = Canvas((VW / 2, VH / 2, 1.0))
    cc.img, cc.d = card, cd
    rng = np.random.default_rng(4)
    for i in range(60):
        x, y = rng.uniform(0, VW), rng.uniform(0, VH)
        tw = 0.5 + 0.5 * math.sin(lt * 3 + i)
        cd.ellipse(((x - 2) * K, (y - 2) * K, (x + 2) * K, (y + 2) * K), fill=(255, 255, 255, int(160 * tw)))
    cc.stext(360, 200, "今日のまとめ", 50, (255, 214, 90))
    cd.rounded_rectangle((40 * K, 270 * K, 680 * K, 450 * K), radius=int(28 * K), fill=(255, 255, 255, 30), outline=(255, 214, 90), width=int(3 * K))
    cc.stext(360, 360, "72 ÷ 年利(%)\n＝ お金が2倍になる年数", 42, (255, 255, 255), spacing=14)
    cc.stext(360, 545, "72 ÷ インフレ率(%)\n＝ お金の価値が半分になる年数", 30, (200, 220, 255), spacing=10)
    cc.stext(360, 690, "生活費は残して\n少額から・長く・分散", 32, (200, 255, 210), spacing=10)
    cc.stext(360, 810, "新NISAなら 利益が非課税", 32, (255, 236, 140))
    cc.stext(360, 910, "※投資には元本割れのリスクがあります。\n数値は概算です。", 22, (255, 180, 180), spacing=8)
    for i in range(5):
        x, y = 120 + i * 120, 1010 + math.sin(lt * 4 + i) * 8
        cd.ellipse(((x - 26) * K, (y - 26) * K, (x + 26) * K, (y + 26) * K), fill=(255, 205, 60), outline=(175, 120, 20), width=int(3 * K))
        cc.stext(x, y, "¥", 28, (185, 120, 15))
    cc.stext(360, 1090, "VOICEVOX:春日部つむぎ / VOICEVOX:青山龍星", 18, (200, 200, 220))
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
    with c.at(*BOARD_AT):
        if idx <= 0:
            panel_bank(c, max(0, tm - ST[0]))
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
    cat_teacher(c, tm, idx, lt)
    with c.at(*YUI_AT):
        yui(c, tm, mood, idx)
    # 画面上の文字エフェクト
    if idx == 2 and lt > -0.07:
        k = back((lt + 0.1) / 0.3)
        c.stext(360 + math.sin(tm * 30) * 3, 250, "ガーン！", int(110 * k) + 1, (255, 255, 255), stroke=8, sfill=(40, 50, 100))
    if idx == 4 and lt > -0.07:
        k = back((lt + 0.1) / 0.3)
        c.stext(360, 250, "ぜんぶ投資！？", int(80 * k) + 1, (230, 80, 40), stroke=8, sfill=(255, 255, 255))
        for i in range(6):
            a = tm * 2 + i * 1.05
            x, y = 360 + math.cos(a) * 300, 300 + math.sin(a) * 110
            c.d.ellipse(((x - 26) * K, (y - 26) * K, (x + 26) * K, (y + 26) * K), fill=(255, 205, 60), outline=(175, 120, 20), width=int(3 * K))
            c.stext(x, y, "¥", 28, (185, 120, 15))
    if idx == 5 and 0.03 <= lt < 1.25:
        k = back(lt / 0.25)
        c.stext(360, 220, "待ちたまえ！", int(104 * k) + 1, (255, 255, 255), stroke=10, sfill=(180, 30, 40))
    header(c, tm)
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
