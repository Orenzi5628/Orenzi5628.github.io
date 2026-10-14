"""ネコ先生（cat_cutout.png）をパーツに分けて動かす。

元画像の座標（768x1376）で、頭・胴体・しっぽに分け、
頭のうなずき、しっぽの揺れ、まばたき、口パク、メガネの光を付ける。
"""
import math
import os
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))

NECK = (365, 398)         # 頭の回転の中心
TAIL_PIVOT = (512, 832)   # しっぽの付け根
EYES = ((318, 302), (422, 302))
LENSES = ((327, 317), (397, 317))
MOUTH = (364, 364)
FEET_Y = 1310             # 靴の底
FUR = (180, 184, 192)
RIM = (178, 148, 86)
LINE = (70, 62, 66)


@lru_cache(maxsize=1)
def parts():
    im = Image.open(os.path.join(HERE, "cat_cutout.png")).convert("RGBA")
    a = np.asarray(im).copy()
    H, W = a.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W]
    tail_m = (xx >= TAIL_PIVOT[0]) & (yy >= 800) & (yy < 1200)
    head_m = yy < NECK[1] + 6
    body = a.copy()
    body[tail_m | (yy < NECK[1] - 4), 3] = 0
    head = a.copy()
    head[~head_m, 3] = 0
    tail = a.copy()
    tail[~tail_m, 3] = 0
    return Image.fromarray(head), Image.fromarray(body), Image.fromarray(tail)


FX0, FY0, FX1, FY1 = 260, 240, 470, 410   # 顔の描き足し範囲
AA = 4


@lru_cache(maxsize=1)
def eye_fur():
    """目の周りの毛の色（まばたきで目を隠す色）。"""
    im = np.asarray(parts()[0]).astype(float)
    cols = []
    for ex, ey in EYES:
        ring = [im[ey + int(28 * math.sin(t)), ex + int(36 * math.cos(t)), :3] for t in np.linspace(0, 2 * math.pi, 40)]
        ring = [r for r in ring if r.mean() > 150]
        cols.append(tuple(int(v) for v in np.median(ring, axis=0)))
    return cols


def face_overlay(head, vowel, blink, glint, stern):
    """頭パーツのコピーに口・まぶた・メガネの光を描く（4倍で描いて縮小）。"""
    lay = Image.new("RGBA", ((FX1 - FX0) * AA, (FY1 - FY0) * AA))
    d = ImageDraw.Draw(lay)

    def P(*v):
        return [(q - (FX0 if i % 2 == 0 else FY0)) * AA for i, q in enumerate(v)]

    def W(n):
        return int(n * AA)

    if blink:
        lid = Image.new("L", lay.size)
        ld = ImageDraw.Draw(lid)
        for ex, ey in EYES:
            ld.ellipse(P(ex - 27, ey - 18, ex + 27, ey + 17), fill=255)
        lid = lid.filter(ImageFilter.GaussianBlur(2.5 * AA))
        fur = Image.new("RGBA", lay.size, eye_fur()[0] + (255,))
        lay.paste(fur, (0, 0), lid)
        for ex, ey in EYES:
            d.arc(P(ex - 23, ey - 16, ex + 23, ey + 10), 25, 155, fill=LINE, width=W(3))
    elif stern:  # キリッとした眉
        for (ex, ey), sgn in zip(EYES, (1, -1)):
            d.line(P(ex - 22 * sgn, ey - 30, ex + 16 * sgn, ey - 22), fill=LINE, width=W(3.5))
    mx, my = MOUTH
    open_ = {"a": 20, "o": 16, "e": 13, "u": 9, "i": 8}.get(vowel, 0)
    if open_:
        w = {"i": 22, "e": 20, "a": 18, "o": 14, "u": 11}[vowel]
        fur = eye_fur()[0]
        d.ellipse(P(mx - 36, my - 12, mx + 36, my + 22), fill=fur + (255,))       # 元の口を消す
        d.chord(P(mx - w, my - 8, mx + w, my - 4 + open_ * 1.6), 0, 180, fill=(140, 60, 72), outline=LINE, width=W(2.5))
        d.ellipse(P(mx - w * 0.55, my - 3 + open_ * 0.55, mx + w * 0.55, my - 3 + open_ * 1.45), fill=(225, 118, 125))
        d.arc(P(mx - 32, my - 16, mx + 1, my - 1), 15, 165, fill=LINE, width=W(2.5))  # ω
        d.arc(P(mx - 1, my - 16, mx + 32, my - 1), 15, 165, fill=LINE, width=W(2.5))
    if glint > 0:  # メガネがキラッ
        for lx, ly in LENSES:
            a = int(230 * glint)
            d.polygon(P(lx - 13, ly + 11, lx - 3, ly - 15, lx + 3, ly - 15, lx - 7, ly + 11), fill=(255, 255, 255, a))
            d.polygon(P(lx + 2, ly + 8, lx + 8, ly - 6, lx + 11, ly - 6, lx + 5, ly + 8), fill=(255, 255, 255, a))
    lay = lay.reduce(AA)
    h = head.copy()
    region = h.crop((FX0, FY0, FX1, FY1))
    region.alpha_composite(lay)
    region.putalpha(head.crop((FX0, FY0, FX1, FY1)).getchannel("A"))
    if blink:  # メガネのフチは元の絵のまま残す
        orig = head.crop((FX0, FY0, FX1, FY1))
        o = np.asarray(orig).astype(int)
        rim = ((o[..., 0] - o[..., 2] > 45) & (o[..., 0] > 120) & (o[..., 3] > 0)).astype(np.uint8) * 255
        region.paste(orig, (0, 0), Image.fromarray(rim))
    h.paste(region, (FX0, FY0))
    return h


def sprite(tm, vowel=None, blink=False, glint=0.0, stern=False, nod=0.0, lean=0.0):
    """元画像サイズの RGBA に全パーツを組み立てる。"""
    head, body, tail = parts()
    out = Image.new("RGBA", body.size)
    sway = math.sin(tm * 1.6) * 6 + math.sin(tm * 3.7) * 2
    out.alpha_composite(tail.rotate(sway, resample=Image.BICUBIC, center=TAIL_PIVOT))
    out.alpha_composite(body)
    out.alpha_composite(face_overlay(head, vowel, blink, glint, stern).rotate(nod, resample=Image.BICUBIC, center=NECK))
    if lean:
        out = out.rotate(lean, resample=Image.BICUBIC, center=(365, FEET_Y))
    return out


def draw(c, scale_px, x, feet_y, height, tm, bob=0.0, **kw):
    """Canvas c に描く。x, feet_y, height は設計座標、scale_px は設計座標1単位の描画ピクセル数(z込み)。"""
    img = sprite(tm, **kw)
    s = height / (FEET_Y - 150)              # 元画像1px → 設計座標
    ox = x - 365 * s                         # 元画像の (0,0) の設計座標
    oy = feet_y - FEET_Y * s + bob
    c.ell(x - 95, feet_y - 10, x + 95, feet_y + 12, fill=(0, 0, 0, 45))  # 影
    bb = img.getbbox()
    crop = img.crop(bb)
    tw, th = max(1, int(crop.width * s * scale_px)), max(1, int(crop.height * s * scale_px))
    crop = crop.resize((tw, th), Image.LANCZOS)
    X, Y = c.P(ox + bb[0] * s, oy + bb[1] * s)
    c.img.paste(crop, (int(round(X)), int(round(Y))), crop)
