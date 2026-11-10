"""Khảo sát hạ tầng quanh MỘT ĐỊA ĐIỂM BẤT KỲ (tên hoặc toạ độ) → hồ sơ du_an.json nháp cho run.py.

  python khao_sat.py --ten "Lăng Bác" --out <thư mục>/du_an.json [--vi_tri lat,lon] [--kieu du_an|dia_danh]

1. Tìm địa điểm: Photon (chỉ mục OSM) khoanh Việt Nam, bỏ đường/nhà lẻ/cửa hàng → chấm điểm ứng viên. Ứng viên chỉ là thứ lặt
   vặt (vd cửa hàng "… - Vincom Landmark 81") thì lấy làm MỐC rồi chọn công trình nổi bật nhất quanh mốc 250 m (wikidata,
   chiều cao, diện tích) — OSM đặt tên toà Landmark 81 là "Vincom Center".
2. Lấy hình khối (ranh khu đất / mặt hồ) → "vung"; tâm = điểm trong vùng gần trọng tâm.
3. Khảo sát hạ tầng ĐANG VẬN HÀNH (user chốt 17/10/2026 — đang xây/chạy thử/quy hoạch thì bỏ):
   metro (ray subway/light_rail/monorail + ga NẰM TRÊN ray đó — ga của tuyến quy hoạch cũng hay gắn railway=stop),
   trục lớn (vành đai / đại lộ / cao tốc / xa lộ / quốc lộ), phố mặt tiền, cầu lớn qua sông (≥ 450 m), sân bay có mã IATA
   (≤ 40 km, chấm ở nhà ga), tiện ích nổi bật (wikidata / TTTM / bệnh viện / đại học / SVĐ / công viên / hồ / bến xe).
4. Xếp chương: Ngay cửa nhà|Ngay sát bên · Vành đai & trục lớn · Metro đang chạy · Tiện ích · Cầu & sân bay (spotlight);
   ≤ 4 điểm có nhãn mỗi chương; hai điểm cách nhau < 180 m chỉ giữ một (ghim chồng).
5. Ghi du_an.json + khao_sat.json (mọi ứng viên, kể cả cái bị loại và lý do) để Claude/user sửa ở cổng duyệt.
"""
import argparse, hashlib, json, math, os, re, sys, unicodedata
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import geo

UA = {"User-Agent": "SonAIVideo-bandoht/1.0"}
VN_BBOX = "102.1,8.2,109.6,23.5"
ALIAS = {                                   # cách gọi quen ↔ tên trong OSM (chỉ để TÌM, tên in ra vẫn là chữ user gõ)
    "lăng bác": ["Lăng Chủ tịch Hồ Chí Minh"], "hồ gươm": ["Hồ Hoàn Kiếm"], "bờ hồ": ["Hồ Hoàn Kiếm"],
    "nhà thờ lớn": ["Nhà thờ Lớn Hà Nội"], "keangnam": ["Keangnam Hanoi Landmark Tower"], "landmark 72": ["Keangnam"],
    "bitexco": ["Bitexco Financial Tower"], "chợ bến thành": ["Chợ Bến Thành"], "nhà thờ đức bà": ["Nhà thờ Đức Bà"],
    "phố đi bộ nguyễn huệ": ["Phố đi bộ Nguyễn Huệ"], "landmark 81": ["Landmark 81", "Vincom Landmark 81"],
}
DROP_WORDS = re.compile(r"quy hoạch|dự kiến|dự án|đang xây|đang thi công|\(cũ\)|giai đoạn 2", re.I)
NOT_OPERATING_TAGS = ("construction", "proposed", "disused", "abandoned", "razed", "demolished", "planned")


def cen(e):
    """tâm phần tử Overpass: center (out center) → giữa bounds (out bb — Overpass chỉ giữ 1 cờ hình học) → toạ độ node."""
    if e.get("center"):
        return e["center"]
    b = e.get("bounds")
    if b:
        return {"lat": (b["minlat"] + b["maxlat"]) / 2, "lon": (b["minlon"] + b["maxlon"]) / 2}
    return {"lat": e.get("lat"), "lon": e.get("lon")}


def norm(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn").replace("đ", "d")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def norm_dau(s):
    """hạ chữ, GIỮ DẤU (so tên tiếng Việt: "Đà Nẵng" ≠ "Đa Năng" — bỏ dấu thì khớp nhầm nhà thi đấu Đa Năng, 18/10)."""
    s = unicodedata.normalize("NFC", (s or "").lower())
    return re.sub(r"\s+", " ", re.sub(r"[^\w ]", " ", s)).strip()


TIEN_TO_HC = re.compile(r"^(thành phố|tỉnh|tp|quận|huyện|thị xã|phường|xã)\s+", re.I)
TIEN_TO_TEN = re.compile(r"^(tòa nhà|toà nhà|tòa|toà|dự án|công trình)\s+", re.I)


def tach_ten(raw):
    """«Tòa nhà The Matrix One . Số 1 Lê Quang Đạo, Hà Nội» → ('The Matrix One', toàn câu làm ngữ cảnh lọc vị trí).
    Phần trước dấu phẩy / dấu chấm đứng riêng là TÊN; phần sau là địa chỉ — chỉ dùng chấm điểm vị trí, không gửi Photon."""
    parts = [x.strip() for x in re.split(r"[,;]|\s\.\s|\s-\s|\s–\s", raw) if x.strip()]
    ten = TIEN_TO_TEN.sub("", parts[0] if parts else raw.strip()).strip() or raw.strip()
    return ten, raw


def pretty(s):
    """viết hoa chữ đầu mỗi từ nếu user gõ toàn chữ thường."""
    s = s.strip()
    return " ".join(w[:1].upper() + w[1:] for w in s.split()) if s == s.lower() else s


class Cache:
    def __init__(self, work):
        self.dir = os.path.join(work, "osm", "khao_sat")
        os.makedirs(self.dir, exist_ok=True)

    def overpass(self, q):
        key = hashlib.md5(q.encode("utf-8")).hexdigest()[:14]
        p = os.path.join(self.dir, key + ".json")
        if os.path.exists(p):
            return geo.load_json(p)
        d = geo.overpass(q)
        geo.save_json(p, d)
        return d

    def photon(self, q, loose=False):
        import requests
        key = ("phl_" if loose else "ph_") + hashlib.md5(q.encode("utf-8")).hexdigest()[:12]
        p = os.path.join(self.dir, key + ".json")
        if os.path.exists(p):
            return geo.load_json(p)
        params = [("q", q), ("limit", 10), ("bbox", VN_BBOX)]
        if not loose:
            params += [("osm_tag", "!highway"), ("osm_tag", "!place:house"), ("osm_tag", "!shop"),
                       ("osm_tag", "!amenity:restaurant"), ("osm_tag", "!amenity:cafe")]
        try:
            r = requests.get("https://photon.komoot.io/api/", params=params, headers=UA, timeout=25)
            d = r.json() if r.status_code == 200 else {"features": []}
        except Exception as e:
            print(f"  ⚠ Photon lỗi: {e}")
            d = {"features": []}
        geo.save_json(p, d)
        return d


# ================================================================== hình học
def ring_area_m2(ring_ll):
    if len(ring_ll) < 3:
        return 0.0
    P = geo.lls2m(ring_ll)
    k = geo.scale_k(float(np.mean([p[0] for p in ring_ll])))
    x, y = P[:, 0], P[:, 1]
    return abs(0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)) / (k * k)


def inside(pt, ring):
    x, y = pt
    c = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]; x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-15) + x1:
            c = not c
    return c


def seg_dist(P, A, B):
    """khoảng cách từ các điểm P (N×2) tới đoạn thẳng A-B (mảng)."""
    AB = B - A
    t = np.clip(((P - A) @ AB) / (AB @ AB + 1e-12), 0, 1)
    return np.linalg.norm(P - (A + t[:, None] * AB), axis=1)


def poly_dist_m(pt_m, ring_m, k):
    """khoảng cách (m thật) từ điểm tới ranh vùng; 0 nếu ở trong."""
    if inside(pt_m, ring_m):
        return 0.0
    P = np.asarray([pt_m], float)
    d = min(float(seg_dist(P, ring_m[i], ring_m[(i + 1) % len(ring_m)])[0]) for i in range(len(ring_m)))
    return d / k


def element_rings(e):
    """các vòng ngoài (list [lat,lon]) của way / relation (out geom)."""
    if e["type"] == "way" and "geometry" in e:
        g = [(p["lat"], p["lon"]) for p in e["geometry"]]
        return [g] if len(g) >= 4 and geo.haversine(g[0], g[-1]) < 30 else []
    if e["type"] == "relation":
        outer = [[(p["lat"], p["lon"]) for p in m["geometry"]] for m in e.get("members", [])
                 if m.get("type") == "way" and m.get("role") in ("outer", "") and "geometry" in m]
        rings = [c for c in geo.chain_ways(outer, tol=5) if len(c) >= 4 and geo.haversine(c[0], c[-1]) < 60]
        return rings
    return []


def simplify(ring, n=260):
    if len(ring) <= n:
        return ring
    step = len(ring) / n
    return [ring[int(i * step)] for i in range(n)]


def interior_point(ring_ll):
    """điểm trong vùng gần trọng tâm nhất (hồ cong, trọng tâm có thể rơi ra ngoài)."""
    M = geo.lls2m(ring_ll)
    c = M.mean(0)
    if inside(c, M):
        return geo.m2ll(*c)
    x0, y0 = M.min(0); x1, y1 = M.max(0)
    best = None
    for gx in np.linspace(x0, x1, 40):
        for gy in np.linspace(y0, y1, 40):
            p = np.array([gx, gy])
            if inside(p, M):
                d = float(np.linalg.norm(p - c)) - 0.5 * min(float(seg_dist(np.array([p]), M[i], M[(i + 1) % len(M)])[0]) for i in range(0, len(M), max(1, len(M) // 60)))
                if best is None or d < best[0]:
                    best = (d, p)
    return geo.m2ll(*(best[1] if best else c))


# ================================================================== 1. tìm địa điểm
CAT_W = {("military", None): -4, ("natural", "water"): 4, ("water", "lake"): 4, ("water", "reservoir"): 3, ("historic", None): 4, ("tourism", "attraction"): 4,
         ("tourism", "museum"): 4, ("building", None): 2, ("leisure", "stadium"): 4, ("leisure", "park"): 3, ("landuse", "residential"): 2,
         ("man_made", "bridge"): 3, ("bridge", None): 2, ("amenity", "university"): 2, ("amenity", "hospital"): 2, ("place", "quarter"): 1,
         ("amenity", "place_of_worship"): 1, ("boundary", None): -5, ("place", "suburb"): -3, ("place", "village"): -3, ("place", "town"): -2,
         ("place", "city"): -2, ("waterway", None): -3, ("office", None): -2, ("amenity", None): -1, ("landuse", "construction"): -6}


def cat_weight(key, val):
    if (key, val) in CAT_W:
        return CAT_W[(key, val)]
    return CAT_W.get((key, None), 0)


def locate(name, cache, vi_tri=None, ngu_canh=""):
    """name = tên công trình; ngu_canh = toàn câu user gõ (có thể kèm địa chỉ/thành phố) — dùng để chấm điểm vị trí."""
    rows = []
    if vi_tri:
        lat, lon = vi_tri
        print(f"● Toạ độ cho sẵn {lat:.6f}, {lon:.6f} — tìm công trình tại chỗ")
        return notable_near((lat, lon), name, cache, radius=120) or dict(name=name, lat=lat, lon=lon, osm=None, tags={}, how="toạ độ tay")
    ngu_canh = ngu_canh or name
    q_tok = set(norm_dau(ngu_canh).split())
    q_dau = f" {norm_dau(ngu_canh)} "
    queries = [name] + ([ngu_canh] if norm(ngu_canh) != norm(name) and len(ngu_canh.split()) <= 8 else []) \
        + ALIAS.get(name.lower().strip(), [])
    best_of = {}
    feats = [(qi, q, cache.photon(q).get("features", [])) for qi, q in enumerate(queries)]
    if not any(f_ for _, _, f_ in feats):          # lọc chặt không ra gì (Landmark 81 chỉ khớp tên cửa hàng) → tìm thả lỏng lấy MỐC
        feats = [(qi, q, cache.photon(q, loose=True).get("features", [])) for qi, q in enumerate(queries)]
    for qi, q, fs in feats:
        for rank, f in enumerate(fs):
            p = f["properties"]
            key = (p.get("osm_type"), p.get("osm_id"))
            nm = p.get("name") or ""
            nn = norm(nm)
            # điểm tên: so với MỌI cách gọi (tên user gõ + bí danh), lấy cao nhất — "Lăng Bác" khớp đúng "Lăng Chủ tịch Hồ Chí Minh"
            ms = 0.0
            for q2 in queries:
                qn = norm(q2)
                if qn and nn == qn:
                    ms = max(ms, 6)
                elif qn and qn in nn:
                    ms = max(ms, 3 + (1 if nn.startswith(qn) else 0) - 0.08 * max(0, len(nn) - len(qn)))   # tên dài thừa chữ → trừ
            # tên ứng viên nằm TRỌN trong câu gõ (giữ dấu): "Chợ Hàn" ⊂ "Chợ Hàn Đà Nẵng" — trước đây khớp nguyên cụm mới có điểm
            nt = norm_dau(nm).split()
            if nt:
                hit = sum(w in q_tok for w in nt) / len(nt)
                ms = max(ms, 4 + min(2.0, len(nt) / 2) if hit == 1 else 2 * hit if hit >= 0.5 else 0)
            # đúng thành phố / tỉnh / quận user gõ kèm ("… Đà Nẵng", "…, Hà Nội")
            vt_bonus = 0
            for k_ in ("city", "county", "district", "state", "locality"):
                c_ = norm_dau(TIEN_TO_HC.sub("", p.get(k_) or ""))
                if c_ and f" {c_} " in q_dau:
                    vt_bonus = 3
            ms += vt_bonus
            sc = 3 - 0.45 * rank - 0.5 * qi + ms + cat_weight(p.get("osm_key"), p.get("osm_value")) + (1 if p.get("extent") else 0)
            if key in best_of and best_of[key]["score"] >= sc:
                continue
            lon, lat = f["geometry"]["coordinates"]
            best_of[key] = dict(score=round(sc, 2), name=nm, osm=key, key=p.get("osm_key"), val=p.get("osm_value"),
                                city=p.get("city") or p.get("state"), lat=lat, lon=lon, minor=not p.get("extent"))
    rows = sorted(best_of.values(), key=lambda r: -r["score"])
    print("● Ứng viên địa điểm (Photon/OSM):")
    for r in rows[:6]:
        print(f"   {r['score']:5.1f}  {r['name']}  [{r['key']}={r['val']}]  {r['city']}  {r['lat']:.5f},{r['lon']:.5f}")
    if not rows:
        return None, rows
    best = rows[0]
    if best["minor"] or best["score"] < 4 or best["key"] in ("shop", "amenity", "office"):
        print("  … ứng viên tốt nhất chỉ là điểm lặt vặt → lấy làm MỐC, tìm công trình nổi bật quanh 250 m")
        nb = notable_near((best["lat"], best["lon"]), name, cache, radius=250, ten_moc=best["name"])
        if nb:
            return nb, rows
    t = {"W": "way", "R": "relation", "N": "node"}.get(best["osm"][0], "node")
    return dict(name=best["name"], lat=best["lat"], lon=best["lon"], osm=(t, best["osm"][1]), tags={best["key"]: best["val"]},
                how=f"Photon: {best['name']}"), rows


def notable_near(ll, name, cache, radius=250, ten_moc=None):
    lat, lon = ll
    q = (f'[out:json][timeout:90];(way["building"](around:{radius},{lat},{lon});relation["building"](around:{radius},{lat},{lon});'
         f'nwr["wikidata"](around:{radius},{lat},{lon});nwr["tourism"~"attraction|museum"](around:{radius},{lat},{lon});'
         f'nwr["historic"](around:{radius},{lat},{lon});way["natural"="water"](around:{radius},{lat},{lon}););out center bb;')
    d = cache.overpass(q)
    best = None
    for e in d.get("elements", []):
        t = e.get("tags", {})
        if any(t.get(x) for x in ("highway", "railway", "boundary", "route", "place")):
            continue
        c = cen(e)
        if c.get("lat") is None:
            continue
        h = 0.0
        try:
            h = float(str(t.get("height", "0")).split()[0])
        except Exception:
            pass
        lv = 0.0
        try:
            lv = float(t.get("building:levels", 0))
        except Exception:
            pass
        b = e.get("bounds")
        area = 0.0
        if b:
            area = geo.haversine((b["minlat"], b["minlon"]), (b["minlat"], b["maxlon"])) * geo.haversine((b["minlat"], b["minlon"]), (b["maxlat"], b["minlon"]))
        nm = t.get("name", "")
        sc = (4 if t.get("wikidata") else 0) + min(5, max(h / 60, lv / 12)) + min(2, math.log10(max(area, 1) / 2000 + 1))
        sc += 3 if norm(name) and norm(name) in norm(nm) else 0
        # công trình mang đúng tên mốc vừa khớp (Chợ Hàn là chợ — đừng đổi sang khách sạn cao tầng bên cạnh)
        sc += 6 if ten_moc and norm(ten_moc) and norm(ten_moc) == norm(nm) else 0
        sc -= geo.haversine(ll, (c["lat"], c["lon"])) / 150
        if best is None or sc > best[0]:
            best = (sc, e, nm, c)
    if best is None:
        return None
    _, e, nm, c = best
    print(f"  ✓ công trình nổi bật quanh mốc: «{nm or '(không tên)'}» ({e['type']} {e['id']}, điểm {best[0]:.1f})")
    return dict(name=nm or name, lat=c["lat"], lon=c["lon"], osm=(e["type"], e["id"]), tags=e.get("tags", {}), how=f"quanh mốc: {nm}")


def subject_geometry(loc, cache):
    if not loc.get("osm") or loc["osm"][0] == "node":
        return None, 0.0, loc.get("tags", {})
    t, i = loc["osm"]
    d = cache.overpass(f"[out:json][timeout:120];{t}({i});out geom tags;")
    els = d.get("elements", [])
    if not els:
        return None, 0.0, loc.get("tags", {})
    rings = element_rings(els[0])
    if not rings:
        return None, 0.0, els[0].get("tags", {})
    ring = max(rings, key=ring_area_m2)
    return ring, ring_area_m2(ring), els[0].get("tags", {})


def admin_line(ll, cache):
    lat, lon = ll
    d = cache.overpass(f'[out:json][timeout:60];is_in({lat},{lon})->.a;area.a["boundary"="administrative"]["name"];out tags;')
    lv = {}
    for e in d.get("elements", []):
        t = e.get("tags", {})
        try:
            lv.setdefault(int(t.get("admin_level", 0)), t["name"])
        except Exception:
            pass
    ward = next((lv[x] for x in (8, 7, 6) if x in lv), None)
    city = lv.get(4)
    if city:
        city = re.sub(r"^(Thành phố|Tỉnh)\s+", "", city)
    return " · ".join(x for x in (ward, city) if x) or None


# ================================================================== 3. khảo sát
def not_operating(tags):
    if any(tags.get(x) for x in NOT_OPERATING_TAGS):
        return True
    if any(tags.get(x) in NOT_OPERATING_TAGS for x in ("railway", "highway", "building", "landuse", "amenity", "shop")):
        return True
    return bool(DROP_WORDS.search(tags.get("name", "")))


def lines_of(elements):
    out = {}
    for e in elements:
        if e.get("type") != "way" or "geometry" not in e:
            continue
        out.setdefault(e["tags"].get("name", ""), []).append([(p["lat"], p["lon"]) for p in e["geometry"]])
    return out


def dense(ways_ll, step_m=40):
    pts = []
    for w in ways_ll:
        P = geo.lls2m(w)
        if len(P) >= 2:
            pts.append(geo.resample(P, step_m * geo.scale_k(w[0][0])))
    return np.vstack(pts) if pts else np.zeros((0, 2))


def survey_metro(S, cache, dropped):
    lat, lon = S["ll"]
    d = cache.overpass(f'[out:json][timeout:180];way["railway"~"^(subway|light_rail|monorail)$"](around:6500,{lat},{lon});out geom tags;')
    groups = {}
    for nm, ws in lines_of(d.get("elements", [])).items():
        if not nm or re.search(r"[Dd]epot|chạy thử|[Nn]hánh|ra vào|kho|xưởng", nm):
            continue
        groups[nm] = ws
    res = []
    for nm, ws in groups.items():
        # toàn tuyến (không chỉ trong bán kính) + ga nằm trên ray đó — hai đầu tuyến lấy đúng (2A: Cát Linh – Yên Nghĩa)
        qn = nm.replace("\\", "\\\\").replace('"', '\\"')
        full = cache.overpass(f'[out:json][timeout:180];way["name"="{qn}"]["railway"~"^(subway|light_rail|monorail)$"]->.l;'
                              f'.l out geom tags;(node(around.l:90)["railway"~"^(station|stop|halt)$"]["name"];'
                              f'node(around.l:90)["public_transport"="station"]["name"];);out body;')
        ws_full = [[(p_["lat"], p_["lon"]) for p_ in e["geometry"]] for e in full.get("elements", []) if e.get("type") == "way" and "geometry" in e] or ws
        stations = [e for e in full.get("elements", []) if e.get("type") == "node" and not not_operating(e.get("tags", {}))]
        D = dense(ws)
        if len(D) < 2:
            continue
        L = sum(geo.geolen(w) for w in ws) / 1000
        dmin = min(S["dist_m"](p) for p in D[::3]) / 1000
        if L < 2 or dmin > 4.5:
            continue
        on = {}
        from scipy.spatial import cKDTree
        DF = dense(ws_full)
        tr = cKDTree(DF)
        for e in stations:
            m = geo.ll2m(e["lat"], e["lon"])
            if tr.query(m)[0] / S["k"] <= 90:
                n_ = re.sub(r"^\s*[Gg]a\s+", "", e["tags"]["name"]).strip()
                if n_ and n_ not in on:
                    on[n_] = (e["lat"], e["lon"])
        if not on:
            dropped.append(f"metro «{nm}»: không thấy ga nào nằm trên ray đang chạy — bỏ")
            continue
        # hai đầu tuyến = cặp ga XA NHAU NHẤT (ray OSM hay đứt thành nhiều chuỗi — chiếu lên chuỗi dài nhất cho ra sai đầu)
        names_ = list(on)
        ends = (names_[0], names_[0])
        best_d = -1
        for i_ in range(len(names_)):
            for j_ in range(i_ + 1, len(names_)):
                dd_ = geo.haversine(on[names_[i_]], on[names_[j_]])
                if dd_ > best_d:
                    best_d, ends = dd_, (names_[i_], names_[j_])
        ends = sorted(ends, key=lambda n_: -S["dist_m"](geo.ll2m(*on[n_])))   # ga xa đối tượng hơn đứng trước
        near = min(on, key=lambda n_: S["dist_m"](geo.ll2m(*on[n_])))
        num = re.search(r"(?:số|sô|Số|[Tt]uyến|đô thị|[Ll]ine|[Mm]etro)\s*(\d+[A-Za-z]?)", nm)
        num = num.group(1).upper() if num else None
        res.append(dict(name=nm, num=num, dmin=dmin, ends=(ends[0], ends[1]), near=near, near_ll=on[near],
                        near_d=S["dist_m"](geo.ll2m(*on[near])) / 1000))
    res.sort(key=lambda r: r["dmin"])
    return res[:3]


BIG = re.compile(r"[Vv]ành [đĐ]ai|[Đđ]ại lộ|[Cc]ao tốc|[Xx]a lộ|[Qq]uốc lộ")


def canon_road(nm):
    m = re.search(r"[Vv]ành [đĐ]ai\s*([\d]+(?:[.,]\d)?)", nm)
    if m:
        return "Vành đai " + m.group(1).replace(",", ".")
    m = re.search(r"[Qq]uốc lộ\s*(\d+[A-Z]?)", nm)
    if m:
        return "Quốc lộ " + m.group(1)
    m = re.search(r"([Đđ]ại lộ|[Xx]a lộ)\s+([^(,;]+)", nm)
    if m:
        return (m.group(1)[0].upper() + m.group(1)[1:]) + " " + m.group(2).strip()
    m = re.search(r"[Cc]ao tốc\s+([^(;]+)", nm)
    if m:
        return "Cao tốc " + re.sub(r"\s+TP\..*$", "", m.group(1)).strip()
    return nm


def survey_roads(S, cache, dropped):
    lat, lon = S["ll"]
    R = int(4200 + S["radius_m"])
    d = cache.overpass(f'[out:json][timeout:180];way["highway"~"^(motorway|trunk|primary)$"]["name"](around:{R},{lat},{lon});out geom tags;')
    big, other = {}, {}
    for e in d.get("elements", []):
        t = e.get("tags", {})
        nm = t.get("name", "")
        if not nm or "geometry" not in e or not_operating(t) or re.search(r"[Cc]ầu vượt|[Hh]ầm|[Ll]ối|^Đi |[Hh]ướng|[Nn]út giao|[Dd]ẫn", nm):
            continue
        w = [(p["lat"], p["lon"]) for p in e["geometry"]]
        (big if BIG.search(nm) else other).setdefault(canon_road(nm) if BIG.search(nm) else nm, {"names": set(), "ways": []})
        g = (big if BIG.search(nm) else other)[canon_road(nm) if BIG.search(nm) else nm]
        g["names"].add(nm); g["ways"].append(w)
    out = []
    for key, g in list(big.items()) + list(other.items()):
        D = dense(g["ways"])
        if len(D) < 2:
            continue
        L = sum(geo.geolen(w) for w in g["ways"]) / 1000
        # đoạn LIỀN dài nhất vẽ được (OSM hay chỉ gắn tên "Vành đai 1" cho vài khúc rời → nét cụt ngủn, Lăng Bác 17/10)
        Lc = max(geo.geolen(c) for c in geo.chain_ways(g["ways"], tol=250)) / 1000
        dmin = min(S["dist_m"](p) for p in D[::2]) / 1000
        out.append(dict(key=key, names=sorted(g["names"]), big=key in big, L=L, Lc=Lc, dmin=dmin, D=D))
    for r in out:
        if r["big"] and r["Lc"] < 2.5 and r["dmin"] <= 4.0:
            dropped.append(f"trục «{r['key']}»: đoạn liền dài nhất chỉ {r['Lc']:.1f} km quanh đây — bỏ (nét cụt)")
    bigs = sorted([r for r in out if r["big"] and r["Lc"] >= 2.5 and r["dmin"] <= 4.0], key=lambda r: r["dmin"])[:3]
    if len(bigs) < 2:                                   # không đủ vành đai/đại lộ vẽ liền được → trục chính dài nhất gần đó
        extra = sorted([r for r in out if not r["big"] and r["Lc"] >= 2.5 and r["dmin"] <= 1.5], key=lambda r: (r["dmin"] > 0.6, -r["Lc"]))
        bigs += extra[:2 - len(bigs)]
    return bigs


def survey_front(S, cache):
    lat, lon = S["ll"]
    R = int(350 + S["radius_m"])
    d = cache.overpass(f'[out:json][timeout:90];way["highway"~"^(trunk|primary|secondary|tertiary)$"]["name"](around:{R},{lat},{lon});out geom tags;')
    best = None
    for nm, ws in lines_of([e for e in d.get("elements", []) if not not_operating(e.get("tags", {}))]).items():
        if not nm or re.search(r"[Cc]ầu vượt|[Hh]ầm|[Ll]ối|^Đi ", nm):
            continue
        D = dense(ws, 20)
        if len(D) < 2:
            continue
        dm = min(S["dist_m"](p) for p in D)
        if best is None or dm < best[0]:
            best = (dm, nm)
    return best[1] if best else None


def survey_bridges(S, cache):
    lat, lon = S["ll"]
    d = cache.overpass(f'[out:json][timeout:180];way["bridge"]["highway"~"^(motorway|trunk|primary|secondary)$"]["name"~"^Cầu "]'
                       f'(around:16000,{lat},{lon});out geom tags;')
    res = []
    for nm, ws in lines_of([e for e in d.get("elements", []) if not not_operating(e.get("tags", {}))]).items():
        if re.search(r"vượt|[Cc]ạn|dẫn|[Hh]ầm|[Nn]út|làn xe máy|\(", nm):
            continue
        ch = geo.chain_ways(ws, tol=60)
        c = max(ch, key=geo.geolen)
        L = geo.geolen(c)
        if L < 450:
            continue
        a, b = c[0], c[-1]
        da, db = S["dist_m"](geo.ll2m(*a)), S["dist_m"](geo.ll2m(*b))
        near, far = (a, b) if da <= db else (b, a)
        mid = geo.m2ll(*geo.point_at(geo.lls2m(c), geo.cumlen(geo.lls2m(c)), geo.cumlen(geo.lls2m(c))[-1] / 2))
        res.append(dict(name=nm, L=L, near=near, far=far, mid=mid, d=min(da, db) / 1000))
    res.sort(key=lambda r: r["d"])
    out, used = [], []
    for r in res:                                      # 2 cầu khác hẳn nhau (không phải 2 nhánh/2 làn của 1 cầu)
        if r["d"] > 15 or any(geo.haversine(r["mid"], u) < 1500 for u in used):
            continue
        out.append(r); used.append(r["mid"])
        if len(out) == 2:
            break
    return out


def survey_airport(S, cache):
    lat, lon = S["ll"]
    d = cache.overpass(f'[out:json][timeout:120];nwr["aeroway"="aerodrome"]["iata"](around:45000,{lat},{lon});out center;')
    best = None
    for e in d.get("elements", []):
        t = e.get("tags", {})
        if not_operating(t) or t.get("military") or t.get("landuse") == "military":
            continue
        c = cen(e)
        dist = geo.haversine((lat, lon), (c["lat"], c["lon"])) / 1000
        sc = dist - (8 if re.search(r"[Qq]uốc tế|International", t.get("name", "") + t.get("name:en", "")) else 0)
        if dist <= 40 and (best is None or sc < best[0]):
            best = (sc, e, c, dist)
    if not best:
        return None
    _, e, c, dist = best
    tq = cache.overpass(f'[out:json][timeout:90];nwr["aeroway"="terminal"](around:4500,{c["lat"]},{c["lon"]});out center bb;')
    term = None
    for x in tq.get("elements", []):
        t = x.get("tags", {})
        if not_operating(t):
            continue
        cc = cen(x)
        b = x.get("bounds") or {}
        area = (b.get("maxlat", 0) - b.get("minlat", 0)) * (b.get("maxlon", 0) - b.get("minlon", 0))
        sc = area * 1e6 + (50 if re.search(r"[Qq]uốc tế|International|T2", t.get("name", "")) else 0)
        if term is None or sc > term[0]:
            term = (sc, t.get("name", ""), (cc["lat"], cc["lon"]))
    t = e.get("tags", {})
    ll_ = term[2] if term else (c["lat"], c["lon"])
    # khoảng cách tới đúng chỗ CẮM GHIM (nhà ga), không tới tâm sân bay — bảng khảo sát từng ghi 4,0 km trong khi nhãn 2,6 km (Chợ Hàn)
    return dict(name=t.get("name", "Sân bay"), iata=t.get("iata"), ll=ll_, terminal=term[1] if term else None,
                d=geo.haversine((lat, lon), ll_) / 1000)


POI_W = [(("tourism", "attraction"), 5), (("tourism", "museum"), 5), (("tourism", "zoo"), 4), (("tourism", "theme_park"), 4),
         (("historic", "*"), 4), (("leisure", "stadium"), 5), (("shop", "mall"), 4), (("amenity", "hospital"), 3),
         (("amenity", "university"), 3), (("amenity", "bus_station"), 3), (("natural", "water"), 2), (("leisure", "park"), 1),
         (("amenity", "place_of_worship"), 1), (("historic", "temple"), 4), (("amenity", "conference_centre"), 4), (("amenity", "exhibition_centre"), 4),
         (("building", "commercial"), 1), (("building", "office"), 1)]
POI_BAD = re.compile(r"embassy|diplomatic|government|police|school|kindergarten|parking|fuel|bank|atm|toilets|clinic|pharmacy|civic|townhall|courthouse|prison|military")
POI_BAD_NAME = re.compile(r"^(Phòng [Kk]hám|Nha khoa|Trụ sở|Ủy ban|Uỷ ban|UBND|Sở |Bộ |Cục |Tòa án|Toà án|Viện kiểm sát|Công an|Đại sứ|Lãnh sự|Khách sạn|Kho |Bãi )", re.I)
WATER_OK = ("lake", "reservoir", "pond", "lagoon", "basin")


def poi_kind(t):
    if t.get("leisure") == "stadium":
        return "svd"
    if t.get("shop") == "mall":
        return "tttm"
    if t.get("amenity") == "hospital":
        return "benh_vien"
    if t.get("amenity") == "university":
        return "dai_hoc"
    if t.get("amenity") == "bus_station":
        return "ben_xe"
    if t.get("natural") == "water":
        return "ho"
    if t.get("leisure") == "park":
        return "cong_vien"
    if t.get("tourism") or t.get("historic"):
        return "di_tich"
    return "khac"


def survey_pois(S, cache, dropped):
    lat, lon = S["ll"]
    R = int(3500 + S["radius_m"])
    q = (f'[out:json][timeout:180];(nwr["wikidata"]["name"](around:{R},{lat},{lon});nwr["shop"="mall"]["name"](around:{R},{lat},{lon});'
         f'nwr["leisure"~"^(stadium|park)$"]["name"](around:{R},{lat},{lon});'
         f'nwr["amenity"~"^(hospital|university|bus_station|conference_centre|exhibition_centre)$"]["name"](around:{R},{lat},{lon});'
         f'nwr["tourism"~"^(attraction|museum|zoo|theme_park)$"]["name"](around:{R},{lat},{lon});'
         f'way["natural"="water"]["name"](around:{R},{lat},{lon});relation["natural"="water"]["name"](around:{R},{lat},{lon}););out center bb;')
    d = cache.overpass(q)
    cands = []
    for e in d.get("elements", []):
        t = e.get("tags", {})
        nm = t.get("name", "")
        if not nm or any(t.get(x) for x in ("highway", "railway", "route", "boundary", "place", "waterway", "public_transport", "power", "aeroway")):
            continue
        if not_operating(t):
            dropped.append(f"điểm «{nm}»: chưa vận hành / đang xây — bỏ")
            continue
        if POI_BAD.search(" ".join(f"{k}={v}" for k, v in t.items() if k in ("amenity", "office", "building", "landuse", "healthcare"))) or POI_BAD_NAME.search(nm):
            continue
        if t.get("natural") == "water" and t.get("water") not in WATER_OK and not re.match(r"^(Hồ|Đầm)", nm):
            continue                                    # sông, kênh, rạch không phải "tiện ích" (Rạch Văn Thánh, Kênh Thị Nghè)
        if S["osm"] and (e["type"], e["id"]) == tuple(S["osm"]):
            continue
        c = cen(e)
        if c.get("lat") is None:
            continue
        b = e.get("bounds")
        area = 0.0
        if b:
            area = geo.haversine((b["minlat"], b["minlon"]), (b["minlat"], b["maxlon"])) * geo.haversine((b["minlat"], b["minlon"]), (b["maxlat"], b["minlon"]))
        w = 0
        for (k_, v_), ww in POI_W:
            if t.get(k_) and (v_ == "*" or t.get(k_) == v_):
                w = max(w, ww)
        kind = poi_kind(t)
        if kind == "ho" and area < 8e4:
            continue
        if kind == "cong_vien" and area < 5e4:
            continue
        if w == 0 and not t.get("wikidata"):
            continue
        dist = S["dist_m"](geo.ll2m(c["lat"], c["lon"])) / 1000
        water_subj = S.get("water")
        if b and kind in ("ho", "cong_vien", "svd", "tttm", "benh_vien", "dai_hoc"):
            cl = (min(max(S["ll"][0], b["minlat"]), b["maxlat"]), min(max(S["ll"][1], b["minlon"]), b["maxlon"]))
            dist = min(dist, S["dist_m"](geo.ll2m(*cl)) / 1000)
        if not water_subj and (dist < 0.12 or (S["ring_m"] is not None and inside(geo.ll2m(c["lat"], c["lon"]), S["ring_m"]))):
            continue                                       # chính là đối tượng / một phần của nó
        if water_subj and t.get("natural") == "water":
            continue                                       # hồ khác dính liền (Trúc Bạch) — giữ, trừ khi là chính mặt nước
        if water_subj and dist < 0.15:
            sc_bonus_shore = 4.0                           # chùa/đền trên bán đảo, ven bờ — chính là thứ đáng xem của hồ
        else:
            sc_bonus_shore = 0.0
        if S["name_n"] and S["name_n"] in norm(nm):
            continue
        areal = (any(t.get(x) for x in ("natural", "leisure", "landuse", "historic", "building")) or t.get("amenity") in ("university", "hospital")
                 or t.get("tourism") in ("zoo", "theme_park"))
        if t.get("amenity") == "place_of_worship" and t.get("wikidata"):
            w = max(w, 3)                                  # chùa/đền/nhà thờ có wikidata là điểm tham quan thật (Chùa Trấn Quốc)
        sc = w + (2 if t.get("wikidata") else 0) + (min(2.0, math.log10(area / 1e4)) if (area > 1e4 and areal) else 0) - 0.9 * dist
        if kind in ("ho", "cong_vien") and area > 3e5:
            sc += 1.5
        sc += sc_bonus_shore
        cands.append(dict(name=nm, kind=kind, ll=(c["lat"], c["lon"]), d=dist, score=round(sc, 2), osm=(e["type"], e["id"]), area=area))
    cands.sort(key=lambda r: -r["score"])
    out = []
    for c in cands:
        if any(geo.haversine(c["ll"], o["ll"]) < 180 or norm(c["name"]) == norm(o["name"]) for o in out):
            dropped.append(f"điểm «{c['name']}»: trùng chỗ / trùng tên với «{next(o['name'] for o in out if geo.haversine(c['ll'], o['ll']) < 180 or norm(c['name']) == norm(o['name']))}» (ghim chồng) — bỏ")
            continue
        out.append(c)
        if len(out) >= 8:
            break
    # ghim tại điểm ranh gần đối tượng khảo sát nhất (hồ lớn, công viên: ghim bên bờ, không giữa hồ)
    ids = [o for o in out if o["osm"][0] in ("way", "relation") and o["area"] > 3e4]
    if ids:
        ws = ",".join(str(o["osm"][1]) for o in ids if o["osm"][0] == "way")
        rs = ",".join(str(o["osm"][1]) for o in ids if o["osm"][0] == "relation")
        q2 = "[out:json][timeout:120];(" + (f"way(id:{ws});" if ws else "") + (f"relation(id:{rs});" if rs else "") + ");out geom;"
        g = cache.overpass(q2)
        geoms = {(e["type"], e["id"]): element_rings(e) for e in g.get("elements", [])}
        for o in ids:
            rings = geoms.get(o["osm"])
            if rings:
                ring = max(rings, key=len)
                M = geo.lls2m(ring)
                dd = [S["dist_m"](m) for m in M[:: max(1, len(M) // 200)]]
                j = int(np.argmin(dd)) * max(1, len(M) // 200)
                o["ll"] = tuple(ring[j])
                o["d"] = float(min(dd)) / 1000
                o["_M"] = geo.resample(np.asarray(M, float), 20 * S["k"]) if len(M) >= 2 else np.asarray(M, float)
    # lọc trùng LẦN 2 theo ghim CUỐI: ghim công trình dài vừa dời về mép gần nhất có thể rơi sát điểm khác, và điểm nằm ngay
    # TRÊN công trình đã chọn là một phần của nó (Cầu Rồng dời về đầu cầu → cách "Dragon's Tail" 44 m; "Dragon's Head" nằm trên
    # chính cây cầu — Chợ Hàn 18/10)
    final = []
    for c in out:
        cm = np.asarray(geo.ll2m(*c["ll"]), float)
        clash = next((o for o in final if geo.haversine(c["ll"], o["ll"]) < 180), None)
        if clash is None:
            clash = next((o for o in final if o.get("_M") is not None and len(o["_M"])
                          and float(np.min(np.linalg.norm(o["_M"] - cm, axis=1))) / S["k"] < 80), None)
        if clash is not None:
            dropped.append(f"điểm «{c['name']}»: trùng chỗ / nằm trên «{clash['name']}» (sau khi đặt ghim) — bỏ")
            continue
        final.append(c)
    for o in final:
        o.pop("_M", None)
    return final


# ================================================================== 4. xếp chương
SHORT = [(r"^Khu du lịch\s+", "KDL "), (r"^Khu vui chơi\s+", "KVC "), (r"^Sân vận động\s+", "SVĐ "), (r"^Trung tâm thương mại\s+", "TTTM "), (r"^Bệnh viện\s+", "BV "),
         (r"^Trường Đại học\s+|^Đại học\s+", "ĐH "), (r"^Sân bay Quốc tế\s+|^Cảng hàng không quốc tế\s+", "SB "),
         (r"^Trung tâm Hội nghị\s+", "TT Hội nghị "), (r"\s+(Quốc gia|Hà Nội|Việt Nam|Thành phố Hồ Chí Minh)$", ""),
         (r"\s+Quốc gia\s+", " ")]


def short_name(nm, maxlen=18):
    """rút gọn tên cho nhãn ngắn: viết tắt loại (SVĐ, TTTM, BV, ĐH, SB), bỏ đuôi địa danh; còn dài thì GIỮ CÁC TỪ ĐẦU
    ("Hoàng thành Thăng Long" → "HOÀNG THÀNH", không bao giờ cắt từ đầu thành "THÀNH THĂNG LONG")."""
    s = nm
    for a, b in SHORT:
        s = re.sub(a, b, s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > maxlen:
        w = s.split()
        while len(" ".join(w)) > maxlen and len(w) > 2:
            w = w[:-2] if len(w) >= 4 else w[:-1]        # tiếng Việt hay ghép 2 âm tiết → bỏ theo CẶP từ cuối
        s = " ".join(w)
    return s.upper()


LOC_TAIL = re.compile(r"\s+(Thành phố Hồ Chí Minh|TP\.? ?HCM|Hà Nội|Việt Nam|Sài Gòn)$")


# ngắt dòng nhãn: ưu tiên ngay sau DANH TỪ ĐẦU tên, không tách TỪ GHÉP ("BẢO TÀNG MỸ / THUẬT ĐÀ NẴNG" — Chợ Hàn 18/10)
LABEL_HEADS = ("SÂN VẬN ĐỘNG", "TRUNG TÂM THƯƠNG MẠI", "TRUNG TÂM", "BẢO TÀNG", "TRƯỜNG ĐẠI HỌC", "ĐẠI HỌC", "BỆNH VIỆN",
               "CÔNG VIÊN", "NHÀ THỜ", "NHÀ HÁT", "KHU DU LỊCH", "KHU ĐÔ THỊ", "QUẢNG TRƯỜNG", "SÂN BAY", "BẾN XE", "TÒA NHÀ",
               "CHỢ", "CẦU", "CHÙA", "ĐỀN", "LĂNG", "HỒ", "GA", "CUNG", "KHU")
LABEL_PAIRS = {tuple(x.split()) for x in (
    "MỸ THUẬT", "NGHỆ THUẬT", "LỊCH SỬ", "QUỐC GIA", "QUỐC TẾ", "HỘI NGHỊ", "HỮU NGHỊ", "THƯƠNG MẠI", "THỂ THAO", "VĂN HÓA",
    "VĂN HOÁ", "ĐIÊU KHẮC", "DU LỊCH", "GIẢI TRÍ", "TRIỂN LÃM", "KHOA HỌC", "BÁCH KHOA", "SƯ PHẠM", "KINH TẾ", "ĐA KHOA",
    "NHI ĐỒNG", "THÀNH PHỐ", "VIỆT NAM", "VIỆT TRUNG", "HÀ NỘI", "ĐÀ NẴNG", "SÀI GÒN", "HẢI PHÒNG", "CẦN THƠ", "NHA TRANG",
    "ĐÀ LẠT", "VŨNG TÀU", "MỸ ĐÌNH", "HÒA BÌNH", "THĂNG LONG", "TRUNG ƯƠNG", "QUÂN ĐỘI", "CÔNG NGHỆ", "Y DƯỢC")}


def label_lines(nm, maxc=18):
    nm = LOC_TAIL.sub("", nm)                          # "Bảo tàng Lịch sử Thành phố Hồ Chí Minh" → "Bảo tàng Lịch sử"
    s = nm.upper()
    if len(s) <= maxc:
        return s
    w = s.split()
    best = None
    for i in range(1, len(w)):
        a, b = " ".join(w[:i]), " ".join(w[i:])
        sc = max(len(a), len(b))
        if a in LABEL_HEADS:
            sc -= 5                                    # "BẢO TÀNG / MỸ THUẬT ĐÀ NẴNG", "SÂN VẬN ĐỘNG / QUỐC GIA MỸ ĐÌNH"
        if (w[i - 1], w[i]) in LABEL_PAIRS:
            sc += 8                                    # đừng tách "MỸ / THUẬT", "QUỐC / GIA", "ĐÀ / NẴNG"
        if best is None or sc < best[0]:
            best = (sc, [a, b])
    return best[1]


PALETTE = ["#FFB800", "#CC75FF", "#1E90FF", "#12B5A8", "#FE3A5A", "#2FC85E", "#FF7A1A", "#E040FB", "#00BCD4", "#8BC34A"]


def build_brief(name, kieu, S, metros, roads, front, bridges, airport, pois, dropped):
    used_col = []

    def col(prefer=None):
        for c_ in ([prefer] if prefer else []) + PALETTE:
            if c_ and c_ not in used_col:
                used_col.append(c_)
                return c_
        return PALETTE[len(used_col) % len(PALETTE)]

    tuyen, chuong = {}, []
    used_poi = set()
    # cầu / sân bay đã có chương riêng ("Cầu & sân bay") → không lấy lại làm tiện ích ở chương trước
    # (Cầu Sông Hàn hiện 2 lần: điểm trên đường Lê Duẩn + cầu ở chương cuối — Chợ Hàn 18/10)
    reserved = {norm(b["name"]) for b in bridges} | ({norm(airport["name"])} if airport else set())
    for p in pois:
        if norm(p["name"]) in reserved or any(geo.haversine(p["ll"], b["mid"]) < 300 for b in bridges):
            used_poi.add(p["name"])

    def poi_entry(p, loai="diem", uu=1):
        used_poi.add(p["name"])
        e = dict(ten=label_lines(p["name"]), ten_ngan=short_name(p["name"]), loai=loai, latlon=[round(p["ll"][0], 6), round(p["ll"][1], 6)], uu_tien=uu)
        if S.get("water") and p["d"] < 0.15:
            e["phu"] = "ngay bên hồ"
        elif p["d"] < 0.15:
            e["phu"] = "ngay bên cạnh"
        return e

    def road_entry(r, ve_km):
        return dict(ten=r["key"], nhan=r["key"].upper(), loai="duong", mau=col(),
                    nguon={"osm_ten": r["names"], "loai": "highway", "ban_kinh_km": 14}, huong="both", ve_km=ve_km, diem=[])

    # ---- C0 (đối tượng là HỒ): vòng ven hồ — icon chạy hết bờ, các điểm ven bờ / trên bán đảo bật dọc đường
    if S.get("water") and S["ring"]:
        shore = [p for p in pois if p["d"] < 0.15][:4]
        R = list(S["ring"])
        i0 = int(np.argmin([S["dist_m"](geo.ll2m(*q)) * 0 + geo.haversine(S["ll"], q) for q in R]))
        R = R[i0:] + R[:i0 + 1]
        per = geo.geolen(R) / 1000
        tuyen["ven"] = dict(ten="Vòng ven hồ", nhan=None, loai="duong", mau=col("#FFD24A"), chu_giai=False,
                            nguon={"latlon": [[round(a_, 6), round(b_, 6)] for a_, b_ in R]}, huong="cuoi", ve_km=round(per, 2),
                            diem=[poi_entry(p, uu=3) for p in shore])
        if shore:
            chuong.append({"ten": "Ven hồ", "tuyen": ["ven"]})
        else:
            tuyen.pop("ven")

    # ---- C1: ngay sát bên — trục lớn gần nhất (≤ 1,5 km) hoặc phố mặt tiền + đường đi tới tiện ích gần nhất
    c1 = []
    has_ven = "ven" in tuyen
    near_road = roads[0] if (roads and roads[0]["dmin"] <= 1.5 and not has_ven) else None   # hồ: "Ven hồ" thay cho chương 1
    if near_road:
        tuyen["r0"] = road_entry(near_road, 2.4); c1.append("r0")
    elif front and not has_ven:
        tuyen["front"] = dict(ten=front, nhan=re.sub(r"^(Đường|Phố)\s+", "", front).upper(), loai="duong", mau=col(),
                              nguon={"osm_ten": [front], "loai": "highway", "ban_kinh_km": 6}, huong="both", ve_km=1.6, diem=[])
        c1.append("front")
    close = [p for p in pois if p["name"] not in used_poi and 0.15 <= p["d"] <= 1.0] or             [p for p in pois if p["name"] not in used_poi and 0.15 <= p["d"] <= 2.0]
    if close and not has_ven:
        p = close[0]
        tuyen["p0"] = dict(ten=f"{short_name(p['name']).title()} – đường đi", loai="duong", mau=col("#FE3A5A"), chu_giai=False,
                           nguon={"duong_di": {"den": [p["ll"][0], p["ll"][1]], "hang": "tertiary"}}, diem=[poi_entry(p, uu=3)])
        tuyen["p0"]["ten"] = "Tới " + p["name"]
        c1.append("p0")
    if c1:
        chuong.append({"ten": "Ngay cửa nhà" if kieu == "du_an" else "Ngay sát bên", "tuyen": c1})

    # ---- C2: vành đai & trục lớn (trừ trục đã dùng ở C1) + tiện ích nằm sát trục đó
    c2 = []
    for i, r in enumerate([r for r in roads if r is not near_road][:2]):
        key = f"r{i + 1}"
        e = road_entry(r, 3.2)
        from scipy.spatial import cKDTree
        tr = cKDTree(r["D"])
        for p in pois:
            if p["name"] in used_poi or len(e["diem"]) >= 2:
                continue
            if tr.query(geo.ll2m(*p["ll"]))[0] / S["k"] <= 450:
                e["diem"].append(poi_entry(p))
        tuyen[key] = e; c2.append(key)
    if c2:
        chuong.append({"ten": "Vành đai & trục lớn" if any(BIG.search(tuyen[k]["ten"]) for k in c2) else "Trục đường lớn", "tuyen": c2})

    # ---- C3: metro đang chạy
    c3 = []
    mcol = ["#1E90FF", "#12B5A8", "#E040FB"]
    for i, m in enumerate(metros):
        key = f"m{i}"
        lab = f"TUYẾN {m['num']}" if m["num"] else "METRO"
        sub = f"{m['ends'][0]} – {m['ends'][1]}"
        tuyen[key] = dict(ten=f"Metro {m['num'] or ''} ({sub})".replace("  ", " "), nhan=lab, nhan_phu=sub, loai="metro", mau=col(mcol[i % 3]),
                          nguon={"osm_ten": [m["name"]], "loai": "railway", "ban_kinh_km": 14}, huong="both", ve_km=2.2,
                          diem=[dict(ten=label_lines("Ga " + m["near"]), ten_ngan=("GA " + short_name(m["near"], 12)), loai="ga",
                                     latlon=[round(m["near_ll"][0], 6), round(m["near_ll"][1], 6)], uu_tien=2)])
        c3.append(key)
    if c3:
        chuong.append({"ten": "Metro đang chạy", "tuyen": c3})

    # ---- C4: tiện ích (đường đi thật tới 2 điểm nổi bật còn lại)
    c4 = []
    rest = [p for p in pois if p["name"] not in used_poi and p["d"] >= 0.15][:2]
    for i, p in enumerate(rest):
        key = f"p{i + 1}"
        tuyen[key] = dict(ten="Tới " + p["name"], loai="duong", mau=col("#2FC85E" if i == 0 else None), chu_giai=False,
                          nguon={"duong_di": {"den": [p["ll"][0], p["ll"][1]], "hang": "tertiary"}}, diem=[poi_entry(p, uu=2)])
        c4.append(key)
    if c4:
        kinds = {p["kind"] for p in rest}
        chuong.append({"ten": "Trung tâm thương mại" if kinds == {"tttm"} else "Tiện ích quanh đây", "tuyen": c4})

    # ---- C5: cầu & sân bay (spotlight)
    c5 = []
    for i, b in enumerate(bridges):
        key = f"b{i}"
        tuyen[key] = dict(ten="Đường ra " + b["name"][0].lower() + b["name"][1:], loai="duong", mau=col("#FF7A1A" if i == 0 else None),
                          nguon={"duong_di": {"qua": [list(b["near"])], "den": list(b["far"]), "hang": "primary"}},
                          diem=[dict(ten=label_lines(b["name"]), ten_ngan=short_name(b["name"]), loai="cau",
                                     latlon=[round(b["mid"][0], 6), round(b["mid"][1], 6)], uu_tien=2)])
        c5.append(key)
    if airport:
        nm = airport["name"]
        sb = re.sub(r"^(Sân bay [Qq]uốc tế|Sân bay|Cảng [Hh]àng không [Qq]uốc tế|Cảng [Hh]àng không)\s+", "", nm)
        tuyen["sb"] = dict(ten="Đường ra SB " + sb, loai="sanbay", mau="#E9EEF5",
                           nguon={"duong_di": {"den": list(airport["ll"]), "hang": "primary"}},
                           diem=[dict(ten=["SÂN BAY", sb.upper()], ten_ngan="SB " + sb.upper(), loai="sanbay",
                                      latlon=[round(airport["ll"][0], 6), round(airport["ll"][1], 6)], uu_tien=2)])
        c5.append("sb")
    if c5:
        chuong.append({"ten": ("Cầu & sân bay" if bridges and airport else "Cầu lớn" if bridges else "Sân bay"), "tuyen": c5, "spotlight": True})

    cats = []
    if roads:
        cats.append("vành đai" if any(BIG.search(r["key"]) and "Vành" in r["key"] for r in roads) else "trục lớn")
    if metros:
        cats.append("metro")
    if bridges:
        cats.append("cầu")
    if airport:
        cats.append("sân bay")
    disp = pretty(name)
    brief = {
        "ten": disp, "vi_tri": [round(S["ll"][0], 6), round(S["ll"][1], 6)], "the_phu": S.get("admin"), "logo": None, "phoi_canh": None,
        "vung": [[round(a, 6), round(b, 6)] for a, b in S["ring"]] if S["ring"] else None,
        "tieu_de": ["HẠ TẦNG GIAO THÔNG", "QUANH " + disp.upper()], "tieu_de_phu": " · ".join(cats) if cats else None,
        "nhac": None, "watermark": None, "khung_ket": None, "chuong": chuong, "tuyen": tuyen,
    }
    return brief


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ten", required=True)
    ap.add_argument("--vi_tri")
    ap.add_argument("--kieu", choices=["auto", "du_an", "dia_danh"], default="auto")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    work = os.path.dirname(os.path.abspath(a.out))
    os.makedirs(work, exist_ok=True)
    cache = Cache(work)
    vt = None
    if a.vi_tri:
        m = re.findall(r"(-?\d+\.\d+)", a.vi_tri)
        vt = (float(m[0]), float(m[1]))
    ten, ngu_canh = tach_ten(a.ten)                     # «Tòa nhà X . Số 1 đường Y, Hà Nội» → tên «X», phần sau chỉ để lọc vị trí
    if ten != a.ten.strip():
        print(f"● Tên công trình: «{ten}» (phần còn lại của câu dùng để lọc vị trí)")
    a.ten = ten
    loc, cands = (locate(a.ten, cache, vt), []) if vt else locate(a.ten, cache, ngu_canh=ngu_canh)
    if isinstance(loc, tuple):
        loc = loc[0]
    if not loc:
        raise SystemExit(f"⛔ Không tìm thấy «{a.ten}» trên bản đồ — cho toạ độ (--vi_tri lat,lon hoặc link Google Maps).")
    nm_loc = (loc.get("name") or "").strip()
    if nm_loc and len(nm_loc) < len(a.ten) and set(norm_dau(nm_loc).split()) <= set(norm_dau(a.ten).split()):
        a.ten = nm_loc                                   # "Chợ Hàn Đà Nẵng" → in "Chợ Hàn" (phần thừa là tên thành phố)
    ring, area, tags = subject_geometry(loc, cache)
    ll = (loc["lat"], loc["lon"])
    if ring and area >= 15000:
        ll = interior_point(ring)
    else:
        ring = None
    k = geo.scale_k(ll[0])
    ring_m = geo.lls2m(simplify(ring)) if ring else None
    S = dict(ll=ll, k=k, ring=simplify(ring) if ring else None, ring_m=ring_m, osm=loc.get("osm"), name_n=norm(loc.get("name", "")),
             radius_m=(math.sqrt(area / math.pi) if ring else 0.0))
    PMm = geo.ll2m(*ll)
    S["dist_m"] = (lambda m, _r=ring_m: poly_dist_m(np.asarray(m, float), _r, k)) if ring_m is not None else (lambda m: float(np.linalg.norm(np.asarray(m, float) - PMm)) / k)
    S["admin"] = admin_line(ll, cache)
    S["water"] = tags.get("natural") == "water" or tags.get("water") in ("lake", "reservoir")
    kieu = a.kieu
    if kieu == "auto":
        res_tag = tags.get("building") in ("apartments", "residential") or tags.get("landuse") == "residential"
        kieu = "du_an" if res_tag or re.search(r"chung cư|khu đô thị|vinhomes|residence|the\s", a.ten, re.I) else "dia_danh"
    print(f"● Địa điểm: «{pretty(a.ten)}» → OSM «{loc.get('name')}» ({loc.get('how')}) @ {ll[0]:.6f}, {ll[1]:.6f}"
          f"{f' · vùng {area / 1e4:.1f} ha' if ring else ''} · {S['admin'] or ''} · kiểu {kieu}")
    dropped = []
    print("● Khảo sát metro đang chạy…"); metros = survey_metro(S, cache, dropped)
    print("● Khảo sát trục lớn…"); roads = survey_roads(S, cache, dropped); front = survey_front(S, cache)
    print("● Khảo sát cầu lớn…"); bridges = survey_bridges(S, cache)
    print("● Khảo sát sân bay…"); airport = survey_airport(S, cache)
    print("● Khảo sát tiện ích nổi bật…"); pois = survey_pois(S, cache, dropped)
    brief = build_brief(a.ten, kieu, S, metros, roads, front, bridges, airport, pois, dropped)
    geo.save_json(a.out, brief)
    rep = dict(dia_diem=dict(ten=a.ten, osm=loc, vung_ha=area / 1e4 if ring else 0, kieu=kieu),
               metro=[{k_: v for k_, v in m.items()} for m in metros], truc=[{k_: v for k_, v in r.items() if k_ != "D"} for r in roads],
               pho_mat_tien=front, cau=bridges, san_bay=airport, tien_ich=pois, bo=dropped)
    geo.save_json(os.path.join(work, "khao_sat.json"), rep)
    print("\n══════════ KẾT QUẢ KHẢO SÁT ══════════")
    print(f"Metro đang chạy: " + (", ".join(f"{m['name']} (ga gần nhất {m['near']} ~{m['near_d']:.1f} km)" for m in metros) or "không có trong 4,5 km"))
    print(f"Trục lớn: " + (", ".join(f"{r['key']} ~{r['dmin']:.1f} km" for r in roads) or "—") + (f" · phố mặt tiền: {front}" if front else ""))
    print(f"Cầu lớn: " + (", ".join(f"{b['name']} ~{b['d']:.1f} km" for b in bridges) or "—"))
    print(f"Sân bay: " + (f"{airport['name']} ({airport['iata']}) ~{airport['d']:.1f} km, chấm ở {airport['terminal'] or 'tâm sân bay'}" if airport else "không có trong 40 km"))
    print(f"Tiện ích: " + (", ".join(f"{p['name']} ~{p['d']:.1f} km" for p in pois) or "—"))
    print("Chương: " + " · ".join(f"{c['ten']} ({len(c['tuyen'])} tuyến)" for c in brief["chuong"]))
    if dropped:
        print("Đã bỏ: " + "; ".join(dropped[:12]) + (" …" if len(dropped) > 12 else ""))
    print(f"● Đã ghi {a.out} (+ khao_sat.json) — Claude soát lại tên/điểm trước khi chạy run.py")


if __name__ == "__main__":
    main()
