"""お金の2Dアニメ「ユイとフクロウ先生 〜72の法則〜」のレンダラー。

Open JTalk で作った line*.wav を読み込み、セリフの長さに合わせて
タイムラインを組み、Pillow でフレームを描いて ffmpeg で mp4 にする。
"""
import math
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "money-72.mp4")
W, H = 1280, 720
S = 2  # 2倍で描いて縮小（アンチエイリアス）
FPS = 24
SR = 44100

FONT_DIR = "/usr/share/fonts/opentype/noto/"
def font(size, bold=True):
    name = "NotoSansCJK-Bold.ttc" if bold and os.path.exists(FONT_DIR + "NotoSansCJK-Bold.ttc") else "NotoSansCJK-Regular.ttc"
    return ImageFont.truetype(FONT_DIR + name, size * S, index=0)

F_SUB = font(34)
F_NAME = font(24)
F_BIG = font(64)
F_MID = font(40)
F_SMALL = font(26)

# ---------- 台本と音声 ----------
LINES = []
with open(os.path.join(HERE, "lines.tsv"), encoding="utf-8") as f:
    for i, row in enumerate(f):
        who, text = row.rstrip("\n").split("\t")
        with wave.open(os.path.join(HERE, f"line{i}.wav")) as w:
            pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        LINES.append({"who": who, "text": text, "pcm": pcm})

INTRO, GAP, OUTRO = 0.8, 0.2, 2.4
t = INTRO
for ln in LINES:
    ln["start"] = t
    ln["dur"] = len(ln["pcm"]) / SR
    t += ln["dur"] + GAP
TOTAL = t - GAP + OUTRO
NFRAMES = int(TOTAL * FPS)

# 音声トラック
track = np.zeros(int(TOTAL * SR) + SR, dtype=np.float32)
for ln in LINES:
    s = int(ln["start"] * SR)
    track[s:s + len(ln["pcm"])] += ln["pcm"]
track = np.clip(track[:int(TOTAL * SR)] * 0.95, -1, 1)
with wave.open(os.path.join(HERE, "voice.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((track * 32767).astype(np.int16).tobytes())


def current(tm):
    for i, ln in enumerate(LINES):
        if ln["start"] <= tm < ln["start"] + ln["dur"] + GAP:
            return i, tm - ln["start"]
    return (len(LINES), tm - LINES[-1]["start"] - LINES[-1]["dur"]) if tm > INTRO else (-1, tm)


def loudness(who, tm):
    """その話者がいま声を出している大きさ (0..1)。口パク用。"""
    for ln in LINES:
        if ln["who"] == who and ln["start"] <= tm < ln["start"] + ln["dur"]:
            a = int((tm - ln["start"]) * SR)
            seg = ln["pcm"][a:a + SR // FPS]
            return min(1.0, float(np.sqrt(np.mean(seg ** 2))) * 9) if len(seg) else 0
    return 0


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def P(*v):  # 座標をスケール
    return [int(round(a * S)) for a in v]


# ---------- 描画パーツ ----------
SKY = (255, 244, 225)
INK = (60, 45, 40)

def background(d, tm, scene):
    d.rectangle(P(0, 0, W, H), fill=SKY)
    # 壁紙のドット
    for y in range(30, 560, 60):
        for x in range(30 + (y // 60 % 2) * 30, W, 60):
            d.ellipse(P(x - 3, y - 3, x + 3, y + 3), fill=(250, 228, 200))
    # 窓（最後のシーンで朝日）
    sunrise = ease((tm - LINES[6]["start"]) / 2.0) if scene >= 6 else 0
    sky = tuple(int(a + (b - a) * sunrise) for a, b in zip((170, 210, 240), (255, 200, 140)))
    d.rounded_rectangle(P(70, 60, 300, 260), radius=12 * S, fill=sky, outline=INK, width=5 * S)
    if sunrise > 0:
        sy = 250 - 110 * sunrise
        d.ellipse(P(185 - 40, sy - 40, 185 + 40, sy + 40), fill=(255, 150, 70))
    d.line(P(185, 60, 185, 260), fill=INK, width=4 * S)
    d.line(P(70, 160, 300, 160), fill=INK, width=4 * S)
    # 床
    d.rectangle(P(0, 560, W, H), fill=(214, 168, 120))
    for x in range(0, W, 120):
        d.line(P(x, 560, x + 40, H), fill=(196, 150, 104), width=3 * S)
    # 本棚＋止まり木
    d.rectangle(P(1040, 330, 1240, 560), fill=(160, 105, 70), outline=INK, width=4 * S)
    for i, c in enumerate([(230, 90, 90), (90, 150, 220), (240, 200, 80), (110, 190, 120), (200, 120, 200)]):
        d.rectangle(P(1055 + i * 34, 350, 1082 + i * 34, 430), fill=c, outline=INK, width=2 * S)
    d.line(P(1040, 440, 1240, 440), fill=INK, width=4 * S)


def board(d):
    d.rounded_rectangle(P(350, 40, 960, 400), radius=18 * S, fill=(255, 255, 255), outline=INK, width=5 * S)


def text_c(d, xy, s, f, fill=INK, stroke=0, sfill=(255, 255, 255)):
    d.text(P(*xy), s, font=f, fill=fill, anchor="mm", stroke_width=stroke * S, stroke_fill=sfill)


def coin(d, x, y, r, label="¥"):
    d.ellipse(P(x - r, y - r, x + r, y + r), fill=(250, 200, 60), outline=(170, 120, 20), width=max(2, int(r / 8)) * S)
    d.ellipse(P(x - r * .7, y - r * .7, x + r * .7, y + r * .7), outline=(220, 160, 30), width=2 * S)
    text_c(d, (x, y + 1), label, font(max(10, int(r))), fill=(170, 110, 10))


def bill(d, cx, cy, scale, alpha_col=None):
    w, h = 220 * scale, 110 * scale
    col = alpha_col or (200, 230, 200)
    d.rounded_rectangle(P(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), radius=int(8 * scale * S) + 1,
                        fill=col, outline=(70, 120, 80), width=max(1, int(4 * scale)) * S)
    d.ellipse(P(cx + w * .15, cy - h * .3, cx + w * .4, cy + h * .3), outline=(70, 120, 80), width=max(1, int(3 * scale)) * S)
    text_c(d, (cx - w * .12, cy), "10000", font(max(8, int(34 * scale))), fill=(50, 100, 60))


def piggy(d, x, y, sc=1.0, shake=0):
    x += shake
    pink, dk = (250, 170, 190), (200, 110, 140)
    d.ellipse(P(x - 70 * sc, y - 50 * sc, x + 70 * sc, y + 50 * sc), fill=pink, outline=dk, width=4 * S)
    d.ellipse(P(x + 55 * sc, y - 15 * sc, x + 90 * sc, y + 20 * sc), fill=pink, outline=dk, width=4 * S)
    for nx in (68, 78):
        d.ellipse(P(x + nx * sc - 3, y - 2, x + nx * sc + 3, y + 6), fill=dk)
    d.polygon(P(x + 20 * sc, y - 45 * sc, x + 40 * sc, y - 75 * sc, x + 50 * sc, y - 38 * sc), fill=pink, outline=dk)
    d.ellipse(P(x + 25 * sc, y - 18 * sc, x + 35 * sc, y - 8 * sc), fill=INK)
    d.rounded_rectangle(P(x - 25 * sc, y - 52 * sc, x + 15 * sc, y - 44 * sc), radius=3 * S, fill=dk)
    for lx in (-40, 30):
        d.rectangle(P(x + lx * sc, y + 40 * sc, x + (lx + 18) * sc, y + 62 * sc), fill=pink, outline=dk, width=3 * S)


def yui(d, tm, mood):
    """主人公ユイ。mood: normal / shock / excited / happy"""
    x0, y0 = 205, 330
    bob = math.sin(tm * 2.4) * 4
    jump = 0
    if mood == "excited":
        jump = -abs(math.sin(tm * 9)) * 26
    if mood == "shock":
        jump = -10 * math.exp(-max(0, tm - LINES[2]["start"]) * 3) * math.sin(tm * 40)
    y = y0 + bob + jump
    x = x0
    # 体
    d.rounded_rectangle(P(x - 70, y + 90, x + 70, y + 240), radius=40 * S, fill=(255, 120, 110), outline=INK, width=5 * S)
    d.rectangle(P(x - 45, y + 230, x - 15, y + 270 - jump), fill=(80, 80, 120))
    d.rectangle(P(x + 15, y + 230, x + 45, y + 270 - jump), fill=(80, 80, 120))
    # 腕
    if mood == "excited":
        d.line(P(x - 60, y + 120, x - 120, y + 20), fill=INK, width=14 * S)
        d.line(P(x + 60, y + 120, x + 120, y + 20), fill=INK, width=14 * S)
        d.ellipse(P(x - 135, y + 5, x - 105, y + 35), fill=(255, 220, 190), outline=INK, width=3 * S)
        d.ellipse(P(x + 105, y + 5, x + 135, y + 35), fill=(255, 220, 190), outline=INK, width=3 * S)
    elif mood == "shock":
        d.line(P(x - 60, y + 120, x - 75, y + 40), fill=INK, width=14 * S)
        d.line(P(x + 60, y + 120, x + 75, y + 40), fill=INK, width=14 * S)
    else:
        d.line(P(x - 60, y + 120, x - 85, y + 200), fill=INK, width=14 * S)
        d.line(P(x + 60, y + 120, x + 85, y + 200), fill=INK, width=14 * S)
    # 頭
    d.ellipse(P(x - 95, y - 120, x + 95, y + 100), fill=(70, 50, 45))  # 後ろ髪
    d.ellipse(P(x - 80, y - 90, x + 80, y + 80), fill=(255, 225, 200), outline=INK, width=5 * S)
    d.chord(P(x - 85, y - 110, x + 85, y + 30), 180, 360, fill=(70, 50, 45))  # 前髪
    d.ellipse(P(x + 60, y - 110, x + 105, y - 65), fill=(255, 120, 110), outline=INK, width=3 * S)  # 髪飾り
    # 目
    blink = (tm % 3.7) < 0.12
    for ex in (-32, 32):
        cx, cy = x + ex, y + 5
        if mood == "shock":
            d.ellipse(P(cx - 16, cy - 20, cx + 16, cy + 20), fill="white", outline=INK, width=4 * S)
            d.ellipse(P(cx - 5, cy - 5, cx + 5, cy + 5), fill=INK)
        elif mood in ("excited", "happy") and not blink:
            d.arc(P(cx - 16, cy - 10, cx + 16, cy + 18), 200, 340, fill=INK, width=5 * S)
        elif blink:
            d.line(P(cx - 14, cy, cx + 14, cy), fill=INK, width=4 * S)
        else:
            d.ellipse(P(cx - 11, cy - 16, cx + 11, cy + 16), fill=INK)
            d.ellipse(P(cx - 5, cy - 11, cx + 2, cy - 4), fill="white")
    # ほっぺ
    for ex in (-52, 52):
        d.ellipse(P(x + ex - 14, y + 28, x + ex + 14, y + 42), fill=(255, 170, 160))
    # 口（音声の大きさで開く）
    op = loudness("yui", tm)
    if op > 0.08:
        h = 6 + 22 * op
        d.ellipse(P(x - 13, y + 40, x + 13, y + 40 + h), fill=(170, 60, 70), outline=INK, width=3 * S)
    elif mood == "shock":
        d.ellipse(P(x - 9, y + 42, x + 9, y + 60), fill=(170, 60, 70), outline=INK, width=3 * S)
    else:
        d.arc(P(x - 16, y + 30, x + 16, y + 54), 20, 160, fill=INK, width=4 * S)
    if mood == "shock":  # 汗
        d.polygon(P(x + 90, y - 50, x + 80, y - 20, x + 100, y - 20), fill=(120, 190, 255))
        d.ellipse(P(x + 79, y - 32, x + 101, y - 10), fill=(120, 190, 255))
    if mood == "excited":  # きらきら
        for k, (sx, sy) in enumerate([(-130, -90), (130, -110), (150, 60)]):
            r = 12 + 6 * math.sin(tm * 8 + k * 2)
            d.polygon(P(x + sx, y + sy - r, x + sx + r / 3, y + sy, x + sx, y + sy + r, x + sx - r / 3, y + sy), fill=(255, 200, 40))
            d.polygon(P(x + sx - r, y + sy, x + sx, y + sy - r / 3, x + sx + r, y + sy, x + sx, y + sy + r / 3), fill=(255, 200, 40))


def owl(d, tm, pose):
    """フクロウ先生。最初のセリフで飛んできて本棚にとまる。"""
    arrive = LINES[1]["start"] - 0.9
    k = ease((tm - arrive) / 1.0)
    if k <= 0:
        return
    x = 1140 + (1 - k) * 300
    y = 290 - (1 - k) * 260 + math.sin(tm * 2) * 3
    flap = math.sin(tm * 25) * 30 * (1 - k)
    br, lt = (150, 105, 70), (230, 200, 160)
    # 翼
    lw = -40 if pose == "stop" else 0
    d.polygon(P(x - 70, y - 10, x - 100 - flap / 2, y + 50 + lw - flap, x - 60, y + 90), fill=(120, 80, 50), outline=INK)
    if pose == "stop":  # 右翼を前に突き出す「待った！」
        d.polygon(P(x + 60, y + 10, x - 10, y - 50, x - 30, y - 20, x + 40, y + 60), fill=(120, 80, 50), outline=INK)
    else:
        d.polygon(P(x + 70, y - 10, x + 100 + flap / 2, y + 50 - flap, x + 60, y + 90), fill=(120, 80, 50), outline=INK)
    d.ellipse(P(x - 75, y - 80, x + 75, y + 110), fill=br, outline=INK, width=5 * S)
    d.ellipse(P(x - 45, y + 10, x + 45, y + 100), fill=lt)
    # 耳
    d.polygon(P(x - 60, y - 55, x - 70, y - 110, x - 25, y - 70), fill=br, outline=INK)
    d.polygon(P(x + 60, y - 55, x + 70, y - 110, x + 25, y - 70), fill=br, outline=INK)
    # 目とメガネ
    blink = (tm % 4.3) < 0.13
    for ex in (-30, 30):
        d.ellipse(P(x + ex - 26, y - 50, x + ex + 26, y + 2), fill="white", outline=INK, width=4 * S)
        if blink:
            d.line(P(x + ex - 14, y - 24, x + ex + 14, y - 24), fill=INK, width=4 * S)
        else:
            d.ellipse(P(x + ex - 11, y - 35, x + ex + 11, y - 13), fill=INK)
            d.ellipse(P(x + ex - 5, y - 31, x + ex, y - 26), fill="white")
    d.line(P(x - 4, y - 24, x + 4, y - 24), fill=INK, width=4 * S)
    # くちばし（音声で開閉）
    op = loudness("owl", tm)
    d.polygon(P(x - 12, y + 2, x + 12, y + 2, x, y + 18), fill=(250, 180, 50), outline=INK)
    if op > 0.08:
        d.polygon(P(x - 10, y + 20 + 2, x + 10, y + 20 + 2, x, y + 22 + 18 * op), fill=(230, 150, 30), outline=INK)
    # 博士帽
    d.polygon(P(x - 55, y - 90, x, y - 115, x + 55, y - 90, x, y - 70), fill=(50, 50, 70))
    d.rectangle(P(x - 25, y - 95, x + 25, y - 78), fill=(50, 50, 70))
    d.line(P(x + 40, y - 92, x + 50, y - 55), fill=(240, 200, 60), width=3 * S)
    # 足
    for fx in (-20, 20):
        d.line(P(x + fx - 10, y + 108, x + fx + 10, y + 108), fill=(250, 180, 50), width=6 * S)


# ---------- ホワイトボードの中身（シーン別） ----------
def panel_piggy(d, lt):
    board(d)
    text_c(d, (655, 85), "お年玉 1万円", F_MID)
    drop = ease(lt / 1.4)
    piggy(d, 655, 280, 1.4, shake=math.sin(lt * 30) * 4 if 1.4 < lt < 1.8 else 0)
    if drop < 1:
        bill(d, 640, 140 + drop * 90, 0.6 * (1 - drop * 0.6))
    else:
        text_c(d, (655, 175), "ちょきん！", F_SMALL, fill=(220, 90, 120))


def panel_inflation(d, lt, dur):
    board(d)
    k = ease((lt - 0.5) / (dur - 1.5))
    years = int(36 * k)
    text_c(d, (655, 80), f"物価 年2% UP … {years}年後", F_MID)
    # お札の価値が縮む
    sc = 1.0 - 0.5 * k
    bill(d, 520, 225, 0.9 * math.sqrt(sc), alpha_col=(int(200 + 50 * k), int(230 - 10 * k), int(200 + 20 * k)))
    text_c(d, (520, 315), f"価値 {int(10000 * sc):,}円分", F_SMALL, fill=(200, 60, 60))
    # アイスの値段が上がる
    ix, iy = 810, 230
    d.polygon(P(ix - 30, iy, ix + 30, iy, ix, iy + 80), fill=(230, 180, 110), outline=INK)
    d.ellipse(P(ix - 38, iy - 55, ix + 38, iy + 15), fill=(255, 190, 210), outline=INK, width=3 * S)
    price = int(round(100 * (1.02 ** (36 * k))))
    text_c(d, (ix, 315), f"アイス {price}円", F_SMALL, fill=(200, 60, 60))
    if lt > 3.0:
        text_c(d, (655, 365), "72 ÷ 2 ＝ 36年で 価値が半分", F_SMALL, fill=(40, 90, 200))


def panel_shock(d, lt):
    board(d)
    text_c(d, (655, 220), "お金が へる！？", F_BIG, fill=(220, 60, 60))
    for i in range(4):  # コインが飛んでいく
        a = lt * 1.5 + i * 1.6
        coin(d, 655 + math.cos(a) * (120 + lt * 60), 220 + math.sin(a) * 90 - lt * 40, 18)


def panel_compound(d, lt, dur):
    board(d)
    k = ease((lt - 0.3) / (dur - 1.2))
    years = 14.4 * k
    val = 10000 * 1.05 ** years
    text_c(d, (655, 75), f"年5%で運用 … {int(years)}年後 {int(val):,}円", F_SMALL)
    # 軸
    ox, oy, gw, gh = 420, 350, 470, 220
    d.line(P(ox, oy, ox + gw, oy), fill=INK, width=3 * S)
    d.line(P(ox, oy, ox, oy - gh - 10), fill=INK, width=3 * S)
    d.line(P(ox, oy - gh / 2, ox + gw, oy - gh / 2), fill=(200, 200, 200), width=2 * S)
    d.text(P(ox - 52, oy - gh / 2 - 14), "1万", font=F_SMALL, fill=(150, 150, 150))
    d.text(P(ox - 52, oy - gh - 14), "2万", font=F_SMALL, fill=(150, 150, 150))
    pts = []
    n = max(2, int(60 * k))
    for i in range(n + 1):
        yr = years * i / n
        pts += P(ox + gw * yr / 14.4, oy - gh / 2 * 1.05 ** yr)
    if len(pts) >= 4:
        d.line(pts, fill=(60, 170, 90), width=6 * S, joint="curve")
    # 先端で雪だるま式に大きくなるコイン
    coin(d, pts[-2] / S, pts[-1] / S, 14 + 14 * k)
    if lt > 3.2:
        text_c(d, (700, 310), "72 ÷ 5 ＝ 約14年で 2倍！", F_MID, fill=(40, 90, 200), stroke=4)


def panel_allin(d, lt):
    board(d)
    text_c(d, (655, 170), "ぜんぶ投資！", F_BIG, fill=(230, 120, 30))
    for i in range(6):
        coin(d, 470 + i * 75, 290 + math.sin(lt * 10 + i) * 14, 24)


def panel_rules(d, lt):
    board(d)
    text_c(d, (655, 80), "投資のコツ", F_MID)
    items = [("少しずつ", (90, 160, 230)), ("長く", (90, 190, 120)), ("分散", (240, 150, 60))]
    for i, (s, c) in enumerate(items):
        k = ease((lt - 1.6 - i * 0.9) / 0.4)
        if k <= 0:
            continue
        cx = 470 + i * 185
        r = 70 * k
        d.ellipse(P(cx - r, 200 - r, cx + r, 200 + r), fill=c, outline=INK, width=4 * S)
        if k > 0.6:
            text_c(d, (cx, 200), s, F_SMALL, fill="white")
    if lt > 6.0:
        k = ease((lt - 6.0) / 0.4)
        d.rounded_rectangle(P(470, 300, 840, 370), radius=14 * S, fill=(255, 235, 120), outline=INK, width=4 * S)
        text_c(d, (655, 335), "NISA = 利益が非課税", F_SMALL)
    if lt < 1.6:  # 「待った！」の吹き出し
        d.rounded_rectangle(P(480, 150, 830, 270), radius=30 * S, fill=(255, 90, 90), outline=INK, width=5 * S)
        text_c(d, (655, 210), "待った！", F_BIG, fill="white")


def panel_tree(d, lt):
    board(d)
    g = ease(lt / 2.2)
    # コインの木がのびる
    d.rectangle(P(640, 370 - 150 * g, 670, 370), fill=(140, 95, 60))
    d.ellipse(P(655 - 140 * g, 230 - 120 * g, 655 + 140 * g, 230 + 80 * g), fill=(110, 190, 110))
    for i in range(7):
        if g > 0.5 + i * 0.06:
            a = i * 0.9
            coin(d, 655 + math.cos(a) * 85, 210 + math.sin(a) * 55, 18)
    text_c(d, (655, 75), "時間を 味方に！", F_MID, fill=(40, 140, 70))


def subtitle(d, idx):
    if not (0 <= idx < len(LINES)):
        return
    ln = LINES[idx]
    name, col = ("ユイ", (255, 120, 110)) if ln["who"] == "yui" else ("フクロウ先生", (150, 105, 70))
    d.rounded_rectangle(P(60, 600, 1220, 705), radius=18 * S, fill=(255, 255, 255), outline=INK, width=4 * S)
    d.rounded_rectangle(P(80, 580, 80 + 30 + 26 * len(name), 620), radius=12 * S, fill=col, outline=INK, width=3 * S)
    d.text(P(95, 584), name, font=F_NAME, fill="white")
    txt = ln["text"]
    # 長いセリフは句読点で2行に
    if len(txt) > 30:
        cut = max(txt.rfind("、", 0, len(txt) // 2 + 6), txt.rfind("。", 0, len(txt) // 2 + 6))
        txt = txt[:cut + 1] + "\n" + txt[cut + 1:] if cut > 0 else txt
    d.multiline_text(P(640, 657), txt, font=F_SUB if "\n" not in txt else font(28), fill=INK, anchor="mm", align="center", spacing=4 * S)


def title_card(d, tm):
    if tm < INTRO + 0.6:
        a = 1 - ease((tm - INTRO) / 0.6)
        if a <= 0:
            return
        y = 360 - (1 - a) * 400
        d.rounded_rectangle(P(240, y - 110, 1040, y + 110), radius=30 * S, fill=(255, 210, 90), outline=INK, width=6 * S)
        text_c(d, (640, y - 30), "ユイと フクロウ先生", F_BIG, stroke=5)
        text_c(d, (640, y + 55), "〜 お金と 72の法則 〜", F_MID)


def ending(d, lt):
    a = ease(lt / 0.5)
    d.rectangle(P(0, 0, W, H * a), fill=(40, 60, 90))
    if a < 1:
        return
    text_c(d, (640, 170), "今日のまとめ", F_MID, fill=(255, 210, 90))
    text_c(d, (640, 300), "72 ÷ 年利(%) ＝ お金が2倍になる約年数", F_MID, fill="white")
    text_c(d, (640, 380), "インフレ率で割れば、お金の価値が半分になる年数", F_SMALL, fill=(200, 220, 255))
    text_c(d, (640, 500), "※投資には元本割れのリスクがあります。数値は概算です。", F_SMALL, fill=(255, 180, 180))
    for i in range(5):
        coin(d, 340 + i * 150, 620 + math.sin(lt * 4 + i) * 10, 26)


def frame(n):
    tm = n / FPS
    idx, lt = current(tm)
    img = Image.new("RGB", (W * S, H * S))
    d = ImageDraw.Draw(img)
    background(d, tm, idx)
    mood = {2: "shock", 4: "excited", 6: "happy"}.get(idx, "normal")
    owl(d, tm, "stop" if idx == 5 and lt < 1.8 else "normal")
    yui(d, tm, mood)
    dur = LINES[idx]["dur"] if 0 <= idx < len(LINES) else 1
    if idx <= 0:
        panel_piggy(d, max(0, tm - INTRO + 0.3))
    elif idx == 1:
        panel_inflation(d, lt, dur)
    elif idx == 2:
        panel_shock(d, lt)
    elif idx == 3:
        panel_compound(d, lt, dur)
    elif idx == 4:
        panel_allin(d, lt)
    elif idx == 5:
        panel_rules(d, lt)
    else:
        panel_tree(d, tm - LINES[6]["start"])
    subtitle(d, idx)
    title_card(d, tm)
    if idx == len(LINES) and lt > 0.5:
        ending(d, lt - 0.5)
    return img.resize((W, H), Image.LANCZOS)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:  # プレビュー: python render.py 12.5 20 ...
        for s in sys.argv[1:]:
            frame(int(float(s) * FPS)).save(os.path.join(HERE, f"preview_{s}.png"))
        sys.exit()
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", os.path.join(HERE, "voice.wav"),
                           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "22", "-preset", "medium",
                           "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", OUT],
                          stdin=subprocess.PIPE)
    for n in range(NFRAMES):
        ff.stdin.write(frame(n).tobytes())
    ff.stdin.close()
    ff.wait()
    print(f"done: {OUT}  {TOTAL:.1f}s  {NFRAMES} frames")
