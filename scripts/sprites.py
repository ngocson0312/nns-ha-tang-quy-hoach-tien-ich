"""Sprite RGBA dựng sẵn bằng PIL: huy hiệu phương tiện, ghim điểm, nhãn, thẻ dự án, chữ chương, bìa, chú giải.

Mọi hàm trả (arr RGBA uint8 H×W×4, (ax, ay)) — (ax, ay) là điểm neo trong sprite (vd đầu nhọn của ghim).
Vẽ ở 4× rồi thu nhỏ cho mượt cạnh (glyph) — chữ dùng PIL trực tiếp (đã khử răng cưa).
"""
import math, os
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import common as C

SS = 4


@lru_cache(None)
def font(path, size):
    return ImageFont.truetype(path, int(size))


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def darker(rgb, k=0.62):
    return tuple(int(c * k) for c in rgb)


def to_arr(im):
    return np.asarray(im.convert("RGBA")).copy()


def shadowed(im, blur=6, alpha=0.55, dy=4, spread=0):
    """thêm bóng mờ dưới sprite RGBA (PIL) — trả ảnh mới có lề."""
    pad = blur * 3 + abs(dy) + spread
    W, H = im.size
    out = Image.new("RGBA", (W + 2 * pad, H + 2 * pad), (0, 0, 0, 0))
    a = im.split()[3]
    if spread:
        a = a.filter(ImageFilter.MaxFilter(spread * 2 + 1))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(a.point(lambda v: int(v * alpha)))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(sh, (pad, pad + dy))
    out.alpha_composite(im, (pad, pad))
    return out, pad


# ------------------------------------------------------------------ glyph vector (vẽ trắng trên nền trong suốt)
def _glyph(kind, s):
    """glyph trắng cỡ s×s (đã ×SS)."""
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = (255, 255, 255, 255)
    k = s / 100.0
    if kind in ("metro", "ga", "tau"):
        # đầu tàu nhìn thẳng
        d.rounded_rectangle([22 * k, 10 * k, 78 * k, 74 * k], radius=14 * k, fill=w)
        d.rounded_rectangle([30 * k, 20 * k, 70 * k, 44 * k], radius=6 * k, fill=(0, 0, 0, 0))
        d.ellipse([30 * k, 54 * k, 40 * k, 64 * k], fill=(0, 0, 0, 0))
        d.ellipse([60 * k, 54 * k, 70 * k, 64 * k], fill=(0, 0, 0, 0))
        d.polygon([(32 * k, 74 * k), (24 * k, 90 * k), (33 * k, 90 * k), (40 * k, 74 * k)], fill=w)
        d.polygon([(68 * k, 74 * k), (76 * k, 90 * k), (67 * k, 90 * k), (60 * k, 74 * k)], fill=w)
    elif kind in ("duong", "oto", "nutgiao_xe"):
        # ô tô nhìn thẳng
        d.polygon([(28 * k, 46 * k), (36 * k, 22 * k), (64 * k, 22 * k), (72 * k, 46 * k)], fill=w)
        d.polygon([(35 * k, 43 * k), (41 * k, 28 * k), (59 * k, 28 * k), (65 * k, 43 * k)], fill=(0, 0, 0, 0))
        d.rounded_rectangle([16 * k, 42 * k, 84 * k, 70 * k], radius=10 * k, fill=w)
        d.ellipse([23 * k, 50 * k, 35 * k, 62 * k], fill=(0, 0, 0, 0))
        d.ellipse([65 * k, 50 * k, 77 * k, 62 * k], fill=(0, 0, 0, 0))
        d.rounded_rectangle([20 * k, 66 * k, 34 * k, 84 * k], radius=4 * k, fill=w)
        d.rounded_rectangle([66 * k, 66 * k, 80 * k, 84 * k], radius=4 * k, fill=w)
    elif kind in ("sanbay", "maybay"):
        # máy bay nhìn từ trên, mũi hướng lên-phải 45°
        pts = [(50, 6), (57, 18), (57, 40), (92, 60), (92, 68), (57, 56), (57, 78), (68, 87), (68, 93), (50, 88),
               (32, 93), (32, 87), (43, 78), (43, 56), (8, 68), (8, 60), (43, 40), (43, 18)]
        cx, cy, a = 50, 50, math.radians(45)
        rot = [((x - cx) * math.cos(a) - (y - cy) * math.sin(a) + cx, (x - cx) * math.sin(a) + (y - cy) * math.cos(a) + cy)
               for x, y in pts]
        d.polygon([(x * k, y * k) for x, y in rot], fill=w)
    elif kind == "cau":
        # cầu vòm trên mặt nước
        d.rectangle([10 * k, 52 * k, 90 * k, 60 * k], fill=w)
        d.arc([18 * k, 22 * k, 82 * k, 86 * k], 200, 340, fill=w, width=int(8 * k))
        for x in (30, 42, 58, 70):
            d.line([(x * k, 34 * k + abs(50 - x) * 0.55 * k), (x * k, 52 * k)], fill=w, width=int(4 * k))
        for i, y in enumerate((70, 82)):
            d.arc([14 * k, (y - 6) * k, 50 * k, (y + 6) * k], 200, 340, fill=w, width=int(5 * k))
            d.arc([50 * k, (y - 6) * k, 86 * k, (y + 6) * k], 200, 340, fill=w, width=int(5 * k))
    elif kind == "nutgiao":
        # nút giao: hai đường cắt nhau + vòng xuyến
        d.line([(12 * k, 50 * k), (88 * k, 50 * k)], fill=w, width=int(11 * k))
        d.line([(50 * k, 12 * k), (50 * k, 88 * k)], fill=w, width=int(11 * k))
        d.ellipse([28 * k, 28 * k, 72 * k, 72 * k], outline=w, width=int(9 * k))
    else:
        d.ellipse([30 * k, 30 * k, 70 * k, 70 * k], fill=w)
    return im


def _down(im, s):
    return im.resize((s, s), Image.LANCZOS)


@lru_cache(None)
def icon_badge(kind, color_hex, r=C.ICON_R):
    """huy hiệu tròn màu tuyến + viền trắng + glyph phương tiện; neo = tâm."""
    col = hex2rgb(color_hex)
    S = 2 * r * SS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], fill=(255, 255, 255, 255))
    e = int(5.5 * SS)
    d.ellipse([e, e, S - 1 - e, S - 1 - e], fill=col + (255,))
    g = _glyph(kind, int(S * 0.62))
    if col[0] > 200 and col[1] > 200 and col[2] > 200:           # huy hiệu sáng (sân bay) → glyph tối
        g = Image.merge("RGBA", (*[Image.new("L", g.size, v) for v in darker(col, 0.3)], g.split()[3]))
    im.alpha_composite(g, ((S - g.size[0]) // 2, (S - g.size[1]) // 2))
    im = im.resize((2 * r, 2 * r), Image.LANCZOS)
    im, pad = shadowed(im, blur=7, alpha=0.5, dy=5)
    return to_arr(im), (pad + r, pad + r)


@lru_cache(None)
def pin(kind, color_hex, h=74):
    """ghim giọt nước màu tuyến, ruột trắng có glyph; neo = mũi nhọn dưới cùng."""
    col = hex2rgb(color_hex)
    w = int(h * 0.78)
    S = SS
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    R = w * S / 2
    cx, cy = R, R
    d.ellipse([0, 0, 2 * R, 2 * R], fill=col + (255,))
    d.polygon([(cx - R * 0.62, cy + R * 0.72), (cx + R * 0.62, cy + R * 0.72), (cx, h * S - 1)], fill=col + (255,))
    ri = R * 0.72
    d.ellipse([cx - ri, cy - ri, cx + ri, cy + ri], fill=(255, 255, 255, 255))
    g = _glyph(kind, int(ri * 1.5))
    g = Image.merge("RGBA", (*[Image.new("L", g.size, v) for v in col], g.split()[3]))
    im.alpha_composite(g, (int(cx - g.size[0] / 2), int(cy - g.size[1] / 2)))
    im = im.resize((w, h), Image.LANCZOS)
    im, pad = shadowed(im, blur=5, alpha=0.5, dy=3)
    return to_arr(im), (pad + w // 2, pad + h - 1)


@lru_cache(None)
def dot(color_hex, r=11):
    col = hex2rgb(color_hex)
    S = 2 * r * SS
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], fill=(20, 22, 28, 255))
    e = int(S * 0.28)
    d.ellipse([e, e, S - 1 - e, S - 1 - e], fill=col + (255,))
    im = im.resize((2 * r, 2 * r), Image.LANCZOS)
    return to_arr(im), (r, r)


# ------------------------------------------------------------------ chữ
_CMAP = {}
_SUBST = {"→": "–", "←": "–", "⇒": "–", "•": "·", "✓": "", "✗": ""}
MISSING = set()


def safe_text(text, path):
    """thay ký tự font không có glyph (vd "→" trong Be Vietnam Pro hiện thành ô trống — chú giải Matrix One 17/10)."""
    if path not in _CMAP:
        from fontTools.ttLib import TTFont
        _CMAP[path] = set(TTFont(path).getBestCmap().keys())
    cm = _CMAP[path]
    out = []
    for ch in text:
        if ch.isspace() or ord(ch) in cm:
            out.append(ch)
        elif ch in _SUBST and all(ord(c) in cm for c in _SUBST[ch]):
            out.append(_SUBST[ch]); MISSING.add((ch, os.path.basename(path)))
        else:
            out.append("?"); MISSING.add((ch, os.path.basename(path)))
    return "".join(out)


def text_img(text, path, size, fill, stroke=0, stroke_fill=(255, 255, 255), spacing=0):
    text = safe_text(text, path)
    f = font(path, size)
    l, t, r, b = f.getbbox(text, stroke_width=stroke)
    im = Image.new("RGBA", (r - l + 4, b - t + 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2 - l, 2 - t), text, font=f, fill=fill + (255,) if len(fill) == 3 else fill,
                            stroke_width=stroke, stroke_fill=stroke_fill + (255,) if len(stroke_fill) == 3 else stroke_fill)
    return im


def stack(imgs, align="center", gap=2):
    W = max(i.size[0] for i in imgs)
    H = sum(i.size[1] for i in imgs) + gap * (len(imgs) - 1)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    y = 0
    for i in imgs:
        x = (W - i.size[0]) // 2 if align == "center" else (0 if align == "left" else W - i.size[0])
        out.alpha_composite(i, (x, y))
        y += i.size[1] + gap
    return out


@lru_cache(None)
def poi_label(lines, color_hex, sub=None, short=False, scale=1.0):
    """nhãn điểm: các dòng IN HOA màu tuyến (tối hơn để đọc được) viền trắng dày + dòng phụ trắng viền tối.
    lines: tuple chuỗi. Trả sprite, neo = giữa cạnh dưới."""
    col = hex2rgb(color_hex)
    fill = col if sum(col) < 600 else (40, 70, 140)
    fill = darker(fill, 0.86)
    sizes = [(C.S_LABEL if not short else C.S_LABEL2) * scale] + [C.S_LABEL2 * scale] * (len(lines) - 1)
    ims = [text_img(t, C.F_LABEL, s, fill, stroke=max(4, int(7 * scale)), stroke_fill=(255, 255, 255)) for t, s in zip(lines, sizes)]
    if sub and not short:
        ims.append(text_img(sub, C.F_SUB, C.S_SUB * max(scale, 0.9), (255, 255, 255), stroke=5, stroke_fill=(24, 26, 32)))
    im = stack(ims, gap=-6)
    im, pad = shadowed(im, blur=6, alpha=0.45, dy=4)
    return to_arr(im), (im.size[0] // 2, im.size[1] - pad)


@lru_cache(None)
def route_label(text, color_hex, sub=None):
    col = hex2rgb(color_hex)
    fill = darker(col, 0.80) if sum(col) < 600 else (50, 80, 150)
    ims = [text_img(text, C.F_LABEL, C.S_ROUTE, fill, stroke=6, stroke_fill=(255, 255, 255))]
    if sub:
        ims.append(text_img(sub, C.F_SUB, C.S_ROUTE_SUB, fill, stroke=5, stroke_fill=(255, 255, 255)))
    im = stack(ims, gap=-4)
    im, pad = shadowed(im, blur=5, alpha=0.4, dy=3)
    return to_arr(im), (im.size[0] // 2, im.size[1] // 2)


@lru_cache(None)
def km_label(text):
    im = text_img(text, C.F_SUB, C.S_KM, (255, 255, 255), stroke=5, stroke_fill=(20, 22, 28))
    return to_arr(im), (im.size[0] // 2, im.size[1] // 2)


@lru_cache(None)
def chapter_title(text):
    size = C.S_CHAPTER
    text = safe_text(text, C.F_TITLE)
    f = font(C.F_TITLE, size)
    l, t, r, b = f.getbbox(text)
    maxw = C.SAFE_X1 - C.SAFE_X0 - 40                 # chữ chương dài tự co cho vừa vùng an toàn (Matrix One 17/10)
    if r - l > maxw:
        size = int(size * maxw / (r - l))
        f = font(C.F_TITLE, size)
        l, t, r, b = f.getbbox(text)
    pad = 40
    im = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    # quầng tối mềm cho đọc được trên mọi nền
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).text((pad - l, pad - t), text, font=f, fill=(0, 0, 0, 200), stroke_width=6, stroke_fill=(0, 0, 0, 200))
    glow = glow.filter(ImageFilter.GaussianBlur(10))
    im.alpha_composite(glow)
    # chữ VÀNG gradient dọc (user chốt 18/10: "mấy chữ title này màu vàng") + viền nâu mảnh cho rõ nét chữ thư pháp
    edge = Image.new("L", im.size, 0)
    ImageDraw.Draw(edge).text((pad - l, pad - t), text, font=f, fill=255, stroke_width=4, stroke_fill=255)
    ed = Image.new("RGBA", im.size, C.CHAPTER_EDGE + (0,))
    ed.putalpha(edge)
    im.alpha_composite(ed)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).text((pad - l, pad - t), text, font=f, fill=255)
    g = np.linspace(0, 1, im.size[1])[:, None, None]
    top, bot = np.array(C.CHAPTER_TOP, float), np.array(C.CHAPTER_BOT, float)
    grad = np.repeat((top * (1 - g) + bot * g).astype(np.uint8), im.size[0], axis=1)
    im.alpha_composite(Image.fromarray(np.dstack([grad, np.asarray(mask)]), "RGBA"))
    return to_arr(im), (im.size[0] // 2, im.size[1] // 2)


@lru_cache(None)
def project_card(name, sub=None, compact=False, logo_path=None):
    """thẻ trắng bo góc: logo (nếu có) hoặc tên dự án 2 màu + dòng phụ; neo = giữa cạnh dưới (đặt trên ghim)."""
    if logo_path:
        lg = Image.open(logo_path).convert("RGBA")
        hh = 64 if not compact else 44
        lg = lg.resize((int(lg.size[0] * hh / lg.size[1]), hh), Image.LANCZOS)
        body = [lg]
    else:
        words = name.split()
        s = 58 if not compact else 40
        if len(words) >= 2 and words[0].lower() in ("the", "a"):
            a = text_img(words[0], C.F_CARD, s * 0.62, (30, 36, 70))
            b = text_img(" ".join(words[1:]), C.F_CARD, s, (30, 36, 70))
            body = [stack([a, b], gap=-10)]
        else:
            one = text_img(name, C.F_CARD, s, (30, 36, 70))
            maxw = 560 if not compact else 400
            if one.size[0] > maxw and len(words) >= 2:      # tên dài ("Lăng Chủ tịch Hồ Chí Minh") → 2 dòng cân nhau
                best = None
                for i in range(1, len(words)):
                    a_, b_ = " ".join(words[:i]), " ".join(words[i:])
                    sc_ = max(len(a_), len(b_))
                    if best is None or sc_ < best[0]:
                        best = (sc_, a_, b_)
                s2 = s * 0.8
                body = [stack([text_img(best[1], C.F_CARD, s2, (30, 36, 70)), text_img(best[2], C.F_CARD, s2, (30, 36, 70))], gap=-6)]
                if body[0].size[0] > maxw:
                    body = [body[0].resize((maxw, int(body[0].size[1] * maxw / body[0].size[0])), Image.LANCZOS)]
            else:
                body = [one]
    if sub and not compact:
        body.append(text_img(sub, C.F_SUB, 26, (40, 44, 60)))
    inner = stack(body, gap=2)
    px, py = (22, 14) if not compact else (16, 10)
    W, H = inner.size[0] + 2 * px, inner.size[1] + 2 * py
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([0, 0, W - 1, H - 1], radius=18 if not compact else 14, fill=(255, 255, 255, 250))
    card.alpha_composite(inner, (px, py))
    card, pad = shadowed(card, blur=9, alpha=0.5, dy=6)
    return to_arr(card), (card.size[0] // 2, card.size[1] - pad)


@lru_cache(None)
def project_pin(r=17):
    S = 2 * r * SS
    im = Image.new("RGBA", (S + 8 * SS, S + 8 * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    o = 4 * SS
    d.ellipse([0, 0, S + 2 * o - 1, S + 2 * o - 1], fill=(255, 205, 40, 120))
    d.ellipse([o, o, o + S, o + S], fill=(20, 20, 26, 255))
    e = int(S * 0.22)
    d.ellipse([o + e, o + e, o + S - e, o + S - e], fill=C.PIN_RED + (255,))
    w = im.size[0] // SS
    im = im.resize((w, w), Image.LANCZOS)
    return to_arr(im), (w // 2, w // 2)


@lru_cache(None)
def cover(lines, sub=None):
    """bìa: dòng 1 cam-vàng, dòng 2 xanh, chữ khối nghiêng viền tối; dòng phụ thư pháp trắng."""
    grads = [((255, 236, 120), (255, 150, 20), (120, 30, 10)), ((140, 230, 255), (20, 110, 240), (10, 30, 90))]
    out = []
    for i, t in enumerate(lines):
        top, bot, edge = grads[min(i, 1)]
        size = C.S_COVER1 if i == 0 else C.S_COVER2
        f = font(C.F_COVER, size)
        l, tt, r, b = f.getbbox(t, stroke_width=10)
        W, H = r - l + 30, b - tt + 30
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).text((15 - l, 15 - tt), t, font=f, fill=255)
        stroke = Image.new("L", (W, H), 0)
        ImageDraw.Draw(stroke).text((15 - l, 15 - tt), t, font=f, fill=255, stroke_width=10, stroke_fill=255)
        g = np.linspace(0, 1, H)[:, None, None]
        grad = (np.array(top) * (1 - g) + np.array(bot) * g).astype(np.uint8)
        grad = np.repeat(grad, W, axis=1)
        im = Image.new("RGBA", (W, H), edge + (0,))
        im.putalpha(stroke)
        fill = Image.fromarray(np.dstack([grad, np.asarray(mask)]), "RGBA")
        im.alpha_composite(fill)
        out.append(im)
    if sub:
        # dòng phụ bìa: chữ đậm thẳng trắng viền tối (bỏ thư pháp nghiêng — user 18/10)
        out.append(text_img(sub, C.F_TITLE, C.S_COVER3 * 0.82, (255, 255, 255), stroke=5, stroke_fill=(20, 22, 30)))
    maxw = C.W - 120                                   # tự co cho vừa khung (chữ dài như "QUANH THE CITYON")
    out = [o.resize((maxw, int(o.size[1] * maxw / o.size[0])), Image.LANCZOS) if o.size[0] > maxw else o for o in out]
    im = stack(out, gap=-8)
    im, pad = shadowed(im, blur=12, alpha=0.65, dy=8, spread=2)
    return to_arr(im), (im.size[0] // 2, im.size[1] // 2)


@lru_cache(None)
def legend(items):
    """items: tuple (tên, màu hex); 2 cột; thẻ trắng bo góc; neo = giữa cạnh trên."""
    rows = [items[i:i + 2] for i in range(0, len(items), 2)]
    col_imgs = []
    for name, colh in items:
        t = text_img(name, C.F_LEGEND, C.S_LEGEND, INK_RGB)
        bar = Image.new("RGBA", (44, 12), hex2rgb(colh) + (255,))
        if sum(hex2rgb(colh)) > 600:                    # màu quá sáng trên thẻ trắng → viền xám cho thấy
            ImageDraw.Draw(bar).rectangle([0, 0, 43, 11], outline=(120, 128, 140, 255), width=2)
        row = Image.new("RGBA", (44 + 14 + t.size[0], max(t.size[1], 12)), (0, 0, 0, 0))
        row.alpha_composite(bar, (0, (row.size[1] - 12) // 2))
        row.alpha_composite(t, (58, 0))
        col_imgs.append(row)
    half = (len(col_imgs) + 1) // 2
    left, right = col_imgs[:half], col_imgs[half:]
    L = stack(left, align="left", gap=8)
    R = stack(right, align="left", gap=8) if right else Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    gapx = 40
    W = L.size[0] + gapx + R.size[0] + 60
    H = max(L.size[1], R.size[1]) + 44
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([0, 0, W - 1, H - 1], radius=24, fill=(255, 255, 255, 248))
    card.alpha_composite(L, (30, 22))
    card.alpha_composite(R, (30 + L.size[0] + gapx, 22))
    maxw = C.SAFE_X1 - C.SAFE_X0
    if card.size[0] > maxw:                        # tên tuyến dài → co cả thẻ, không để tràn mép (Matrix One 17/10)
        card = card.resize((maxw, int(card.size[1] * maxw / card.size[0])), Image.LANCZOS)
    card, pad = shadowed(card, blur=10, alpha=0.45, dy=6)
    return to_arr(card), (card.size[0] // 2, pad)


@lru_cache(None)
def end_card(line1, line2=None):
    ims = [text_img(line1, C.F_LABEL, 64, (30, 36, 70))]
    if line2:
        ims.append(text_img(line2, C.F_SUB, 44, (200, 40, 50)))
    inner = stack(ims, gap=8)
    W, H = inner.size[0] + 80, inner.size[1] + 50
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle([0, 0, W - 1, H - 1], radius=28, fill=(255, 255, 255, 250))
    card.alpha_composite(inner, (40, 25))
    card, pad = shadowed(card, blur=12, alpha=0.5, dy=8)
    return to_arr(card), (card.size[0] // 2, card.size[1] // 2)


INK_RGB = C.INK


def size_of(sprite):
    arr, anc = sprite
    return arr.shape[1], arr.shape[0], anc
