"""Hàm địa lý dùng chung: chiếu Web Mercator, tải tile Esri có cache, gọi Overpass, đo khoảng cách, xử lý polyline.

Toạ độ "mét Mercator" (mx, my) với my hướng XUỐNG (giống trục y ảnh) để chiếu ra pixel cho tiện.
"""
import json, math, os, time, concurrent.futures as cf
import numpy as np

R = 6378137.0
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)


def _project_dir(skill):
    """thư mục dự án: <dự án>/.claude/skills/<skill> → <dự án>; skill giải nén ở chỗ khác → thư mục chứa skill."""
    parent = os.path.dirname(skill)
    if os.path.basename(parent) == "skills" and os.path.basename(os.path.dirname(parent)) == ".claude":
        return os.path.dirname(os.path.dirname(parent))
    return parent


PROJECT = _project_dir(SKILL)
# dùng chung giữa các skill bản đồ; skill cài cho mọi dự án (~/.claude/skills) → ~/.cache, không bày ra thư mục người dùng
TILE_CACHE = os.environ.get("NNS_TILE_CACHE") or (
    os.path.join(PROJECT, ".cache", "nns_ban_do", "esri") if os.path.normcase(PROJECT) == os.path.normcase(os.path.expanduser("~"))
    else os.path.join(PROJECT, "_cache_tiles", "esri"))
UA = {"User-Agent": "SonAIVideo-bandoht/1.0"}
ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]


# ------------------------------------------------------------------ chiếu
def ll2m(lat, lon):
    """độ → mét Mercator (y hướng xuống)."""
    return np.array([R * math.radians(lon), -R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))])


def m2ll(mx, my):
    lon = math.degrees(mx / R)
    lat = math.degrees(2 * math.atan(math.exp(-my / R)) - math.pi / 2)
    return lat, lon


def lls2m(pts):
    return np.array([ll2m(a, b) for a, b in pts], float)


def scale_k(lat):
    """1 mét thật = 1/cos(lat) mét Mercator."""
    return 1.0 / math.cos(math.radians(lat))


def haversine(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(min(1.0, h)))


def geolen(pts):
    return sum(haversine(a, b) for a, b in zip(pts, pts[1:]))


def tile_xy(lat, lon, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def tile_m(z):
    """bề rộng 1 tile tính bằng mét Mercator."""
    return 2 * math.pi * R / (2 ** z)


def tile_origin_m(x, y, z):
    s = tile_m(z)
    return np.array([-math.pi * R + x * s, -math.pi * R + y * s])     # góc trên-trái của tile (x, y)


# ------------------------------------------------------------------ tile Esri
def fetch_tile(z, x, y, cache=TILE_CACHE):
    import requests
    os.makedirs(cache, exist_ok=True)
    p = os.path.join(cache, f"{z}_{x}_{y}.jpg")
    if os.path.exists(p) and os.path.getsize(p) > 200:
        return p
    last = None
    for k in range(5):
        try:
            r = requests.get(ESRI.format(z=z, x=x, y=y), headers=UA, timeout=30)
            r.raise_for_status()
            with open(p, "wb") as f:
                f.write(r.content)
            return p
        except Exception as e:                      # mạng chập chờn: thử lại
            last = e
            time.sleep(1.5 * (k + 1))
    raise RuntimeError(f"không tải được tile {z}/{x}/{y}: {last}")


def mosaic(z, lat0, lat1, lon0, lon1, workers=8):
    """ghép ảnh vệ tinh phủ bbox; trả (ảnh BGR uint8, góc trên-trái mét Mercator, mét/pixel Mercator)."""
    import cv2
    x0, y1 = tile_xy(lat0, lon0, z)
    x1, y0 = tile_xy(lat1, lon1, z)
    xs = range(int(x0), int(x1) + 1)
    ys = range(int(y0), int(y1) + 1)
    img = np.zeros((len(ys) * 256, len(xs) * 256, 3), np.uint8)
    jobs = [(x, y) for x in xs for y in ys]
    with cf.ThreadPoolExecutor(workers) as ex:
        for (x, y), p in zip(jobs, ex.map(lambda xy: fetch_tile(z, *xy), jobs)):
            t = cv2.imread(p)
            if t is None:
                continue
            img[(y - ys[0]) * 256:(y - ys[0] + 1) * 256, (x - xs[0]) * 256:(x - xs[0] + 1) * 256] = t[:256, :256]
    return img, tile_origin_m(xs[0], ys[0], z), tile_m(z) / 256


# ------------------------------------------------------------------ Overpass
def overpass(query, retries=8):
    """POST bằng requests (chữ có dấu đi qua curl của Git Bash bị hỏng âm thầm); luân phiên các mirror —
    overpass-api.de hay báo 502 "at capacity", mirror maps.mail.ru thường vẫn chạy (17/10/2026)."""
    import requests
    last = None
    for k in range(retries):
        url = OVERPASS[k % len(OVERPASS)]
        try:
            r = requests.post(url, data={"data": query}, headers=UA, timeout=240)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = e
        time.sleep(2 if k < len(OVERPASS) else 5 * (k + 1))
    raise RuntimeError(f"Overpass lỗi sau {retries} lần: {last}")


def _dir(pts, at_end, n=6):
    """vector hướng (độ) ở đầu/cuối chuỗi, đi RA khỏi chuỗi."""
    a = pts[-1] if at_end else pts[0]
    b = pts[max(0, len(pts) - 1 - n)] if at_end else pts[min(len(pts) - 1, n)]
    v = np.array([a[1] - b[1], a[0] - b[0]], float)
    return v / (np.linalg.norm(v) + 1e-12)


def _uturn(c, s, mode):
    """nối c với s theo mode có làm tuyến QUAY ĐẦU không (đường đôi: 2 làn song song ngược chiều)."""
    out_c = _dir(c, mode[0] == "e")                      # hướng đi ra khỏi c tại chỗ nối
    s_join_end = mode in ("er", "be")                    # chỗ nối nằm ở CUỐI s?
    into_s = -_dir(s, s_join_end)                        # hướng đi vào s tại chỗ nối
    return float(np.dot(out_c, into_s)) < -0.3


def chain_ways(ways, tol=30):
    """nối các way (list điểm [lat,lon]) thành chuỗi liền theo đầu/cuối trùng hoặc gần (≤ tol m)."""
    segs = [list(map(tuple, w)) for w in ways if len(w) >= 2]
    out = []
    while segs:
        c = segs.pop(0)
        grown = True
        while grown:
            grown = False
            best = None
            for i, s in enumerate(segs):
                for mode, d in (("ee", haversine(c[-1], s[0])), ("er", haversine(c[-1], s[-1])),
                                ("be", haversine(c[0], s[-1])), ("br", haversine(c[0], s[0]))):
                    if d <= tol and (best is None or d < best[0]) and not _uturn(c, s, mode):
                        best = (d, i, mode)
            if best:
                _, i, mode = best
                s = segs.pop(i)
                if mode == "ee": c = c + s[1:]
                elif mode == "er": c = c + s[::-1][1:]
                elif mode == "be": c = s + c[1:]
                else: c = s[::-1] + c[1:]
                grown = True
        out.append(c)
    out.sort(key=lambda c: -geolen(c))
    return out


# ------------------------------------------------------------------ polyline (mét Mercator)
def cumlen(P):
    P = np.asarray(P, float)
    return np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])


def resample(P, step):
    P = np.asarray(P, float)
    L = cumlen(P)
    if L[-1] <= 0:
        return P[:1]
    s = np.arange(0, L[-1], step)
    s = np.append(s, L[-1])
    return np.stack([np.interp(s, L, P[:, 0]), np.interp(s, L, P[:, 1])], 1)


def smooth(P, win):
    """làm mượt trung bình trượt, giữ nguyên 2 đầu."""
    P = np.asarray(P, float)
    if len(P) < 3 or win < 2:
        return P
    k = np.ones(win) / win
    pad = np.vstack([np.repeat(P[:1], win, 0), P, np.repeat(P[-1:], win, 0)])
    out = np.stack([np.convolve(pad[:, i], k, "same") for i in range(2)], 1)[win:-win]
    out[0], out[-1] = P[0], P[-1]
    return out


def point_at(P, L, s):
    s = float(np.clip(s, 0, L[-1]))
    return np.array([np.interp(s, L, P[:, 0]), np.interp(s, L, P[:, 1])])


def nearest_on(P, q):
    """điểm gần q nhất trên polyline P: trả (chỉ số đoạn, quãng đường s, điểm, khoảng cách)."""
    P = np.asarray(P, float)
    L = cumlen(P)
    best = (0, 0.0, P[0], 1e18)
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]
        ab = b - a
        t = 0.0 if not ab.any() else float(np.clip(np.dot(q - a, ab) / np.dot(ab, ab), 0, 1))
        p = a + ab * t
        d = float(np.linalg.norm(q - p))
        if d < best[3]:
            best = (i, L[i] + t * np.linalg.norm(ab), p, d)
    return best


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_json(p, d):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
