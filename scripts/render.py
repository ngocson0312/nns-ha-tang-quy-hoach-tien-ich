"""Dựng hình từ plan.json → video câm (hoặc vài khung PNG để xem trước).

  python render.py --plan work/plan.json --out work/video_cam.mp4 [--workers 6]
  python render.py --plan work/plan.json --frames 1.0,6.5,20 --outdir work/preview
  python render.py --plan work/plan.json --prefetch          # chỉ tải tile cần dùng

Lớp (dưới → trên): ảnh vệ tinh Esri nhiều tầng (crossfade giữa tầng) → phối cảnh dự án → tối ngoài spotlight →
vòng km nét đứt ĐỨNG YÊN → nét tuyến (bóng, viền trắng, lõi màu) → ghim điểm → ghim + thẻ dự án → huy hiệu phương
tiện → nhãn → chữ chương → bìa → chú giải → khung kết.
"""
import argparse, math, os, subprocess, sys, time
from collections import OrderedDict
import numpy as np, cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import geo
import sprites as SP

W, H, FPS = C.W, C.H, C.FPS
ZMIN, ZMAX = 8, 18


def ease_s(x):
    x = min(1.0, max(0.0, x)); return 0.5 - 0.5 * math.cos(math.pi * x)


def smooth(x):
    x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)


def back_out(x, s=1.7):
    x = min(1.0, max(0.0, x)) - 1; return 1 + x * x * ((s + 1) * x + s)


def fade(t, t0, d):
    return smooth((t - t0) / d) if d > 0 else float(t >= t0)


def window(t, t0, t1, din, dout):
    return min(fade(t, t0, din), 1 - fade(t, t1, dout))


# ================================================================== camera
class Camera:
    def __init__(self, plan):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import plan as PL
        self.segs = plan["camera"]
        self.k = plan["meta"]["k"]
        self.f = {}
        self.PL = PL

    def __call__(self, t):
        return self.PL.camera_at(self.segs, t, self.k)

    def _old(self, t):
        for i, s in enumerate(self.segs):
            if t <= s["t1"] or i == len(self.segs) - 1:
                c0, c1 = np.array(s["c0"]), np.array(s["c1"])
                if s["mode"] == "hold":
                    return c0, s["u0"]
                x = (t - s["t0"]) / max(s["t1"] - s["t0"], 1e-6)
                x = min(1.0, max(0.0, x))
                if s["mode"] == "lin":
                    return c0 + (c1 - c0) * x, math.exp(math.log(s["u0"]) + (math.log(s["u1"]) - math.log(s["u0"])) * x)
                if i not in self.f:
                    self.f[i] = self.PL.vw_path(c0, c1, s["u0"], s["u1"], self.k)
                return self.f[i](ease_s(x))
        s = self.segs[-1]
        return np.array(s["c1"]), s["u1"]


# ================================================================== tile
TILE_M = lambda z: 2 * math.pi * geo.R / (2 ** z)
ORG = -math.pi * geo.R


def levels_for(u):
    """các tầng ảnh + trọng số cho mét Mercator/px = u."""
    zf = math.log2(2 * math.pi * geo.R / (256 * u))
    base = math.floor(zf + 0.35)
    frac = zf + 0.35 - base                      # 0..1 trong tầng base
    out = [(int(np.clip(base, ZMIN, ZMAX)), 1.0)]
    if frac > 0.85 and base + 1 <= ZMAX:          # sắp sang tầng mịn hơn → hoà dần
        w = smooth((frac - 0.85) / 0.15)
        out = [(int(np.clip(base, ZMIN, ZMAX)), 1 - w), (base + 1, w)]
    return out


def tiles_for(c, u, z, pad=1):
    r = TILE_M(z) / 256
    x0 = (c[0] - W / 2 * u - ORG) / r / 256
    x1 = (c[0] + W / 2 * u - ORG) / r / 256
    y0 = (c[1] - H / 2 * u - ORG) / r / 256
    y1 = (c[1] + H / 2 * u - ORG) / r / 256
    return range(int(math.floor(x0)) - pad, int(math.floor(x1)) + pad + 1), range(int(math.floor(y0)) - pad, int(math.floor(y1)) + pad + 1)


class Tiles:
    def __init__(self, cap=1400):
        self.cache = OrderedDict()
        self.cap = cap
        self.blank = np.full((256, 256, 3), (40, 46, 40), np.uint8)

    def get(self, z, x, y):
        key = (z, x, y)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        n = 2 ** z
        if not (0 <= x < n and 0 <= y < n):
            im = self.blank
        else:
            p = os.path.join(geo.TILE_CACHE, f"{z}_{x}_{y}.jpg")
            if not os.path.exists(p):
                try:
                    geo.fetch_tile(z, x, y)
                except Exception:
                    pass
            im = cv2.imread(p) if os.path.exists(p) else None
            if im is None or im.shape[:2] != (256, 256):
                im = self.blank
        self.cache[key] = im
        if len(self.cache) > self.cap:
            self.cache.popitem(last=False)
        return im

    def layer(self, c, u, z):
        xs, ys = tiles_for(c, u, z)
        patch = np.empty((len(ys) * 256, len(xs) * 256, 3), np.uint8)
        for j, y in enumerate(ys):
            for i, x in enumerate(xs):
                patch[j * 256:(j + 1) * 256, i * 256:(i + 1) * 256] = self.get(z, x, y)
        r = TILE_M(z) / 256
        A = u / r
        if A > 1.3:                                   # thu nhỏ nhiều → lọc trước cho bớt răng cưa
            patch = cv2.GaussianBlur(patch, (0, 0), 0.42 * A)
        bx = (c[0] - W / 2 * u - ORG) / r - xs[0] * 256
        by = (c[1] - H / 2 * u - ORG) / r - ys[0] * 256
        M = np.array([[A, 0, bx + 0.5 * A - 0.5], [0, A, by + 0.5 * A - 0.5]], np.float64)
        return cv2.warpAffine(patch, M, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)


def render_map(tiles, c, u):
    lv = levels_for(u)
    if len(lv) == 1:
        return tiles.layer(c, u, lv[0][0]).astype(np.float32)
    (z0, w0), (z1, w1) = lv
    return tiles.layer(c, u, z0).astype(np.float32) * w0 + tiles.layer(c, u, z1).astype(np.float32) * w1


# ================================================================== vẽ chồng
def over(canvas, arr, x, y, alpha=1.0, scale=1.0):
    """dán sprite RGBA arr với góc trên-trái (x, y) (float) lên canvas float BGR."""
    if alpha <= 0.003:
        return
    if abs(scale - 1.0) > 1e-3:
        h, w = arr.shape[:2]
        nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
        arr = cv2.resize(arr, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    h, w = arr.shape[:2]
    xi, yi = int(math.floor(x)), int(math.floor(y))
    x0, y0, x1, y1 = max(0, xi), max(0, yi), min(W, xi + w), min(H, yi + h)
    if x0 >= x1 or y0 >= y1:
        return
    sub = arr[y0 - yi:y1 - yi, x0 - xi:x1 - xi].astype(np.float32)
    a = sub[..., 3:4] / 255.0 * alpha
    rgb = sub[..., 2::-1]                             # RGBA → BGR
    canvas[y0:y1, x0:x1] += (rgb - canvas[y0:y1, x0:x1]) * a


def put(canvas, spr, px, py, alpha=1.0, scale=1.0):
    arr, (ax, ay) = spr
    over(canvas, arr, px - ax * scale, py - ay * scale, alpha, scale)


_INK = {}


def ink_box(spr):
    """hộp mực thật (alpha > 60) của sprite, toạ độ trong sprite — bỏ bóng mờ."""
    key = id(spr[0])
    if key not in _INK:
        ys, xs = np.nonzero(spr[0][..., 3] > 60)
        _INK[key] = (xs.min(), ys.min(), xs.max(), ys.max()) if len(xs) else (0, 0, 1, 1)
    return _INK[key]


def leader(canvas, spr, lx, ly, pin, alpha, scale=1.0):
    """đường dẫn mảnh từ đầu ghim tới mép gần nhất của nhãn khi nhãn đứng xa ghim (> LEADER_MIN px) —
    nhãn bị đẩy xa vì chật chỗ mà không có đường dẫn thì người xem gán nhầm sang ghim khác (Matrix One 17/10)."""
    if alpha <= 0.02:
        return
    arr, (ax, ay) = spr
    x0, y0, x1, y1 = ink_box(spr)
    bx0, by0 = lx + (x0 - ax) * scale, ly + (y0 - ay) * scale
    bx1, by1 = lx + (x1 - ax) * scale, ly + (y1 - ay) * scale
    px, py = pin
    cx, cy = min(max(px, bx0), bx1), min(max(py, by0), by1)
    d = math.hypot(cx - px, cy - py)
    if d < C.LEADER_MIN:
        return
    k = (d - 10) / d                                   # dừng cách nhãn 10 px
    ex, ey = px + (cx - px) * k, py + (cy - py) * k
    m = np.zeros((H, W), np.uint8)
    cv2.line(m, (int(px * 4), int(py * 4)), (int(ex * 4), int(ey * 4)), 255, 9 * 4 // 2, cv2.LINE_AA, 2)
    m2 = np.zeros((H, W), np.uint8)
    cv2.line(m2, (int(px * 4), int(py * 4)), (int(ex * 4), int(ey * 4)), 255, 3 * 4 // 2, cv2.LINE_AA, 2)
    a1 = m.astype(np.float32)[..., None] / 255 * 0.55 * alpha
    canvas *= (1 - a1)
    a2 = m2.astype(np.float32)[..., None] / 255 * alpha
    canvas += (255 - canvas) * a2
    cv2.circle(canvas, (int(ex), int(ey)), 4, (255, 255, 255), -1, cv2.LINE_AA) if alpha > 0.5 else None


def hexbgr(h):
    r, g, b = SP.hex2rgb(h)
    return (b, g, r)


class Scene:
    def __init__(self, plan):
        import plan as PL
        self.PL = PL
        self.p = plan
        self.cam = Camera(plan)
        self.tiles = Tiles()
        self.k = plan["meta"]["k"]
        self.PM = np.array(plan["project"]["m"])
        self.routes = {k: dict(v, P=np.array(v["P"]), L=geo.cumlen(np.array(v["P"]))) for k, v in plan["routes"].items()}
        pr = plan["project"]
        self.card_full = SP.project_card(pr["name"], pr["sub"], False, pr["logo"])
        self.card_mini = SP.project_card(pr["name"], None, True, pr["logo"])
        self.pin = SP.project_pin()
        self.mp = None
        if plan.get("masterplan"):
            m = plan["masterplan"]
            img = cv2.imread(m["img"], cv2.IMREAD_UNCHANGED)
            (n, w_), (s, e) = m["bounds"]
            self.mp = dict(img=img, m0=geo.ll2m(n, w_), m1=geo.ll2m(s, e), xfade=m["xfade"], t_out=m["t_out"],
                           opacity=float(m.get("opacity", 1.0)), show_ring=bool(m.get("ring", True)))
            # tháp ảnh: lớp quy hoạch 4096 px thu nhỏ ×4–×8 khi máy lùi xa — warpAffine không lọc khi thu nhỏ (INTER_AREA
            # không có tác dụng) → viền lô mảnh răng cưa / nhấp nháy. Chọn tầng tháp sao cho tỉ lệ ≥ 0,6
            pyr = [img]
            while max(pyr[-1].shape[:2]) > 700:
                pyr.append(cv2.pyrDown(pyr[-1]))
            self.mp["pyr"] = pyr
            a = img[..., 3]
            cnts, _ = cv2.findContours((a > 128).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            ring = max(cnts, key=cv2.contourArea).reshape(-1, 2).astype(float)
            sx = (self.mp["m1"][0] - self.mp["m0"][0]) / img.shape[1]
            sy = (self.mp["m1"][1] - self.mp["m0"][1]) / img.shape[0]
            self.mp["ring"] = self.mp["m0"] + ring * [sx, sy]

    # ---------------------------------------------------------- tiện ích
    def scr(self, m, c, u):
        return (np.asarray(m, float) - c) / u + np.array([W / 2, H / 2])

    def route_pts(self, key, s0, s1, c, u):
        r = self.routes[key]
        P, L = r["P"], r["L"]
        a, b = sorted((s0, s1))
        step = max(1, int((1.5 * u) / max(L[1] - L[0], 1e-6))) if len(L) > 1 else 1
        i0, i1 = np.searchsorted(L, a), np.searchsorted(L, b)
        idx = list(range(i0, i1, step))
        pts = [geo.point_at(P, L, a)] + [P[i] for i in idx] + [geo.point_at(P, L, b)]
        pts = np.array(pts)
        if s1 < s0:
            pts = pts[::-1]
        return self.scr(pts, c, u)

    # ---------------------------------------------------------- khung
    def frame(self, t):
        p = self.p
        c, u = self.cam(t)
        canvas = render_map(self.tiles, c, u)
        # nhẹ: tăng tương phản một chút như ảnh mẫu
        canvas = (canvas - 128) * 1.04 + 128 + 2

        # phối cảnh dự án
        if self.mp is not None:
            a_in = fade(t, self.mp["xfade"][0], self.mp["xfade"][1] - self.mp["xfade"][0])
            a_out = 1 - fade(t, self.mp["t_out"][0], self.mp["t_out"][1] - self.mp["t_out"][0])
            al = a_in * a_out * self.mp.get("opacity", 1.0)
            if al > 0.003:
                q0, q1 = self.scr(self.mp["m0"], c, u), self.scr(self.mp["m1"], c, u)
                img = self.mp["img"]
                for lv in self.mp["pyr"]:
                    img = lv
                    if (q1[0] - q0[0]) / lv.shape[1] >= 0.6:
                        break
                sx = (q1[0] - q0[0]) / img.shape[1]
                sy = (q1[1] - q0[1]) / img.shape[0]
                M = np.array([[sx, 0, q0[0]], [0, sy, q0[1]]])
                warped = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_AREA if sx < 1 else cv2.INTER_LINEAR,
                                        borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
                a = warped[..., 3:4].astype(np.float32) / 255 * al
                canvas += (warped[..., :3].astype(np.float32) - canvas) * a
            if al > 0.003 and self.mp.get("show_ring", True):
                ring = self.scr(self.mp["ring"], c, u).astype(np.int32)
                glow = np.zeros((H, W), np.uint8)
                cv2.polylines(glow, [ring], True, 255, 18, cv2.LINE_AA)
                glow = cv2.GaussianBlur(glow, (0, 0), 9).astype(np.float32)[..., None] / 255 * 0.55 * al
                canvas += (np.array([90, 215, 255], np.float32) - canvas) * glow
                edge = np.zeros((H, W), np.uint8)
                cv2.polylines(edge, [ring], True, 255, 4, cv2.LINE_AA)
                e = edge.astype(np.float32)[..., None] / 255 * al
                canvas += (np.array([120, 230, 255], np.float32) - canvas) * e

        # viền vùng đối tượng (hồ, khu đất lớn): vàng phát sáng + phủ nhẹ — rõ ở mở đầu, nhạt dần về sau
        vg = p["project"].get("vung")
        if vg:
            a_v = fade(t, 0.35, 0.5) * (1 - 0.55 * fade(t, p["camera"][1]["t0"] if len(p["camera"]) > 1 else 2.0, 1.0))
            ring = self.scr(np.array(vg), c, u).astype(np.int32)
            fill = np.zeros((H, W), np.uint8)
            cv2.fillPoly(fill, [ring], 255, cv2.LINE_AA)
            # có lớp màu quy hoạch thì KHÔNG phủ vàng trong ranh (ám vàng làm màu loại đất nhạt, khó đọc — 10/11/2026)
            fk = 0.0 if (self.mp is not None and not self.mp.get("show_ring", True)) else 0.14
            fa = fill.astype(np.float32)[..., None] / 255 * fk * a_v
            canvas += (np.array([60, 200, 255], np.float32) - canvas) * fa
            glow = np.zeros((H, W), np.uint8)
            cv2.polylines(glow, [ring], True, 255, 16, cv2.LINE_AA)
            ga = cv2.GaussianBlur(glow, (0, 0), 8).astype(np.float32)[..., None] / 255 * 0.5 * a_v
            canvas += (np.array([90, 215, 255], np.float32) - canvas) * ga
            edge = np.zeros((H, W), np.uint8)
            cv2.polylines(edge, [ring], True, 255, 4, cv2.LINE_AA)
            ea = edge.astype(np.float32)[..., None] / 255 * a_v
            canvas += (np.array([120, 230, 255], np.float32) - canvas) * ea

        # KHOANH VÙNG điểm dạng cụm / quần thể (xã, cụm CN — user 10/11/2026): phủ màu tuyến + quầng + viền, hiện khi line
        # chạm mép vùng, đậm trong chương của nó, nhạt bớt sau đó (vẫn giữ để khung kết thấy đủ)
        for z in p.get("zones", []):
            a_z = fade(t, z["t_in"], 0.6)
            if a_z <= 0.003:
                continue
            emph = 1 - 0.5 * fade(t, z["t_dim"], 0.6)
            ring = self.scr(np.array(z["ring"]), c, u)
            ri = np.round(ring * 4).astype(np.int32)
            b_, g_, r_ = hexbgr(z["color"])
            col = np.array([b_, g_, r_], np.float32)
            fill = np.zeros((H, W), np.uint8)
            cv2.fillPoly(fill, [ri], 255, cv2.LINE_AA, 2)
            canvas += (col - canvas) * (fill.astype(np.float32)[..., None] / 255 * 0.26 * a_z * emph)
            glow = np.zeros((H, W), np.uint8)
            cv2.polylines(glow, [ri], True, 255, 18, cv2.LINE_AA, 2)
            ga = cv2.GaussianBlur(glow, (0, 0), 9).astype(np.float32)[..., None] / 255 * 0.75 * a_z * emph
            canvas += (col - canvas) * ga
            edge = np.zeros((H, W), np.uint8)
            cv2.polylines(edge, [ri], True, 255, 5, cv2.LINE_AA, 2)
            canvas += (np.minimum(col + 70, 255) - canvas) * (edge.astype(np.float32)[..., None] / 255 * 0.95 * a_z)

        # spotlight
        PMs = self.scr(self.PM, c, u)
        km_labels = []
        for ch in p["chapters"]:
            if not ch["spot"] or t < ch["t_spot"]:
                continue
            t_off = p["outro"]["t_move"]
            vis = window(t, ch["t_spot"], t_off, 0.35, 0.45)
            if vis <= 0.003:
                continue
            ts = np.array([x[0] for x in ch["spot_r"]]); rs = np.array([x[1] for x in ch["spot_r"]])
            r_now = float(np.interp(t, ts, rs)) * back_out((t - ch["t_spot"]) / C.SPOT_GROW, 1.2)
            R = max(1.0, r_now / u)
            mask = np.zeros((H, W), np.uint8)
            cv2.circle(mask, (int(PMs[0]), int(PMs[1])), int(R), 255, -1, cv2.LINE_AA)
            mask = cv2.GaussianBlur(mask, (0, 0), 2.0).astype(np.float32)[..., None] / 255
            dim = 1 - (1 - C.SPOT_DIM) * vis
            canvas *= (mask + (1 - mask) * dim)
            ov = np.zeros((H, W), np.uint8)
            cv2.circle(ov, (int(PMs[0]), int(PMs[1])), int(R), 255, 3, cv2.LINE_AA)
            for rg in ch["rings"] or []:
                av = fade(t, rg["t"], 0.35) * vis
                if av <= 0.003:
                    continue
                Rr = rg["r"] / u
                n = max(24, int(2 * math.pi * Rr / 26))
                ring_l = np.zeros((H, W), np.uint8)
                for i in range(n):                     # nét đứt ĐỨNG YÊN: pha cố định theo góc
                    a0 = 2 * math.pi * i / n
                    a1 = a0 + math.pi / n * 1.1
                    pts = np.array([[PMs[0] + Rr * math.cos(a), PMs[1] + Rr * math.sin(a)] for a in np.linspace(a0, a1, 4)], np.int32)
                    cv2.polylines(ring_l, [pts], False, 255, 2, cv2.LINE_AA)
                rl = ring_l.astype(np.float32)[..., None] / 255 * 0.75 * av
                canvas += (255 - canvas) * rl
                ang = math.radians(rg.get("ang", 28))  # góc do plan.py chọn (ít đè nét/ghim/thẻ nhất)
                kx, ky = PMs[0] + Rr * math.cos(ang), PMs[1] + Rr * math.sin(ang)
                km_labels.append((kx, ky, f"{rg['km']} km", av))
            o = ov.astype(np.float32)[..., None] / 255 * 0.92 * vis
            canvas += (255 - canvas) * o


        # nét tuyến
        shadow = np.zeros((H, W), np.uint8)
        lines = []
        for h in p["heads"]:
            if t < h["t0"] or self.routes[h["route"]].get("an_net"):     # vùng giáp ranh: không vẽ line
                continue
            e = self.PL.ease_draw((t - h["t0"]) / (h["t1"] - h["t0"]))
            s_now = h["s0"] + (h["s1"] - h["s0"]) * e
            if abs(s_now - h["s0"]) < 1:
                continue
            pts = self.route_pts(h["route"], h["s0"], s_now, c, u)
            lines.append((h["route"], pts))
            cv2.polylines(shadow, [pts.astype(np.int32)], False, 255, C.LINE_W + C.LINE_SHADOW, cv2.LINE_AA)
        if lines:
            sh = cv2.GaussianBlur(shadow, (0, 0), 5).astype(np.float32)[..., None] / 255 * 0.42
            canvas *= (1 - sh)
            # "line sáng" (user 10/11/2026): quầng màu tuyến tỏa quanh nét — 2 lớp mờ (rộng nhạt + hẹp đậm), cộng sáng lên nền
            gl = [(key, pts) for key, pts in lines if self.routes[key].get("glow")]
            if gl:
                halo = np.zeros((H, W, 3), np.float32)
                for width, sigma, gain in C.GLOW_LAYERS:
                    lay_g = np.zeros((H, W, 3), np.uint8)
                    for key, pts in gl:
                        b, g, r = hexbgr(self.routes[key]["color"])
                        cv2.polylines(lay_g, [np.round(pts * 4).astype(np.int32)], False, (b, g, r), width, cv2.LINE_AA, 2)
                    halo += cv2.GaussianBlur(lay_g, (0, 0), sigma).astype(np.float32) * gain
                canvas += halo * (1 - canvas / 300.0).clip(0.15, 1)
            lay = np.zeros((H, W, 4), np.uint8)
            for key, pts in lines:
                cv2.polylines(lay, [np.round(pts * 4).astype(np.int32)], False, (255, 255, 255, 235), C.LINE_W + 2 * C.LINE_EDGE, cv2.LINE_AA, 2)
            for key, pts in lines:
                b, g, r = hexbgr(self.routes[key]["color"])
                cv2.polylines(lay, [np.round(pts * 4).astype(np.int32)], False, (b, g, r, 255), C.LINE_W, cv2.LINE_AA, 2)
            a = lay[..., 3:4].astype(np.float32) / 255
            canvas += (lay[..., :3].astype(np.float32) - canvas) * a

        for kx, ky, txt, av in km_labels:                # nhãn km nằm TRÊN nét tuyến
            if C.SAFE_X0 + 55 < kx < C.SAFE_X1 - 55 and C.SAFE_Y0 + 20 < ky < C.SAFE_Y1 - 20:
                put(canvas, SP.km_label(txt), kx, ky, av)

        # ghim điểm (sau khi bật thì giữ tới hết; khung kết ẩn ghim chồng nhau)
        outro_t = p["outro"]["t"]
        for q in p["pois"]:
            if q["t"] is None or t < q["t"]:
                continue
            col = self.routes[q["route"]]["color"]
            s = self.scr(q["m"], c, u)
            k_ = back_out((t - q["t"]) / C.LABEL_POP)
            ah = 1 - fade(t, p["outro"]["t_move"], 0.5) if q.get("outro_hide") else 1.0
            for a0, a1 in q.get("hide", []):              # ghim cũ chồng ghim chương mới → mờ đi trong chương đó
                ah *= 1 - window(t, a0, a1, 0.45, 0.45)
            if ah <= 0.003:
                continue
            put(canvas, SP.dot(col), s[0], s[1], ah, max(0.01, k_))
            put(canvas, SP.pin(q["kind"] if q["kind"] != "diem" else "diem", col), s[0], s[1], min(1, (t - q["t"]) / 0.12) * ah, max(0.01, k_))

        # huy hiệu phương tiện
        for h in p["heads"]:
            if t < h["t_pop"] or t > h["t1"] + 0.5 or self.routes[h["route"]].get("an_net"):
                continue
            e = self.PL.ease_draw((t - h["t0"]) / (h["t1"] - h["t0"])) if t >= h["t0"] else 0.0
            r = self.routes[h["route"]]
            s_now = h["s0"] + (h["s1"] - h["s0"]) * e
            q = self.scr(geo.point_at(r["P"], r["L"], s_now), c, u)
            k_ = back_out((t - h["t_pop"]) / 0.32)
            a = 1 - fade(t, h["t1"] + 0.05, 0.4)
            dx = min(q[0] - 0, W - q[0]); dy = min(q[1] - 0, H - q[1])
            a *= smooth((min(dx, dy) - 20) / (C.ICON_EDGE - 20))     # gần mép thì mờ dần, không kẹt nửa người
            hop = 5 * abs(math.sin(2 * math.pi * 2.4 * t)) if h["t0"] < t < h["t1"] else 0.0
            put(canvas, SP.icon_badge(h["icon"], r["color"]), q[0], q[1] - 6 - hop, a, max(0.01, k_))

        # ghim + thẻ dự án — vẽ SAU icon phương tiện: icon bật ra từ sau thẻ, không đè chữ tên dự án (Matrix One 17/10)
        put(canvas, self.pin, PMs[0], PMs[1])
        sw = p["project"]["switch_u"]
        wmini = smooth((u - sw * 0.94) / (sw * 0.12))    # dải hoà hẹp; plan.py giữ mọi khung đứng yên ngoài dải
        card_a = fade(t, 0.3, 0.2)
        side = p["project"].get("card_side", "tren")
        put(canvas, self.card_full, *self.PL.card_anchor(PMs, self.card_full, side), card_a * (1 - wmini))
        put(canvas, self.card_mini, *self.PL.card_anchor(PMs, self.card_mini, side), card_a * wmini)

        # nhãn tuyến
        for lr in p["route_labels"]:
            ch = p["chapters"][lr["chapter"]]
            a = window(t, lr["t"], ch["t_end"], 0.3, 0.3)
            if a <= 0.003:
                continue
            r = self.routes[lr["route"]]
            q = self.scr(geo.point_at(r["P"], r["L"], lr["s"]), c, u) + np.array(lr["off"])
            put(canvas, SP.route_label(lr["text"], r["color"], lr.get("sub")), q[0], q[1], a, 0.85 + 0.15 * back_out((t - lr["t"]) / 0.3))

        # nhãn điểm: đầy đủ trong chương, rút gọn ở khung kết
        for q in p["pois"]:
            if q["t"] is None:
                continue
            ch = p["chapters"][q["chapter"]]
            col = self.routes[q["route"]]["color"]
            s = self.scr(q["m"], c, u)
            t_full_end = q.get("t_collapse")
            t_full_end = ch["t_end"] if t_full_end is None else t_full_end
            tl = q.get("t_label") or q["t"]                 # nhãn có thể hiện trễ hơn ghim (chờ nhãn cũ nhường)
            a = window(t, tl, t_full_end, C.LABEL_POP, 0.3)
            head = (s[0], s[1] - 50)                       # đầu ghim (giọt nước cao 74 px)
            if a > 0.003 and q["off"]:
                k_ = 0.7 + 0.3 * back_out((t - tl) / C.LABEL_POP)
                sp_ = SP.poi_label(tuple(q["lines"]), col, q["sub"], False, q.get("scale", 1.0))
                leader(canvas, sp_, s[0] + q["off"][0], s[1] + q["off"][1], head, a, k_)
                put(canvas, sp_, s[0] + q["off"][0], s[1] + q["off"][1], a, k_)
            if q.get("off_short"):
                a3 = window(t, t_full_end + 0.3, ch["t_end"], 0.3, 0.3)
                if a3 > 0.003:
                    sp_ = SP.poi_label(tuple(q["short"]), col, None, True)
                    leader(canvas, sp_, s[0] + q["off_short"][0], s[1] + q["off_short"][1], head, a3)
                    put(canvas, sp_, s[0] + q["off_short"][0], s[1] + q["off_short"][1], a3)
            if q.get("final") and t >= outro_t:
                a2 = fade(t, outro_t + 0.1, 0.35)
                f = q["final"]
                sp_ = SP.poi_label(tuple(f["lines"]), col, None, True)
                leader(canvas, sp_, s[0] + f["off"][0], s[1] + f["off"][1], head, a2)
                put(canvas, sp_, s[0] + f["off"][0], s[1] + f["off"][1], a2)

        # chữ chương
        for ch in p["chapters"]:
            a = window(t, ch["t_title"], ch["t_end"], C.CHAPTER_IN, C.CHAPTER_OUT)
            if a > 0.003:
                put(canvas, SP.chapter_title(ch["title"]), ch["pos"][0], ch["pos"][1] + 18 * (1 - a), a)

        # bìa
        cv_ = p.get("cover")
        if cv_ and t < cv_["t1"]:
            a = 1 - fade(t, cv_["t1"] - C.COVER_FADE, C.COVER_FADE)
            put(canvas, SP.cover(tuple(cv_["lines"]), cv_.get("sub")), W / 2, C.SAFE_Y0 + 300, a)

        # chú giải
        lt = p["outro"]["legend_t"]
        if t >= lt:
            a = fade(t, lt, C.LEGEND_IN)
            lg = SP.legend(tuple(tuple(x) for x in p["outro"]["legend_items"]))
            put(canvas, lg, W / 2, p["outro"]["legend_y"] - 24 * (1 - a), a)

        # khung kết
        ec = p.get("end_card")
        if ec and t >= ec["t"]:
            a = fade(t, ec["t"], 0.4)
            put(canvas, SP.end_card(ec["line1"], ec.get("line2")), W / 2, C.H * 0.70, a, 0.9 + 0.1 * back_out((t - ec["t"]) / 0.4))

        # watermark
        if p.get("watermark"):
            put(canvas, SP.chapter_title(p["watermark"]), W / 2, C.SAFE_Y1 - 30, 0.55, 0.55)
        return np.clip(canvas, 0, 255).astype(np.uint8)


# ================================================================== tải trước tile
def needed_tiles(plan):
    cam = Camera(plan)
    T = plan["meta"]["duration"]
    need = set()
    for t in np.arange(0, T + 1e-6, 1 / FPS):
        c, u = cam(t)
        for z, w in levels_for(u):
            xs, ys = tiles_for(c, u, z)
            for x in xs:
                for y in ys:
                    if 0 <= x < 2 ** z and 0 <= y < 2 ** z:
                        need.add((z, x, y))
    return need


def prefetch(plan, workers=8):
    import concurrent.futures as cf
    need = needed_tiles(plan)
    miss = [n for n in need if not os.path.exists(os.path.join(geo.TILE_CACHE, f"{n[0]}_{n[1]}_{n[2]}.jpg"))]
    print(f"● Tile cần: {len(need)}, chưa có: {len(miss)}")
    t0 = time.time()
    with cf.ThreadPoolExecutor(workers) as ex:
        list(ex.map(lambda n: geo.fetch_tile(*n), miss))
    print(f"  tải xong sau {time.time() - t0:.0f} s")


# ================================================================== xuất
def ffmpeg_writer(path):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p", "-c:v", "libx264", "-preset", "medium",
           "-crf", "17", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-r", str(FPS), path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def render_range(plan, f0, f1, path):
    sc = Scene(plan)
    pr = ffmpeg_writer(path)
    t0 = time.time()
    for f in range(f0, f1):
        pr.stdin.write(sc.frame(f / FPS).tobytes())
        if (f - f0) % 150 == 0 and f > f0:
            el = time.time() - t0
            print(f"    [{os.path.basename(path)}] {f - f0}/{f1 - f0} khung, {el / (f - f0):.2f} s/khung", flush=True)
    pr.stdin.close(); pr.wait()
    return path


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out")
    ap.add_argument("--frames")
    ap.add_argument("--outdir")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--prefetch", action="store_true")
    ap.add_argument("--range", help="f0,f1 (nội bộ: tiến trình con)")
    a = ap.parse_args()
    plan = geo.load_json(a.plan)
    if a.prefetch:
        prefetch(plan); return
    if a.frames:
        os.makedirs(a.outdir, exist_ok=True)
        sc = Scene(plan)
        for tt in a.frames.split(","):
            t = float(tt)
            cv2.imwrite(os.path.join(a.outdir, f"f_{t:06.2f}.png"), sc.frame(t))
            print(f"  ✓ khung {t:.2f} s")
        return
    if a.range:
        f0, f1 = map(int, a.range.split(","))
        render_range(plan, f0, f1, a.out); return
    # chia đoạn cho nhiều tiến trình rồi nối
    prefetch(plan)
    N = int(round(plan["meta"]["duration"] * FPS))
    k = a.workers
    cuts = np.linspace(0, N, k + 1).astype(int)
    work = os.path.dirname(os.path.abspath(a.out))
    segs, procs = [], []
    t0 = time.time()
    for i in range(k):
        sp = os.path.join(work, f"_seg{i:02d}.mp4")
        segs.append(sp)
        procs.append(subprocess.Popen([sys.executable, os.path.abspath(__file__), "--plan", a.plan, "--out", sp,
                                       "--range", f"{cuts[i]},{cuts[i + 1]}"]))
    for pr in procs:
        pr.wait()
        if pr.returncode != 0:
            raise SystemExit("⛔ một tiến trình dựng lỗi")
    lst = os.path.join(work, "_segs.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for sp in segs:
            f.write(f"file '{sp.replace(os.sep, '/')}'\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-r", str(FPS), a.out], check=True)
    for sp in segs:
        os.remove(sp)
    os.remove(lst)
    print(f"● Dựng xong {N} khung sau {time.time() - t0:.0f} s → {a.out}")


if __name__ == "__main__":
    main()
