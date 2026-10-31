"""Google Flow の Ingredients（参考画像）に使う、アニメ風の「破れたお札」の画像を作る。

本物のお札に見えないよう、文字・数字・肖像のない簡略化したデザインにしている。
出力: prop_full.png（破れていない1枚）、prop_half.png（まん中で半分に破れた左半分）、prop_corner.png（角が少し欠けたほぼ1枚）、
      prop_scrap.png（小さな切れはし）  いずれも 1200x900・白背景
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
S = 2                                  # 2倍で描いて縮小（なめらかな線）
W, H = 1200, 900
NW, NH = 880, 440                      # お札の大きさ
PAPER, PAPER_DK = (222, 233, 206), (196, 212, 178)
INK, LINE = (58, 78, 62), (120, 150, 118)


def P(*v):
    return [a * S for a in v]


def note_layer(cx, cy, angle=0):
    """お札1枚を RGBA で描く（中心 cx, cy）。"""
    lay = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    x0, y0, x1, y1 = cx - NW / 2, cy - NH / 2, cx + NW / 2, cy + NH / 2
    d.rounded_rectangle(P(x0, y0, x1, y1), radius=18 * S, fill=PAPER + (255,), outline=INK + (255,), width=4 * S)
    d.rounded_rectangle(P(x0 + 26, y0 + 26, x1 - 26, y1 - 26), radius=10 * S, outline=LINE + (255,), width=3 * S)
    d.rounded_rectangle(P(x0 + 36, y0 + 36, x1 - 36, y1 - 36), radius=8 * S, outline=LINE + (140,), width=1 * S)
    # 地紋（波線）
    for k in range(9):
        pts = []
        for i in range(0, 121):
            t = i / 120
            x = x0 + 50 + t * (NW * 0.52)
            y = y0 + 80 + k * 32 + math.sin(t * math.pi * 6 + k) * 7
            pts += P(x, y)
        d.line(pts, fill=PAPER_DK + (255,), width=2 * S)
    # すかしの楕円（右側）と飾りの丸
    ox, oy = x1 - 190, cy
    d.ellipse(P(ox - 110, oy - 130, ox + 110, oy + 130), fill=(236, 243, 228, 255), outline=LINE + (255,), width=3 * S)
    d.ellipse(P(ox - 92, oy - 112, ox + 92, oy + 112), outline=LINE + (120,), width=2 * S)
    for k in range(12):
        a = k / 12 * 2 * math.pi
        sx, sy = x0 + 150 + math.cos(a) * 52, y1 - 120 + math.sin(a) * 52
        d.ellipse(P(sx - 16, sy - 16, sx + 16, sy + 16), outline=LINE + (255,), width=2 * S)
    d.ellipse(P(x0 + 112, y1 - 158, x0 + 188, y1 - 82), fill=PAPER_DK + (255,), outline=INK + (255,), width=3 * S)
    # 紙の上側の光
    d.rounded_rectangle(P(x0 + 6, y0 + 6, x1 - 6, y0 + 40), radius=12 * S, fill=(255, 255, 255, 50))
    if angle:
        lay = lay.rotate(angle, resample=Image.BICUBIC, center=(cx * S, cy * S))
    return lay


def jagged(a, b, rng, step=16, amp=9):
    """a→b の破れ目のギザギザの点列。"""
    (ax, ay), (bx, by) = a, b
    n = max(2, int(math.hypot(bx - ax, by - ay) / step))
    nx, ny = -(by - ay), bx - ax
    ln = math.hypot(nx, ny) or 1
    nx, ny = nx / ln, ny / ln
    pts = []
    for i in range(n + 1):
        t = i / n
        o = 0 if i in (0, n) else rng.uniform(-amp, amp) + math.sin(t * 9) * amp * 0.4
        pts.append((ax + (bx - ax) * t + nx * o, ay + (by - ay) * t + ny * o))
    return pts


def cut(lay, keep_poly, tear_pts):
    """keep_poly の中だけ残し、破れ目（tear_pts）に白い繊維と輪郭線を描く。"""
    paper = lay.getchannel("A").filter(ImageFilter.MaxFilter(5))             # 破れる前のお札の形
    mask = Image.new("L", lay.size, 0)
    ImageDraw.Draw(mask).polygon([c * S for p in keep_poly for c in p], fill=255)
    a = np.minimum(np.asarray(lay.getchannel("A")), np.asarray(mask))
    lay.putalpha(Image.fromarray(a))
    edge = Image.new("RGBA", lay.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(edge)
    flat = [c * S for p in tear_pts for c in p]
    d.line(flat, fill=(250, 252, 245, 255), width=9 * S, joint="curve")      # 紙の繊維
    d.line(flat, fill=INK + (255,), width=3 * S, joint="curve")              # 輪郭
    # 破れ目の線は、お札があった場所だけに描く
    edge.putalpha(Image.fromarray(np.minimum(np.asarray(edge.getchannel("A")), np.asarray(paper))))
    lay.alpha_composite(edge)
    return lay


def save(lay, name, fit=0.78):
    """お札を画面の中央に、同じくらいの大きさで置いて保存する。"""
    bb = lay.getchannel("A").getbbox()
    piece = lay.crop(bb)
    k = min(W * S * fit / piece.width, H * S * fit / piece.height, 2.2)
    piece = piece.resize((int(piece.width * k), int(piece.height * k)), Image.LANCZOS)
    lay = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    lay.alpha_composite(piece, ((W * S - piece.width) // 2, (H * S - piece.height) // 2))
    shadow = lay.getchannel("A").filter(ImageFilter.GaussianBlur(14 * S))
    bg = Image.new("RGBA", lay.size, (255, 255, 255, 255))
    sh = Image.new("RGBA", lay.size, (40, 50, 40, 0))
    sh.putalpha(shadow.point(lambda v: int(v * 0.28)))
    bg.alpha_composite(sh, (10 * S, 14 * S))
    bg.alpha_composite(lay)
    bg.convert("RGB").resize((W, H), Image.LANCZOS).save(os.path.join(HERE, name))
    print("saved", name)


def main():
    rng = np.random.default_rng(7)
    cx, cy = W / 2, H / 2
    x0, y0, x1, y1 = cx - NW / 2, cy - NH / 2, cx + NW / 2, cy + NH / 2

    # 0) 破れていない1枚（シリーズ1話のつかみで破る前のお札）
    save(note_layer(cx, cy, angle=-3), "prop_full.png")

    # 1) まん中で半分に破れた左半分（少し右にずらして中央に見せる）
    off = NW / 4
    lay = note_layer(cx + off, cy, angle=-4)
    tear = jagged((cx + off + 4, y0 - 40), (cx + off - 6, y1 + 40), rng)
    save(cut(lay, [(0, 0)] + tear + [(0, H)], tear), "prop_half.png")

    # 2) 右上の角が少し欠けた、ほぼ1枚
    lay = note_layer(cx, cy, angle=-3)
    tear = jagged((x1 - 230, y0 - 40), (x1 + 40, y0 + 150), rng, amp=8)
    keep = [(0, 0), (x1 - 230, 0)] + tear[1:-1] + [(W, y0 + 150), (W, H), (0, H)]
    save(cut(lay, keep, tear), "prop_corner.png")

    # 3) 小さな切れはし（左下の角のかけら）を大きめに
    lay = note_layer(cx + 300, cy - 150, angle=8)
    a = (cx - 190, cy - 120)
    b = (cx + 70, cy + 190)
    tear = jagged((cx - 230, cy - 10), (cx - 40, cy - 120), rng, amp=10) + \
        jagged((cx - 40, cy - 120), (cx + 140, cy + 60), rng, amp=10)[1:]
    keep = [(0, H)] + [(0, cy - 10)] + tear + [(cx + 140, H)]
    save(cut(lay, keep, tear), "prop_scrap.png", fit=0.45)


if __name__ == "__main__":
    main()
