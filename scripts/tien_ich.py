"""Danh sách tiện ích / điểm công cộng quanh khu quy hoạch → toạ độ thật + khoảng cách tới RANH khu quy hoạch.

  python tien_ich.py --work THU_MUC                       # đọc <work>/tien_ich_vao.json (Claude viết từ lời user)
  python tien_ich.py --work THU_MUC --tu_dong             # + tự khảo sát tiện ích nổi bật quanh khu (gợi ý, KHÔNG tự đưa vào)

<work>/tien_ich_vao.json — mỗi điểm một mục (chỉ "ten" là bắt buộc):
  [{"ten": "Nút giao Vành đai 4 – QL21B",              // tên user gọi
    "nhan": ["NÚT GIAO", "VÀNH ĐAI 4 – QL21B"],        // chữ in trên nhãn (≤ 2 dòng IN HOA; bỏ trống → tự tách)
    "ten_ngan": "NÚT GIAO VĐ4",                        // nhãn thu gọn
    "loai": "nutgiao",                                 // ghim: diem | nutgiao | cau | ga | sanbay | duong (tô cả tuyến
                                                       //   đường theo "osm": regex tên/ref, vd "21B" — ghim ở chỗ gần ranh)
    "dia_chi": "Bình Minh, Thanh Oai, Hà Nội",          // dùng tìm toạ độ khi không có latlon/link
    "latlon": [20.93038, 105.75782],                   // HOẶC "link": "<link Google Maps có @lat,lon>"
    "nguon": "OSM way 595927298 (landuse=industrial)", // (tuỳ) ghi nguồn khi latlon do Claude tra OSM
    "giao": ["[Vv]ành [Đđ]ai 4", "21B"],                // HOẶC tìm giao điểm 2 tuyến OSM (regex tên/ref) gần dia_chi
    "nhom": "Kết nối giao thông",                       // chữ chương (cùng nhóm = cùng chương, ≤ 3 điểm/chương)
    "vung": "relation/19514801",                        // (tuỳ) điểm là CỤM / QUẦN THỂ (xã, phường, cụm / khu CN, khu đô
                                                       //   thị) → KHOANH VÙNG theo ranh OSM, line đi tới MÉP vùng, khoảng
                                                       //   cách tới mép vùng. "type/id" OSM, hoặc true = tự tìm theo tên.
                                                       //   Điểm đơn lẻ (tiệm, nút giao, cầu) KHÔNG đặt vung — giữ ghim.
    "ghi_chu": "user ghi …"}]

Ghi <work>/tien_ich.json: toạ độ đã chốt + nguồn + độ chắc (chac / DOAN) + khoảng cách chim bay tới mép ranh.
Điểm user đưa LUÔN được vẽ (user là nguồn), kể cả hạ tầng đang xây — khác luật "chỉ hạ tầng đang vận hành" của
phần tự khảo sát. Toạ độ ĐOÁN (chỉ khớp được tên xã/thôn) → hỏi user ở cổng duyệt.
"""
import argparse, json, math, os, re, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo
import khao_sat as KS


def ranh_of(work):
    q = geo.load_json(os.path.join(work, "quy_hoach", "quy_hoach.json"))
    ring = [tuple(p) for p in q["ranh"]]
    return q, ring


def dist_to_ranh(ll, ring_m, k):
    """(km chim bay tới mép ranh — 0 nếu nằm trong, điểm gần nhất trên ranh [lat,lon])."""
    p = np.asarray(geo.ll2m(*ll), float)
    A = ring_m; B = np.roll(ring_m, -1, axis=0); AB = B - A
    t = np.clip(np.einsum("ij,ij->i", p - A, AB) / (np.einsum("ij,ij->i", AB, AB) + 1e-12), 0, 1)
    Q = A + t[:, None] * AB
    d = np.linalg.norm(Q - p, axis=1)
    i = int(np.argmin(d))
    inside = KS.inside(p, ring_m)
    return (0.0 if inside else float(d[i]) / k / 1000), list(geo.m2ll(*Q[i])), inside


def from_link(link):
    """toạ độ trong link Google Maps: !3dLAT!4dLON (ghim địa điểm) ưu tiên hơn @LAT,LON (tâm màn hình)."""
    m = re.search(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", link)
    if m:
        return (float(m.group(1)), float(m.group(2))), "link Google Maps (ghim)"
    m = re.search(r"[?&](?:q|query|ll|destination)=(-?\d+\.\d+),\s*(-?\d+\.\d+)", link)
    if m:
        return (float(m.group(1)), float(m.group(2))), "link Google Maps (q=)"
    m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", link)
    if m:
        return (float(m.group(1)), float(m.group(2))), "link Google Maps (@ tâm màn hình — kiểm lại)"
    return None, None


def photon_best(cache, q, near):
    d = cache.photon(q, loose=True)
    out = []
    for f in d.get("features", []):
        c = f["geometry"]["coordinates"]; p = f["properties"]
        ll = (c[1], c[0])
        dk = geo.haversine(ll, near) / 1000
        if dk > 60:
            continue
        out.append(dict(ll=ll, ten=p.get("name"), loai=f"{p.get('osm_key')}={p.get('osm_value')}",
                        noi=", ".join(x for x in (p.get("district"), p.get("city") or p.get("county"), p.get("state")) if x), cach_km=round(dk, 1)))
    return out


def intersection(cache, rx, near, radius_km=8.0):
    """giao điểm 2 tuyến OSM (regex tên HOẶC ref) gần điểm `near` — gồm cả đoạn đang xây (điểm do user đưa)."""
    lat, lon = near
    dl = radius_km / 111.0; do = radius_km / (111.0 * math.cos(math.radians(lat)))
    bb = f"{lat - dl:.4f},{lon - do:.4f},{lat + dl:.4f},{lon + do:.4f}"
    sets = []
    for r in rx:
        q = f'[out:json][timeout:180];(way["highway"]["name"~"{r}"]({bb});way["highway"]["ref"~"{r}"]({bb}););out geom tags;'
        d = cache.overpass(q)
        P = []
        for e in d.get("elements", []):
            g = [(p["lat"], p["lon"]) for p in e.get("geometry", [])]
            if len(g) >= 2:
                P.append(geo.resample(geo.lls2m(g).astype(float), 8))
        if not P:
            return None, f"OSM không có tuyến khớp «{r}» trong {radius_km:.0f} km"
        sets.append(np.concatenate(P))
    from scipy.spatial import cKDTree
    t = cKDTree(sets[1])
    dd, ii = t.query(sets[0])
    j = int(np.argmin(dd))
    k = geo.scale_k(lat)
    if dd[j] / k > 60:
        return None, f"2 tuyến gần nhau nhất {dd[j] / k:.0f} m — không cắt nhau trong vùng tìm"
    m = (sets[0][j] + sets[1][ii[j]]) / 2
    return tuple(round(v, 6) for v in geo.m2ll(*m)), f"giao điểm OSM «{rx[0]}» × «{rx[1]}» (lệch {dd[j] / k:.0f} m)"


TIEN_TO_DC = re.compile(r"^(thôn|xóm|ấp|bản|khu|tổ|xã|phường|thị trấn|huyện|quận|tỉnh|thành phố|tp\.?)\s+", re.I)


def place_lookup(cache, dia_chi, center, radius_km=60):
    """phần CỤ THỂ NHẤT của địa chỉ là tên thôn/xã có trong OSM (place=*) → toạ độ mức thôn (ĐOÁN, hỏi user)."""
    parts = [TIEN_TO_DC.sub("", x.strip()) for x in dia_chi.split(",") if x.strip()]
    lat, lon = center
    for i, p in enumerate(parts[:-1] if len(parts) > 1 else parts):
        q = (f'[out:json][timeout:120];(node["place"~"^(village|hamlet|neighbourhood|suburb|quarter|isolated_dwelling|town)$"]'
             f'["name"="{p}"](around:{radius_km * 1000},{lat},{lon}););out;')
        d = cache.overpass(q)
        els = [e for e in d.get("elements", []) if "lat" in e]
        if not els:
            continue
        nxt = KS.norm(parts[i + 1]) if i + 1 < len(parts) else ""
        # nhiều thôn trùng tên: chọn cái gần thôn/xã kế tiếp trong địa chỉ (tên xã thường cũng là một place)
        if nxt and len(els) > 1:
            q2 = (f'[out:json][timeout:120];(nwr["name"~"{parts[i + 1]}"](around:{radius_km * 1000},{lat},{lon}););out center;')
            ref = [KS.cen(e) for e in cache.overpass(q2).get("elements", [])]
            ref = [(r["lat"], r["lon"]) for r in ref if r.get("lat") is not None]
            if ref:
                els.sort(key=lambda e: min(geo.haversine((e["lat"], e["lon"]), r) for r in ref))
        e = els[0]
        return (round(e["lat"], 6), round(e["lon"], 6)), f"ĐOÁN mức thôn: «{p}» (OSM place={e['tags'].get('place')}) — chưa có toạ độ đúng điểm"
    return None


def road_near_ranh(cache, rx, ring_m, center, k, radius_km=25.0):
    """loai "duong" (QL21B, đường tỉnh…): tuyến OSM theo regex tên/ref → điểm trên tuyến gần ranh nhất (ghim + khoảng cách)."""
    lat, lon = center
    dl = radius_km / 111.0; do = radius_km / (111.0 * math.cos(math.radians(lat)))
    bb = f"{lat - dl:.4f},{lon - do:.4f},{lat + dl:.4f},{lon + do:.4f}"
    q = f'[out:json][timeout:180];(way["highway"]["name"~"{rx}"]({bb});way["highway"]["ref"~"{rx}"]({bb}););out geom tags;'
    els = [e for e in cache.overpass(q).get("elements", []) if len(e.get("geometry", [])) >= 2]
    if not els:
        return None, f"OSM không có đường khớp «{rx}» trong {radius_km:.0f} km"
    P = np.concatenate([geo.resample(geo.lls2m([(p["lat"], p["lon"]) for p in e["geometry"]]).astype(float), 10) for e in els])
    ins = np.array([KS.inside(p, ring_m) for p in P[::5]])
    if ins.any():                                                # đường chạy QUA khu quy hoạch: ghim ở chỗ cắt ranh
        A = ring_m; B = np.roll(ring_m, -1, axis=0)
        dd = [np.min(np.linalg.norm(A + np.clip(np.einsum("ij,ij->i", p - A, B - A) / (np.einsum("ij,ij->i", B - A, B - A) + 1e-12), 0, 1)[:, None] * (B - A) - p, axis=1)) for p in P]
        m = P[int(np.argmin(dd))]
        how = f"OSM đường «{rx}» ({len(els)} way) — CHẠY QUA khu quy hoạch, ghim ở chỗ cắt ranh"
    else:
        d = [dist_to_ranh(geo.m2ll(*p), ring_m, k)[0] for p in P[::3]]
        m = P[::3][int(np.argmin(d))]
        how = f"OSM đường «{rx}» ({len(els)} way) — ghim ở điểm gần ranh nhất"
    return tuple(round(v, 6) for v in geo.m2ll(*m)), how


ZONE_TAGS = ("boundary", "landuse", "place", "industrial", "residential")


def zone_of(cache, ref):
    """"relation/19514801" | "way/595927298" → (vòng ranh [lat,lon] lớn nhất, tags OSM)."""
    t, i = ref.split("/")
    d = cache.overpass(f"[out:json][timeout:180];{t}({int(i)});out geom;")   # "out geom tags" bỏ mất members của relation
    for e in d.get("elements", []):
        rings = KS.element_rings(e)
        if rings:
            return max(rings, key=KS.ring_area_m2), e.get("tags", {})
    return None, {}


def zone_find(cache, ten, near, radius_km=30):
    """tìm VÙNG OSM theo tên (ranh xã / phường, khu công nghiệp, khu dân cư…) gần `near` → "type/id" hoặc None + ứng viên."""
    core = TIEN_TO_DC.sub("", KS.tach_ten(ten)[0]).strip()
    lat, lon = near
    q = (f'[out:json][timeout:180];(relation["boundary"="administrative"]["name"~"{core}$",i](around:{radius_km * 1000},{lat},{lon});'
         f'nwr["landuse"]["name"~"{core}",i](around:{radius_km * 1000},{lat},{lon});'
         f'nwr["industrial"]["name"~"{core}",i](around:{radius_km * 1000},{lat},{lon}););out tags center;')
    cands = []
    for e in cache.overpass(q).get("elements", []):
        if e["type"] == "node":
            continue
        c = KS.cen(e)
        if c.get("lat") is None:
            continue
        cands.append(dict(ref=f"{e['type']}/{e['id']}", ten=e.get("tags", {}).get("name"),
                          loai=next((f"{t}={e['tags'][t]}" for t in ZONE_TAGS if t in e.get("tags", {})), "?"),
                          cach_km=round(geo.haversine((c["lat"], c["lon"]), near) / 1000, 1)))
    cands.sort(key=lambda c: (KS.norm_dau(c["ten"] or "") != KS.norm_dau(core) and not KS.norm_dau(c["ten"] or "").endswith(KS.norm_dau(core)), c["cach_km"]))
    return (cands[0]["ref"] if cands else None), cands


def zone_dist(zone_m, ring_m, k):
    """km nhỏ nhất giữa 2 đa giác (0 nếu chạm / chồng nhau)."""
    if any(KS.inside(p, ring_m) for p in zone_m[::3]) or any(KS.inside(p, zone_m) for p in ring_m[::3]):
        return 0.0
    best = min(KS.seg_dist(zone_m, ring_m[i], ring_m[(i + 1) % len(ring_m)]).min() for i in range(len(ring_m)))
    best = min(best, min(KS.seg_dist(ring_m, zone_m[i], zone_m[(i + 1) % len(zone_m)]).min() for i in range(len(zone_m))))
    return float(best) / k / 1000


def resolve(it, cache, center, ring_m=None, k=None):
    if it.get("loai") == "duong" and it.get("osm") and ring_m is not None:
        ll, how = road_near_ranh(cache, it["osm"], ring_m, center, k)
        if ll:
            return ll, how, True, []
        print(f"  ⚠ {it['ten']}: {how}")
    if it.get("latlon"):
        return tuple(it["latlon"]), it.get("nguon") or "toạ độ user / hồ sơ", not it.get("doan"), []
    if it.get("link"):
        ll, how = from_link(it["link"])
        if ll:
            return ll, how, "@" not in how, []
    near = center
    cands = []
    if it.get("dia_chi"):
        c = photon_best(cache, it["dia_chi"], center)
        if c:
            near = c[0]["ll"]
            cands += c
    if it.get("giao"):
        ll, how = intersection(cache, it["giao"], near)
        if ll:
            return ll, how, True, cands
        print(f"  ⚠ {it['ten']}: {how}")
    q = it["ten"] + (", " + it["dia_chi"] if it.get("dia_chi") else "")
    c2 = photon_best(cache, q, near)
    # khớp TÊN thật sự: tên ứng viên chứa NGUYÊN CỤM tên user (giữ dấu, phần trước dấu phẩy). So từng chữ bỏ dấu từng
    # khớp nhầm "Mễ Sở, Hưng Yên" ↔ "Đường sắt đô thị sô 8 … Hưng Yên" (sô = sở, hưng, yên — 10/11/2026)
    cum = KS.norm_dau(KS.tach_ten(it["ten"])[0])
    for c in c2:
        if c["ten"] and cum and cum in KS.norm_dau(c["ten"]) and not re.search(r"construction|proposed", c["loai"]):
            return c["ll"], f"Photon «{c['ten']}» ({c['loai']})", True, c2 + cands
    if it.get("dia_chi"):                                        # thôn / xóm / xã trong địa chỉ (Photon hay thiếu thôn — "Tầm Tang")
        pl = place_lookup(cache, it["dia_chi"], center)
        if pl:
            return pl[0], pl[1], False, c2 + cands
    if cands:
        return cands[0]["ll"], f"ĐOÁN theo địa chỉ «{it['dia_chi']}» → «{cands[0]['ten']}» ({cands[0]['loai']})", False, c2 + cands
    if c2:
        return c2[0]["ll"], f"ĐOÁN «{c2[0]['ten']}» ({c2[0]['loai']})", False, c2
    return None, "không tìm thấy", False, []


def survey(work, q, ring, k):
    """khảo sát tự động (bộ khảo sát của skill gốc) quanh RANH khu quy hoạch → gợi ý, Claude chọn."""
    cache = KS.Cache(work)
    ring_m = geo.lls2m(KS.simplify(ring, 400))
    area = KS.ring_area_m2(ring)
    S = dict(ll=tuple(q["tam"]), k=k, ring=KS.simplify(ring, 400), ring_m=ring_m, osm=None, name_n="",
             radius_m=math.sqrt(area / math.pi))
    S["dist_m"] = lambda m, _r=ring_m: KS.poly_dist_m(np.asarray(m, float), _r, k)
    S["admin"] = KS.admin_line(S["ll"], cache)
    S["water"] = False
    dropped = []
    print("● Tự khảo sát (chỉ hạ tầng đang vận hành) quanh ranh…")
    res = dict(metro=KS.survey_metro(S, cache, dropped), truc=[{k_: v for k_, v in r.items() if k_ != "D"} for r in KS.survey_roads(S, cache, dropped)],
               cau=KS.survey_bridges(S, cache), san_bay=KS.survey_airport(S, cache), tien_ich=KS.survey_pois(S, cache, dropped), bo=dropped)
    geo.save_json(os.path.join(work, "tien_ich_goi_y.json"), res)
    print("  Tiện ích: " + ("; ".join(f"{p['name']} ({p['kind']}) ~{p['d']:.1f} km @ {p['ll'][0]:.5f},{p['ll'][1]:.5f}" for p in res["tien_ich"]) or "—"))
    print("  Trục lớn: " + (", ".join(f"{r['key']} ~{r['dmin']:.1f} km" for r in res["truc"]) or "—"))
    print("  Cầu: " + (", ".join(f"{b['name']} ~{b['d']:.1f} km" for b in res["cau"]) or "—"))
    print("  Metro: " + (", ".join(m["name"] for m in res["metro"]) or "—"))
    if res["san_bay"]:
        print(f"  Sân bay: {res['san_bay']['name']} ~{res['san_bay']['d']:.1f} km")
    print(f"● Gợi ý ghi ở tien_ich_goi_y.json — Claude chọn điểm đáng đưa, chép vào tien_ich_vao.json (kèm latlon)")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--vao", help="file danh sách (mặc định <work>/tien_ich_vao.json)")
    ap.add_argument("--tu_dong", action="store_true", help="tự khảo sát tiện ích quanh khu (gợi ý)")
    a = ap.parse_args()
    q, ring = ranh_of(a.work)
    k = geo.scale_k(q["tam"][0])
    ring_m = geo.lls2m(ring).astype(float)
    if a.tu_dong:
        survey(a.work, q, ring, k)
    vao = a.vao or os.path.join(a.work, "tien_ich_vao.json")
    if not os.path.exists(vao):
        if a.tu_dong:
            return 0
        raise SystemExit(f"⛔ Chưa có {vao} — Claude viết danh sách điểm từ lời user (xem đầu file tien_ich.py).")
    items = geo.load_json(vao)
    cache = KS.Cache(a.work)
    out = []
    print(f"● {len(items)} điểm user đưa — tìm toạ độ:")
    for it in items:
        ll, how, chac, cands = resolve(it, cache, tuple(q["tam"]), ring_m, k)
        if ll is None:
            print(f"  ⛔ {it['ten']}: không tìm được toạ độ — xin user link Google Maps / toạ độ")
            out.append(dict(it, latlon=None, nguon=how, chac=False))
            continue
        d, near, inside = dist_to_ranh(ll, ring_m, k)
        r = dict(it, latlon=[round(ll[0], 6), round(ll[1], 6)], nguon=how, chac=bool(chac), cach_ranh_km=round(d, 3),
                 diem_ranh_gan=[round(v, 6) for v in near], trong_ranh=inside,
                 ung_vien=[dict(c, ll=[round(c["ll"][0], 6), round(c["ll"][1], 6)]) for c in cands[:6]])
        # điểm là CẢ MỘT CỤM / QUẦN THỂ (xã, cụm CN, khu dân cư) → khoanh vùng: line đi tới MÉP vùng, ghim giữa vùng
        # (user 10/11/2026: "nó là 1 cụm, quần thể thì nên khoanh vùng lại xong đi đến"); điểm đơn lẻ giữ ghim như cũ
        if it.get("vung"):
            ref, zc = (it["vung"], []) if isinstance(it["vung"], str) else zone_find(cache, it["ten"], ll)
            zr, ztags = zone_of(cache, ref) if ref else (None, {})
            if zr is None:
                print(f"  ⚠ {it['ten']}: không lấy được vùng OSM ({ref or 'không tìm thấy theo tên'}) — giữ dạng ghim"
                      + ("; ứng viên: " + ", ".join(f"{c['ref']} «{c['ten']}» {c['loai']} ~{c['cach_km']} km" for c in zc[:5]) if zc else ""))
            else:
                zr = KS.simplify(zr, 400)
                zm = geo.lls2m(zr).astype(float)
                if not KS.inside(geo.ll2m(*ll), zm):             # ghim phải nằm TRONG vùng
                    ll = tuple(round(v, 6) for v in KS.interior_point(zr))
                    r["latlon"] = list(ll)
                d = zone_dist(zm, ring_m, k)
                r.update(vung=[[round(a_, 6), round(b_, 6)] for a_, b_ in zr], vung_nguon=f"OSM {ref} «{ztags.get('name', '?')}»",
                         vung_ha=round(KS.ring_area_m2(zr) / 1e4, 1), cach_ranh_km=round(d, 3), trong_ranh=False,
                         giap_ranh=d < 0.02)
                print(f"    ◯ khoanh vùng {r['vung_nguon']} ~{r['vung_ha']:,.0f} ha — mép vùng cách mép ranh "
                      + ("(GIÁP / CHỒNG khu quy hoạch)" if d < 0.02 else f"~{d:.1f} km chim bay"))
        out.append(r)
        tag = "" if chac else "  ← ĐOÁN, hỏi user"
        dtxt = "NẰM TRONG khu quy hoạch" if inside else (f"~{d * 1000:.0f} m" if d < 1 else f"~{d:.1f} km") + " tới mép ranh (chim bay)"
        print(f"  • {it['ten']}: {ll[0]:.6f}, {ll[1]:.6f} — {how} — {dtxt}{tag}")
    geo.save_json(os.path.join(a.work, "tien_ich.json"), dict(diem=out))
    print(f"● Ghi {os.path.join(a.work, 'tien_ich.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
