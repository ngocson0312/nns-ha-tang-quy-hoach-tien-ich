"""Hồ sơ dự án (du_an.json) → kế hoạch dựng (plan.json) + bảng duyệt nội dung.

  python plan.py --brief du_an.json --work THU_MUC_LAM_VIEC

Việc làm:
  1. lấy hình học từng tuyến (OSM theo tên / file trace_lines / toạ độ tay), cắt theo bán kính quanh dự án
  2. đặt các điểm (ga, cầu, nút giao, sân bay) lên tuyến, tính khoảng cách tới dự án (theo tuyến hoặc chim bay)
  3. dựng khung nhìn từng chương, máy quay van Wijk + ease sin, tự kéo dài cú bay tới khi đạt ngưỡng êm
  4. xếp nhịp: icon bật → vẽ nét → nhãn bật khi icon chạm điểm; chương spotlight có vòng km
  5. đặt chữ tránh chồng lấn (nhãn, chữ chương, thẻ dự án, nét tuyến, vùng an toàn)
  6. lập danh sách SFX bám sự kiện; in bảng duyệt tiếng Việt
"""
import argparse, hashlib, json, math, os, re, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import geo
import sprites as SP


# ================================================================== tiện ích
def ease_s(x):
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def ease_draw(x):
    """tiến độ vẽ nét: vào NHANH rồi chậm dần (ease-out bậc 2) — sin cũ chậm cả đầu lẫn cuối, nhìn lề mề."""
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 2


def ease_draw_inv(y):
    y = min(1.0, max(0.0, y))
    return 1 - math.sqrt(1 - y)


def ease_s_inv(y):
    y = min(1.0, max(0.0, y))
    return math.acos(1 - 2 * y) / math.pi


def fmt_km(km):
    return f"{km:.1f}".replace(".", ",")


def fmt_dist(km):
    """khoảng cách in trên nhãn: dưới 1 km ghi MÉT (làm tròn 10 m), từ 1 km ghi km 1 chữ số lẻ (user 10/11/2026: "điền rõ
    khoảng cách bao nhiêu m hoặc km")."""
    if km < 0.995:
        return f"{max(10, int(round(km * 100)) * 10)} m"
    return f"{fmt_km(km)} km"


def warn(msgs, m):
    msgs.append(m)


# ================================================================== hình học tuyến
def ql_str(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def osm_route(regex, kind, center_ll, radius_km, work, names=None):
    """regex tên (chuỗi) HOẶC names = danh sách tên CHÍNH XÁC (khảo sát tự động — tránh thoát ký tự regex)."""
    lat, lon = center_ll
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * math.cos(math.radians(lat)))
    bb = f"{lat - dlat:.4f},{lon - dlon:.4f},{lat + dlat:.4f},{lon + dlon:.4f}"
    kinds = {"highway": ["highway"], "railway": ["railway"], "any": ["highway", "railway"]}[kind]
    # CHỈ way đang vận hành (user chốt 17/10): ray đang xây/quy hoạch, đường construction/proposed bị loại ngay ở truy vấn
    filt = {"highway": f'["highway"]["highway"!~"{C.HIGHWAY_NOT_OPERATING}"]', "railway": f'["railway"~"{C.RAIL_OPERATING}"]'}
    if names:
        body = "".join(f'way["name"="{ql_str(n)}"]{filt[k]}({bb});' for n in names for k in kinds)
        regex = " | ".join(names)
    else:
        body = "".join(f'way["name"~"{regex}"]{filt[k]}({bb});' for k in kinds)
    q = f"[out:json][timeout:180];({body});out geom tags;"
    key = hashlib.md5(q.encode("utf-8")).hexdigest()[:12]
    cp = os.path.join(work, "osm", f"{key}.json")
    if os.path.exists(cp):
        d = geo.load_json(cp)
    else:
        print(f"  … hỏi OSM: {regex[:70]} ({kind})")
        d = geo.overpass(q)
        geo.save_json(cp, d)
    ways = [[(p["lat"], p["lon"]) for p in e["geometry"]] for e in d.get("elements", []) if e.get("geometry")]
    if not ways:
        return None, 0
    # tuyến đang thi công bị OSM chia nhiều khúc rời (khe vài chục–vài trăm m); đường đôi có 2 chuỗi song song.
    # Nối dung sai 250 m rồi chọn chuỗi đi GẦN DỰ ÁN nhất (trong các chuỗi dài ≥ 25 % chuỗi dài nhất).
    chains = geo.chain_ways(ways, tol=250)
    Lmax = geo.geolen(chains[0])
    cand = [c for c in chains if geo.geolen(c) >= 0.25 * Lmax] or chains[:1]
    pm = geo.ll2m(*center_ll)
    best = min(cand, key=lambda c: geo.nearest_on(geo.lls2m(c), pm)[3])
    return best, len(ways)


VUNG = {"ll": None, "m": None}           # vùng đối tượng (ranh khu đất / mặt hồ) — đặt trong build()


def start_from_vung(proj_ll, target_ll):
    """đối tượng là vùng lớn → đường đi bắt đầu từ điểm ranh gần đích nhất (không từ giữa hồ)."""
    if VUNG["ll"] is None:
        return tuple(proj_ll)
    T = geo.ll2m(*target_ll)
    i = int(np.argmin(np.linalg.norm(VUNG["m"] - T, axis=1)))
    return tuple(VUNG["ll"][i])


def osm_path(dd, proj_ll, work):
    """ĐƯỜNG ĐI THẬT từ dự án tới đích (qua các điểm "qua") trên đồ thị đường OSM đang vận hành — thay cho nối
    khúc theo tên (Lê Quang Đạo bị OSM chia khúc rời → nét cụt cách SVĐ 800 m, Matrix One 17/10).
    dd = {"den": [lat,lon], "qua": [[lat,lon],…], "hang": "primary"} — "hang" = cấp đường THẤP NHẤT được đi ở đoạn giữa;
    trong ROUTE_LOCAL_KM quanh mỗi đầu mút được đi tới cấp residential (vào tận cổng)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    from scipy.spatial import cKDTree
    first_target = (dd.get("qua") or [dd["den"]])[0]
    pts = [start_from_vung(proj_ll, first_target)] + [tuple(x) for x in dd.get("qua", [])] + [tuple(dd["den"])]
    hang = dd.get("hang", "tertiary")
    major = C.ROAD_CLASSES[:C.ROAD_CLASSES.index(hang) + 1]
    rx = lambda cl: "^(" + "|".join(cl) + ")(_link)?$"
    lat0, lat1 = min(p[0] for p in pts), max(p[0] for p in pts)
    lon0, lon1 = min(p[1] for p in pts), max(p[1] for p in pts)
    # khung tìm đường nới theo quãng chim bay: qua sông phải vòng tới cầu/phà (Mễ Sở 10/11) — khung 2 km cố định cắt mất cầu
    span = geo.haversine(pts[0], pts[-1]) / 1000
    mk = max(2.0, C.ROUTE_BBOX_FRAC * span)
    mlat = mk / 111.0; mlon = mk / (111.0 * math.cos(math.radians(lat0)))
    bb = f"{lat0 - mlat:.4f},{lon0 - mlon:.4f},{lat1 + mlat:.4f},{lon1 + mlon:.4f}"
    body = f'way["highway"~"{rx(major)}"]({bb});'
    if dd.get("dang_xay"):          # "chuẩn quy hoạch": được đi cả đường/cầu ĐANG XÂY (highway=construction) — chỉ khi user muốn
        # trừ CAO TỐC đang xây: chưa biết chỗ lên/xuống → định tuyến chạy hết cầu cao tốc tới nút giao rồi quay đầu về song
        # hành (vòng gấp khúc, cầu Mễ Sở 10/11); làn song hành / cầu cấp primary đi thẳng vào làng
        body += f'way["highway"="construction"]["construction"~"{rx([c for c in major if c != "motorway"])}"]({bb});'
    if dd.get("pha", True):         # phà đang chạy (route=ferry) — qua sông khi chưa có cầu
        body += f'way["route"="ferry"]({bb});'
    # quanh MỌI đầu mút + điểm qua: được đi cả đường làng nhỏ (service/track/living_street) — thôn trong bãi sông chỉ nối
    # với làng bên cạnh bằng đường loại này (Tầm Tang ↔ Mễ Sở, 10/11: thiếu thì "không có đường liền" khi cấm phà)
    for (a, b) in pts:
        body += f'way(around:{int(C.ROUTE_LOCAL_KM * 1000)},{a},{b})["highway"~"{rx(C.ROAD_CLASSES + C.ROAD_LOCAL_EXTRA)}"];'
    q = f"[out:json][timeout:240];({body});out body geom;"
    key = hashlib.md5(q.encode("utf-8")).hexdigest()[:12]
    cp = os.path.join(work, "osm", f"path_{key}.json")
    if os.path.exists(cp):
        d = geo.load_json(cp)
    else:
        print(f"  … hỏi OSM mạng đường (định tuyến tới {dd['den']})")
        d = geo.overpass(q)
        geo.save_json(cp, d)
    ids, coord = {}, []
    rows, cols, wts = [], [], []
    edge_way, ways = {}, []
    for e in d.get("elements", []):
        if e.get("type") != "way" or "geometry" not in e or "nodes" not in e:
            continue
        t = e.get("tags", {})
        hw = t.get("highway", "").replace("_link", "")
        if hw == "construction":
            hw = t.get("construction", "").replace("_link", "")
        if t.get("route") == "ferry":
            cost, hw = C.FERRY_COST, "ferry"
        elif hw in C.ROAD_COST:
            cost = C.ROAD_COST[hw]
        else:
            continue
        wi = len(ways)
        ways.append(dict(name=t.get("name") or t.get("ref"), bridge=t.get("bridge") not in (None, "no"),
                         xay=t.get("highway") == "construction", pha=hw == "ferry"))
        nodes = e["nodes"]; geom = e["geometry"]
        for nid, g in zip(nodes, geom):
            if nid not in ids:
                ids[nid] = len(coord); coord.append((g["lat"], g["lon"]))
        for (n1, g1), (n2, g2) in zip(zip(nodes, geom), zip(nodes[1:], geom[1:])):
            dist = geo.haversine((g1["lat"], g1["lon"]), (g2["lat"], g2["lon"]))
            rows.append(ids[n1]); cols.append(ids[n2]); wts.append(dist * cost + 0.01)
            edge_way[(min(ids[n1], ids[n2]), max(ids[n1], ids[n2]))] = wi
    if not coord:
        raise SystemExit(f"⛔ Không có mạng đường OSM quanh tuyến tới {dd['den']}.")
    if dd.get("dang_xay"):
        # đường ĐANG XÂY (song hành VĐ4…) cắt ngang đường đang chạy nhưng OSM chưa có nút giao chung → định tuyến chạy quá rồi quay
        # đầu (cầu Mễ Sở 10/11: dư 1,2 km). Nối ảo nút đường đang xây (không phải cầu) với nút đường đang chạy ≤ C.XAY_NOI_M.
        xay_n, run_n = set(), set()
        for e in d.get("elements", []):
            if e.get("type") != "way" or "nodes" not in e:
                continue
            t = e.get("tags", {})
            tgt = xay_n if t.get("highway") == "construction" and t.get("bridge") in (None, "no") else run_n
            tgt.update(ids[n] for n in e["nodes"] if n in ids)
        run_l = sorted(run_n - xay_n)
        if xay_n and run_l:
            Mr = np.array([geo.ll2m(*coord[i]) for i in run_l]); tr = cKDTree(Mr)
            kk = geo.scale_k(coord[0][0])
            for i in xay_n:
                dist_, j = tr.query(geo.ll2m(*coord[i]))
                if dist_ / kk <= C.XAY_NOI_M:
                    rows.append(i); cols.append(run_l[j]); wts.append(dist_ / kk * 1.5 + 0.01)
    N = len(coord)
    G = coo_matrix((wts, (rows, cols)), shape=(N, N)).tocsr()
    G = G.minimum(G.T) if False else G.maximum(G.T)            # bỏ qua chiều 1 chiều — chỉ vẽ, không chỉ đường
    M = np.array([geo.ll2m(*c) for c in coord])
    tree = cKDTree(M)
    snaps = []
    for p in pts:
        dd_, i = tree.query(geo.ll2m(*p))
        snaps.append((int(i), dd_ / geo.scale_k(p[0])))
    # "tu_ranh": chặng đầu xuất phát từ MỌI nút đường nằm trong ranh khu quy hoạch → lối ra ranh cho quãng đường ngắn nhất
    # (điểm ranh gần đích nhất theo chim bay có thể là bờ sông không có đường — Mễ Sở 10/11)
    src_in = None
    if dd.get("tu_ranh") and VUNG["m"] is not None:
        src_in = np.nonzero(inside_poly(M, VUNG["m"]))[0]
        if len(src_in) == 0:
            src_in = None
    # "den_vung": đích là CẢ MỘT VÙNG (xã, cụm CN) → đi tới nút đường TRONG vùng gần nhất theo quãng đường, cắt ở mép vùng
    Zm = geo.lls2m(dd["den_vung"]).astype(float) if dd.get("den_vung") else None
    tgt_in = np.nonzero(inside_poly(M, Zm))[0] if Zm is not None else None
    if Zm is not None and len(tgt_in) == 0:
        raise SystemExit(f"⛔ Không có nút đường OSM nào trong vùng đích {dd['den']} — kiểm ranh vùng.")
    path = []
    for j, ((u, _), (v, _)) in enumerate(zip(snaps, snaps[1:])):
        if j == 0 and src_in is not None:
            dist, pred, srcs = dijkstra(G, indices=src_in, return_predecessors=True, min_only=True)
        else:
            dist, pred = dijkstra(G, indices=u, return_predecessors=True)
        if Zm is not None and j == len(snaps) - 2:
            dz = dist[tgt_in]
            if np.isfinite(dz).any():
                v = int(tgt_in[int(np.argmin(dz))])
                snaps[-1] = (v, 0.0)
        if not np.isfinite(dist[v]):
            raise SystemExit(f"⛔ Không tìm được đường đi liền tới {coord[v]} trên mạng đường OSM — kiểm điểm đích/điểm qua.")
        seg = [v]
        while pred[seg[-1]] >= 0:
            seg.append(int(pred[seg[-1]]))
        seg = seg[::-1]
        path += seg[1:] if path else seg
    if src_in is not None:                                   # cắt phần nằm trong ranh: nét bắt đầu đúng lối ra mép ranh
        ins = inside_poly(M[path], VUNG["m"])
        last = max([i for i in range(len(path)) if ins[i]] or [0])
        path = path[last:]
    if Zm is not None:                                       # dừng ở chỗ ĐẦU TIÊN chạm vùng đích
        insz = inside_poly(M[path], Zm)
        first = next((i for i in range(len(path)) if insz[i]), len(path) - 1)
        path = path[:max(first, 1) + 1]
    if len(path) < 2:
        raise SystemExit(f"⛔ Đường tới {dd['den']} chỉ còn 1 nút (đích chạm ranh khu quy hoạch?) — điểm giáp ranh thì không cần line.")
    qua, dai = [], {}
    for a_, b_ in zip(path, path[1:]):
        w = ways[edge_way[(min(a_, b_), max(a_, b_))]] if (min(a_, b_), max(a_, b_)) in edge_way else None
        if w and (w["bridge"] or w["xay"] or w["pha"]) and w["name"]:
            tag = (w["name"], "phà" if w["pha"] else ("cầu" if w["bridge"] else "đường"), w["xay"])
            if tag not in qua:
                qua.append(tag)
            dai[tag] = dai.get(tag, 0) + geo.haversine(coord[a_], coord[b_])
    qua.sort(key=lambda x: -dai[x])                          # cầu/phà DÀI nhất lên đầu (nhãn line), bỏ cầu cống nhỏ
    qua = [x for x in qua if dai[x] >= 150 or x[1] == "phà"]
    ll = [coord[i] for i in path]
    if Zm is not None:                                       # nút cuối nằm trong vùng → kéo về đúng giao điểm với MÉP vùng
        ll[-1] = tuple(geo.m2ll(*seg_cross(M[path[-2]], M[path[-1]], Zm)))
    return ll, snaps, qua


def seg_cross(A, B, R):
    """điểm đầu tiên trên đoạn A→B cắt ranh đa giác R (Mercator); không cắt → B."""
    A, B = np.asarray(A, float), np.asarray(B, float)
    P1, P2 = R, np.roll(R, -1, axis=0)
    d, e, w = B - A, P2 - P1, P1 - A
    den = d[0] * e[:, 1] - d[1] * e[:, 0]
    t = (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / (den + 1e-15)
    s = (w[:, 0] * d[1] - w[:, 1] * d[0]) / (den + 1e-15)
    ok = (np.abs(den) > 1e-9) & (t >= 0) & (t <= 1) & (s >= 0) & (s <= 1)
    return A + d * float(t[ok].min()) if ok.any() else B


def inside_poly(P, R):
    """điểm (Mercator) nằm trong đa giác R — vector hoá (tia chẵn-lẻ)."""
    P = np.asarray(P, float); x, y = P[:, 0][:, None], P[:, 1][:, None]
    x1, y1 = R[:, 0][None, :], R[:, 1][None, :]
    x2, y2 = np.roll(R[:, 0], -1)[None, :], np.roll(R[:, 1], -1)[None, :]
    hit = ((y1 > y) != (y2 > y)) & (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-15) + x1)
    return (hit.sum(1) % 2) == 1


def vung_dist_km(m, k):
    R = VUNG["m"]
    x, y = m
    c = False
    for i in range(len(R)):
        x1, y1 = R[i]; x2, y2 = R[(i + 1) % len(R)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-15) + x1:
            c = not c
    if c:
        return 0.0
    A = R; B = np.roll(R, -1, axis=0); AB = B - A
    t = np.clip(np.einsum("ij,ij->i", m - A, AB) / (np.einsum("ij,ij->i", AB, AB) + 1e-12), 0, 1)
    return float(np.min(np.linalg.norm(m - (A + t[:, None] * AB), axis=1))) / k / 1000


def clip_radius(ll, center_ll, radius_km):
    """giữ đoạn liền dài nhất nằm trong bán kính."""
    inside = [geo.haversine(center_ll, p) <= radius_km * 1000 for p in ll]
    best, cur = (0, 0), None
    for i, ok in enumerate(inside + [False]):
        if ok and cur is None:
            cur = i
        if not ok and cur is not None:
            if i - cur > best[1] - best[0]:
                best = (cur, i)
            cur = None
    return ll[best[0]:best[1]]


class NotOperating(Exception):
    pass


def resolve_route(key, spec, proj_ll, work, msgs):
    src = spec.get("nguon", {})
    n_ways = None
    if "latlon" in src:
        ll, how = [tuple(p) for p in src["latlon"]], "toạ độ tay"
    elif "trace" in src:
        tp = src["trace"]
        tp = tp if os.path.isabs(tp) else os.path.join(os.path.dirname(spec["_brief_dir"]), tp) if False else tp
        d = geo.load_json(src["trace"] if os.path.isabs(src["trace"]) else os.path.join(spec["_brief_dir"], src["trace"]))
        r = d["routes"][src.get("key", key)]
        ll, how = [tuple(p) for p in r["latlon"]], f"lấy từ ảnh ({os.path.basename(d.get('source', '?'))})"
    elif "duong_di" in src:
        ll, snaps, qua = osm_path(src["duong_di"], proj_ll, work)
        far = max(s[1] for s in (snaps[1:] if src["duong_di"].get("tu_ranh") else snaps))
        qtxt = "; ".join(f"{n}{' (ĐANG XÂY)' if x else ''}" for n, _l, x in qua)
        how = (f"đường đi thật OSM ({sum(geo.haversine(a, b) for a, b in zip(ll, ll[1:])) / 1000:.1f} km, bám đường lệch tối đa {far:.0f} m"
               + (f"; qua {qtxt}" if qtxt else "") + ")")
        if far > 400:
            msgs.append(f"tuyến {key}: điểm qua/đích cách đường gần nhất {far:.0f} m — kiểm toạ độ")
        cq = [x for x in qua if x[1] in ("cầu", "phà")] or [x for x in qua if x[2]]    # cầu/phà; không có → đường ĐANG XÂY
        if spec.get("nhan_tu_dong") and cq and not spec.get("nhan"):   # nhãn trên line: "QUA CẦU MỄ SỞ" / "đang xây"
            n, l_, x = cq[0]
            if l_ == "đường":                                          # "Đường Song hành Vành đai 4 Hà Nội" → "SONG HÀNH VÀNH ĐAI 4"
                n = re.sub(r"\s+(Hà Nội|TP\.?\s*HCM|Hồ Chí Minh)$", "", re.sub(r"^Đường\s+", "", n), flags=re.I)
                spec["nhan"] = ("QUA " + n).upper()
            else:
                spec["nhan"] = ("QUA " + (n if n.lower().startswith(l_) else f"{l_} {n}")).upper()
            spec["nhan_phu"] = "đang xây" if x else None
        if any(x for _n, _l, x in qua):
            msgs.append(f"tuyến {key}: đi qua đoạn ĐANG XÂY ({qtxt}) — theo quy hoạch, hỏi/báo user")
    elif "osm" in src or "osm_ten" in src:
        ll, n_ways = osm_route(src.get("osm"), src.get("loai", "any"), proj_ll, src.get("ban_kinh_km", 45), work,
                               names=src.get("osm_ten"))
        if ll is None:
            # có trong OSM nhưng chỉ ở dạng đang xây / quy hoạch → BỎ (luật chỉ đưa hạ tầng đã vận hành), không dừng
            raise NotOperating(f"tuyến {spec.get('ten', key)}: OSM chỉ có ở dạng đang xây / quy hoạch hoặc không có — bỏ, chưa vận hành")
        how = f"OSM ({n_ways} way)"
    else:
        raise SystemExit(f"⛔ Tuyến {key} chưa có nguồn hình học (osm / trace / latlon).")
    if spec.get("dao_chieu"):
        ll = ll[::-1]
    ll = clip_radius(ll, proj_ll, spec.get("ban_kinh_km", 40))
    if len(ll) < 2:
        raise SystemExit(f"⛔ Tuyến {key} không có đoạn nào trong bán kính quanh dự án.")
    k = geo.scale_k(proj_ll[0])
    P = geo.smooth(geo.resample(geo.lls2m(ll), 15 * k), 5)
    return P, how


# ================================================================== camera
def vw_path(c0, c1, u0, u1, k):
    """van Wijk & Nuij: s∈[0,1] → (tâm, u). k = hệ số Mercator→mét thật."""
    c0, c1 = np.asarray(c0, float), np.asarray(c1, float)
    d = float(np.linalg.norm((c1 - c0) / k))
    w0, w1 = u0 * C.W / k, u1 * C.W / k
    if d < 1e-6 * max(w0, w1) or d < 1.0:
        return lambda e: (c0 + (c1 - c0) * e, math.exp(math.log(u0) + (math.log(u1) - math.log(u0)) * e))
    r2 = C.RHO * C.RHO
    b0 = (w1 * w1 - w0 * w0 + r2 * r2 * d * d) / (2 * w0 * r2 * d)
    b1 = (w1 * w1 - w0 * w0 - r2 * r2 * d * d) / (2 * w1 * r2 * d)
    r0 = math.log(-b0 + math.sqrt(b0 * b0 + 1))
    r1 = math.log(-b1 + math.sqrt(b1 * b1 + 1))
    S = (r1 - r0) / C.RHO

    def f(e):
        sv = S * e
        pos = w0 / r2 * (math.cosh(r0) * math.tanh(C.RHO * sv + r0) - math.sinh(r0))
        w = w0 * math.cosh(r0) / math.cosh(C.RHO * sv + r0)
        return c0 + (c1 - c0) * (pos / d), w * k / C.W
    return f


def motion_of(f, D):
    n = max(2, int(round(D * C.FPS)))
    cs, us = [], []
    for i in range(n + 1):
        c, u = f(ease_s(i / n))
        cs.append(c); us.append(u)
    cs, us = np.array(cs), np.array(us)
    pan = np.linalg.norm(np.diff(cs, axis=0), axis=1) / us[:-1]
    zoom = np.abs(np.diff(np.log(us))) * 100
    return float(pan.max()), float(zoom.max())


def min_move(c0, u0, c1, u1, k, lo=C.MOVE_MIN):
    f = vw_path(c0, c1, u0, u1, k)
    D = lo
    while D < 12:
        p, z = motion_of(f, D)
        if p <= C.MAX_PAN_PX * C.PLAN_MARGIN and z <= C.MAX_ZOOM_PCT * C.PLAN_MARGIN:
            return D, p, z
        D += 0.1
    p, z = motion_of(f, D)
    return D, p, z


_VW_CACHE = {}


def camera_at(cam, t, k):
    """đánh giá camera (danh sách đoạn hold/move/lin) tại thời điểm t → (tâm, u)."""
    for i, sg in enumerate(cam):
        if t <= sg["t1"] or i == len(cam) - 1:
            c0, c1 = np.array(sg["c0"], float), np.array(sg["c1"], float)
            if sg["mode"] == "hold":
                return c0, sg["u0"]
            x = min(1.0, max(0.0, (t - sg["t0"]) / max(sg["t1"] - sg["t0"], 1e-6)))
            if sg["mode"] == "lin":
                return c0 + (c1 - c0) * x, math.exp(math.log(sg["u0"]) + (math.log(sg["u1"]) - math.log(sg["u0"])) * x)
            key = (id(cam), i, sg["t0"])
            if key not in _VW_CACHE:
                _VW_CACHE[key] = vw_path(c0, c1, sg["u0"], sg["u1"], k)
            return _VW_CACHE[key](ease_s(x))
    sg = cam[-1]
    return np.array(sg["c1"], float), sg["u1"]


def fit_view(pts, k, top=None, bottom=None, margin=C.VIEW_MARGIN, umin=1.25, edge=False):
    """khớp tập điểm (mét Mercator) vào vùng dùng được của khung dọc; trả (tâm, u).
    edge=True: bề ngang khớp theo MÉP KHUNG THẬT (EDGE_PAD), không theo vùng an toàn chữ."""
    pts = np.asarray(pts, float)
    x0, y0 = pts.min(0)
    x1, y1 = pts.max(0)
    top = C.SAFE_Y0 + 150 if top is None else top
    bottom = C.SAFE_Y1 - 40 if bottom is None else bottom
    left, right = (C.EDGE_PAD, C.W - C.EDGE_PAD) if edge else (C.SAFE_X0 + 30, C.SAFE_X1 - 30)
    aw, ah = (right - left) * (1 - margin), (bottom - top) * (1 - margin)
    u = max((x1 - x0) / aw, (y1 - y0) / ah, umin)
    cxs, cys = (left + right) / 2, (top + bottom) / 2
    mc = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
    c = mc - np.array([(cxs - C.W / 2) * u, (cys - C.H / 2) * u])
    return c, u


def ink_of(spr):
    a = spr[0][..., 3] > 60
    ys, xs = np.nonzero(a)
    return (xs.min(), ys.min(), xs.max(), ys.max()) if len(xs) else (0, 0, 1, 1)


def card_anchor(ps, spr, side):
    """vị trí đặt NEO sprite thẻ dự án (neo = giữa cạnh dưới) cho phía side quanh ghim ps."""
    x0, y0, x1, y1 = ink_of(spr)
    ax, ay = spr[1]
    if side == "duoi":
        return (ps[0], ps[1] + 24 + (ay - y0))
    if side == "phai":
        return (ps[0] + 26 + (ax - x0), ps[1] + ay - (y0 + y1) / 2)
    if side == "trai":
        return (ps[0] - 26 - (x1 - ax), ps[1] + ay - (y0 + y1) / 2)
    return (ps[0], ps[1] - 20)


def card_clear(c, u, PM, sprs, side, max_px=160):
    """khung zoom sát (khung_sat): thẻ dự án cụt ở mép khung → đẩy máy quay ít nhất có thể cho thẻ ra hẳn ngoài khung."""
    ps = to_screen(PM, c, u)
    bs = [card_box(ps, s_, side) for s_ in sprs]
    x0, y0 = min(b_[0] for b_ in bs), min(b_[1] for b_ in bs)
    x1, y1 = max(b_[2] for b_ in bs), max(b_[3] for b_ in bs)
    if not (x1 > 0 and x0 < C.W and y1 > 0 and y0 < C.H):
        return c
    if x0 >= C.SAFE_X0 and x1 <= C.SAFE_X1 and y0 >= C.SAFE_Y0 and y1 <= C.SAFE_Y1:
        return c
    opts = [(C.W + 6 - x0, 0.0), (-(x1 + 6), 0.0), (0.0, C.H + 6 - y0), (0.0, -(y1 + 6))]
    dx, dy = min(opts, key=lambda v: abs(v[0]) + abs(v[1]))
    if abs(dx) + abs(dy) > max_px:
        return c
    return np.asarray(c, float) - np.array([dx, dy]) * u


def card_box(ps, spr, side):
    x0, y0, x1, y1 = ink_of(spr)
    ax, ay = spr[1]
    X, Y = card_anchor(ps, spr, side)
    return (X - ax + x0, Y - ay + y0, X - ax + x1, Y - ay + y1)


def card_extent_pts(pm, spr, side, u):
    """4 góc hộp thẻ (mét Mercator) khi ghim ở pm và tỉ lệ u — để khớp khung chừa trọn thẻ."""
    b = card_box(np.array([0.0, 0.0]), spr, side)
    return [pm + np.array([b[0] - 20, b[1] - 20]) * u, pm + np.array([b[2] + 20, b[3] + 20]) * u]


def fit_with_labels(base_pts, poi_pts, k, half_w=170, up=150, card=None, **kw):
    """khớp khung chừa chỗ cho NHÃN của các ghim (nhãn ~340 px rộng, nằm trên ghim): lượt 1 khớp điểm,
    lượt 2 thêm các điểm ghim ± half_w px ngang và − up px dọc theo u của lượt 1 rồi khớp lại."""
    pts = np.vstack([np.asarray(base_pts, float).reshape(-1, 2)] + ([np.asarray(poi_pts, float).reshape(-1, 2)] if len(poi_pts) else []))
    c, u = fit_view(pts, k, **kw)
    if not len(poi_pts) and card is None:
        return c, u
    for _ in range(3):
        aug = []
        for q in np.asarray(poi_pts, float).reshape(-1, 2):
            aug += [q + [half_w * u, -up * u], q + [-half_w * u, -up * u]]
        if card is not None:                           # thẻ dự án phải TRỌN trong khung (AEON: thẻ cụt mép phải, 17/10)
            aug += card_extent_pts(card[0], card[1], card[2], u)
        c, u = fit_view(np.vstack([pts] + ([np.array(aug)] if aug else [])), k, **kw)
    return c, u


def to_screen(m, c, u):
    m = np.asarray(m, float)
    return (m - c) / u + np.array([C.W / 2, C.H / 2])


# ================================================================== đặt chữ
class Layout:
    def __init__(self):
        self.boxes = []          # (x0,y0,x1,y1, nặng)
        self.lines = np.zeros((0, 2))
        self.pins = []           # tâm ghim đang hiện (màn hình) — nhãn phải gần ghim CỦA NÓ hơn mọi ghim khác
        self.safe = [C.SAFE_X0, C.SAFE_Y0, C.SAFE_X1, C.SAFE_Y1]   # vùng an toàn (thu hẹp theo cả thời gian nhãn hiện)

    def add_box(self, b, w=1.0):
        self.boxes.append((*b, w))

    def add_pin(self, q):
        self.pins.append(np.asarray(q, float))

    def add_line(self, pts):
        if len(pts):
            self.lines = np.vstack([self.lines, pts])

    def score(self, b, allow_x=False):
        x0, y0, x1, y1 = b
        s = 0.0
        # ra khỏi vùng an toàn (allow_x: nhãn của ghim sát mép trái/phải được tràn ngang — EDGE_FIT)
        sx0, sy0, sx1, sy1 = self.safe
        out_x = 0 if allow_x else max(0, sx0 - x0) + max(0, x1 - sx1)
        out = out_x + max(0, sy0 - y0) + max(0, y1 - sy1)
        s += out * 40
        area = max(1.0, (x1 - x0) * (y1 - y0))
        for a0, b0, a1, b1, w in self.boxes:
            ix = max(0, min(x1, a1) - max(x0, a0)); iy = max(0, min(y1, b1) - max(y0, b0))
            s += 400 * w * ix * iy / area
        if len(self.lines):
            L = self.lines
            inside = (L[:, 0] > x0 - 4) & (L[:, 0] < x1 + 4) & (L[:, 1] > y0 - 4) & (L[:, 1] < y1 + 4)
            s += 0.6 * inside.sum()
        return s


def label_box(anchor, size, anc, off):
    """box màn hình khi neo (anc của sprite) đặt tại anchor + off."""
    w, h = size
    ax, ay = anc
    x = anchor[0] + off[0] - ax
    y = anchor[1] + off[1] - ay
    return (x, y, x + w, y + h)


def place_poi(lay, p, spr, pin_h=74, near_only=False, allow_edge=False):
    arr, anc = spr
    h, w = arr.shape[:2]
    cands = [((0, -pin_h - 4), 0), ((w / 2 + 34, -pin_h / 2 + h / 2 - 10), 1.2), ((-w / 2 - 34, -pin_h / 2 + h / 2 - 10), 1.2),
             ((0, h + 26), 2.5), ((w / 2 + 20, -pin_h - 4), 1.8), ((-w / 2 - 20, -pin_h - 4), 1.8),
             ((w / 2 + 30, h + 20), 3.0), ((-w / 2 - 30, h + 20), 3.0),
             ((0, -pin_h - 4 - h * 0.9), 4.0), ((0, h + 26 + h * 0.9), 5.0),
             ((w / 2 + 34, -pin_h - 4 - h * 0.6), 4.5), ((-w / 2 - 34, -pin_h - 4 - h * 0.6), 4.5),
             ((w / 2 + 34, h + 60), 5.0), ((-w / 2 - 34, h + 60), 5.0)]
    if near_only:                                   # nhãn ngắn: chỉ 6 chỗ sát ghim — xa hơn thì người xem không biết nhãn của ghim nào
        cands = cands[:6]
    else:                                           # nhãn đầy đủ: chỉ các vị trí KỀ ghim (bỏ đường dẫn, user 17/10)
        cands = cands[:C.FULL_NEAR_SLOTS]
    own = np.array([p[0], p[1] - pin_h / 2])
    allow_x = allow_edge and (p[0] < C.EDGE_CROP_ZONE or p[0] > C.W - C.EDGE_CROP_ZONE)
    best = None
    for off, pen in cands:
        b = label_box(p, (w, h), anc, off)
        sc = lay.score(b, allow_x) + pen * 30
        # điểm gần nhất của hộp nhãn tới từng ghim: ghim khác gần hơn ghim mình → đọc nhầm
        cx = np.clip(own[0], b[0], b[2]); cy = np.clip(own[1], b[1], b[3])
        d_own = math.hypot(own[0] - cx, own[1] - cy)
        for q in lay.pins:
            if np.linalg.norm(q - p) < 4:
                continue
            qq = np.array([q[0], q[1] - pin_h / 2])
            ex = np.clip(qq[0], b[0], b[2]); ey = np.clip(qq[1], b[1], b[3])
            if math.hypot(qq[0] - ex, qq[1] - ey) + 12 < d_own:
                sc += C.WRONG_PIN_PENALTY
        if best is None or sc < best[0]:
            best = (sc, off, b)
    return best


# ================================================================== chính
plan_side_retry = []


def build(brief_path, work, side_override=None):
    msgs = []
    B = geo.load_json(brief_path)
    if side_override:
        B["phia_the"] = side_override
    bdir = os.path.dirname(os.path.abspath(brief_path))
    rel = lambda p: p if (p is None or os.path.isabs(p)) else os.path.join(bdir, p)
    proj_ll = tuple(B["vi_tri"])
    k = geo.scale_k(proj_ll[0])
    PM = geo.ll2m(*proj_ll)
    if B.get("vung"):
        VUNG["ll"] = [tuple(x) for x in B["vung"]]
        VUNG["m"] = geo.lls2m(VUNG["ll"])
    else:
        VUNG["ll"] = VUNG["m"] = None
    name = B["ten"]
    print(f"● Dự án: {name} @ {proj_ll[0]:.5f}, {proj_ll[1]:.5f}")

    # ---------------------------------------------------------- tuyến
    routes = {}
    print("● Lấy hình học tuyến…")
    dropped = []
    for key, spec in list(B["tuyen"].items()):
        st = spec.get("trang_thai", "van_hanh")
        if st not in C.STATUS_OK:                               # đang xây / chạy thử / quy hoạch → KHÔNG đưa lên
            dropped.append((key, spec.get("ten", key), st))
            B["tuyen"].pop(key)
            continue
        spec["diem"] = [d_ for d_ in spec.get("diem", []) if d_.get("trang_thai", "van_hanh") in C.STATUS_OK]
    for ch in B["chuong"]:
        ch["tuyen"] = [k_ for k_ in ch["tuyen"] if k_ in B["tuyen"]]
    B["chuong"] = [ch for ch in B["chuong"] if ch["tuyen"]]
    for key, nm, st in dropped:
        warn(msgs, f"BỎ tuyến {nm} — trạng thái '{st}', chưa vận hành (luật: chỉ đưa hạ tầng đã chạy)")
    for key, spec in list(B["tuyen"].items()):
        spec = dict(spec, _brief_dir=bdir)
        try:
            P, how = resolve_route(key, spec, proj_ll, work, msgs)
        except NotOperating as ex:
            warn(msgs, "BỎ " + str(ex))
            B["tuyen"].pop(key)
            for ch in B["chuong"]:
                ch["tuyen"] = [k_ for k_ in ch["tuyen"] if k_ != key]
            continue
        L = geo.cumlen(P)
        i, s_acc, q, d_acc = geo.nearest_on(P, PM)
        if spec.get("tu"):                                   # điểm bắt đầu vẽ do hồ sơ chỉ định
            _, s_acc, q, _ = geo.nearest_on(P, geo.ll2m(*spec["tu"]))
        if spec.get("tu_vung") and VUNG["m"] is not None:   # line xuất phát TỪ MÉP RANH khu quy hoạch: vẽ từ đầu nét,
            s_acc, d_acc = 0.0, 0.0                          # "theo tuyến" = độ dài nét (không cộng khoảng tâm khu → nét)
            spec["huong"] = "cuoi"
        if spec.get("den"):                                  # chỉ vẽ về phía điểm này
            tgt = geo.ll2m(*spec["den"])
            spec["huong"] = "dau" if np.linalg.norm(P[0] - tgt) < np.linalg.norm(P[-1] - tgt) else "cuoi"
        routes[key] = dict(key=key, name=spec.get("ten", key), label=spec.get("nhan"), label_sub=spec.get("nhan_phu"),
                           kind=spec.get("loai", "duong"), color=spec["mau"], P=P, L=L, how=how,
                           s_acc=float(s_acc), d_acc_km=d_acc / k / 1000, huong=spec.get("huong", "auto"),
                           pois_spec=spec.get("diem", []), icon=spec.get("icon"), ve_km=spec.get("ve_km"),
                           glow=bool(spec.get("phat_sang", B.get("duong_sang", False))),
                           # vùng đích (xã / cụm CN): khoanh vùng màu tuyến; an_net = vùng GIÁP ranh → không vẽ line
                           zone=(geo.lls2m(spec["vung_dich"]).astype(float) if spec.get("vung_dich") else None),
                           an_net=bool(spec.get("an_net")))
        tot = L[-1] / k / 1000
        print(f"  ✓ {key}: {routes[key]['name']} — {how}, {tot:.1f} km trong bán kính, cách dự án {d_acc / k / 1000:.2f} km")
        if d_acc / k > 2500:
            warn(msgs, f"tuyến {key} cách dự án {d_acc / k / 1000:.1f} km — icon sẽ bật ở điểm gần nhất trên tuyến, không phải tại dự án")

    # ---------------------------------------------------------- điểm
    pois = []
    for key, r in routes.items():
        for j, ps in enumerate(r["pois_spec"]):
            if "latlon" in ps:
                m = geo.ll2m(*ps["latlon"])
            elif "giao" in ps:
                other = routes[ps["giao"]]["P"]
                from scipy.spatial import cKDTree
                t = cKDTree(other)
                dd, ii = t.query(r["P"])
                m = (r["P"][int(np.argmin(dd))] + other[ii[int(np.argmin(dd))]]) / 2
                if dd.min() / k > 400:
                    warn(msgs, f"điểm giao {key}×{ps['giao']}: hai tuyến cách nhau gần nhất {dd.min() / k:.0f} m — không thật sự cắt nhau")
            elif "osm" in ps:
                q = (f'[out:json][timeout:120];nwr["name"~"{ps["osm"]}"]'
                     f'["highway"!~"{C.HIGHWAY_NOT_OPERATING}"]["railway"!~"^(construction|proposed)$"]'
                     f'({proj_ll[0] - 0.35},{proj_ll[1] - 0.35},{proj_ll[0] + 0.35},{proj_ll[1] + 0.35});out center;')
                hk = hashlib.md5(q.encode("utf-8")).hexdigest()[:12]
                cp = os.path.join(work, "osm", f"poi_{hk}.json")
                d = geo.load_json(cp) if os.path.exists(cp) else geo.overpass(q)
                geo.save_json(cp, d)
                pts = []
                for e in d.get("elements", []):
                    if "center" in e:
                        pts.append((e["center"]["lat"], e["center"]["lon"]))
                    elif "lat" in e:
                        pts.append((e["lat"], e["lon"]))
                if not pts:
                    raise SystemExit(f"⛔ OSM không có điểm '{ps['osm']}' — cho toạ độ tay (latlon).")
                m = geo.lls2m(pts).mean(0)
            elif ps.get("cuoi"):
                m = None                                     # cuối nét vẽ — gán sau khi biết đầu vẽ
            else:
                raise SystemExit(f"⛔ Điểm {ps} thiếu vị trí (latlon / giao / osm / cuoi).")
            pois.append(dict(route=key, idx=j, spec=ps, m=m, kind=ps.get("loai", "diem"),
                             lines=tuple(ps["ten"] if isinstance(ps["ten"], list) else [ps["ten"]]),
                             key=f"{key}.{j}"))

    # ---------------------------------------------------------- đầu vẽ (hướng) — phạm vi theo chương xác định sau
    for key, r in routes.items():
        L = r["L"]; s = r["s_acc"]
        sides = {"dau": s, "cuoi": L[-1] - s}
        h = r["huong"]
        if h == "auto":
            a, b = sides["dau"], sides["cuoi"]
            h = "both" if min(a, b) >= 0.25 * max(a, b) and min(a, b) > 1500 * k else ("dau" if a > b else "cuoi")
        r["dirs"] = ["dau", "cuoi"] if h == "both" else [h]

    # điểm "cuoi": gán tạm ở cuối hướng dài nhất
    for p in pois:
        r = routes[p["route"]]
        if p["m"] is None:
            p["m"] = r["P"][0] if "dau" in r["dirs"] and (len(r["dirs"]) == 1 or r["s_acc"] > r["L"][-1] - r["s_acc"]) else r["P"][-1]
        _, s, q, d = geo.nearest_on(r["P"], np.asarray(p["m"]))
        if r["zone"] is not None:                           # ghim giữa vùng: mốc thời gian + km theo CUỐI nét (mép vùng)
            s = r["L"][-1] if "cuoi" in r["dirs"] else 0.0
        p["s"] = float(s); p["m_on"] = q; p["off_km"] = d / k / 1000
        explicit = any(x in p["spec"] for x in ("latlon", "osm"))
        if explicit and d / k > C.POI_OFF_ROUTE_M:
            # điểm mốc nằm cách đường (sân vận động, sân bay, bến xe): ghim + khoảng cách theo VỊ TRÍ THẬT; mốc thời
            # gian vẫn theo chỗ icon chạy qua gần nhất (s). Ghim vào điểm gần nhất trên đường làm sai số km
            # (SVĐ Mỹ Đình: 0,8 km thay vì 1,6 km — The Matrix One 17/10).
            p["m_on"] = np.asarray(p["m"], float)
            if d / k > 3000:
                warn(msgs, f"điểm {' '.join(p['lines'])} cách tuyến {r['key']} {d / k / 1000:.1f} km — kiểm lại toạ độ hoặc tuyến")
        elif d / k > 600:
            warn(msgs, f"điểm {' '.join(p['lines'])} cách tuyến {r['key']} {d / k:.0f} m — kiểm lại toạ độ")
        # khoảng cách
        crow = geo.haversine(proj_ll, geo.m2ll(*p["m_on"])) / 1000     # tới chỗ GHIM thật (điểm mốc lệch đường → vị trí thật)
        if VUNG["m"] is not None:                                     # đối tượng là vùng (hồ, khu đất) → đo từ mép vùng
            crow = vung_dist_km(np.asarray(p["m_on"], float), k)
        along = r["d_acc_km"] + abs(s - r["s_acc"]) / k / 1000
        # mặc định CHIM BAY: tuyến lấy từ ảnh/vẽ tay hơi gợn làm "theo tuyến" phình 10–45 % (đo trên mẫu KB5)
        mode = p["spec"].get("cach_tinh") or "chim_bay"
        p["dist_crow"], p["dist_along"] = crow, along
        p["dist"] = along if mode == "theo_tuyen" else crow
        p["dist_mode"] = mode
        if "km" in p["spec"]:
            given = float(p["spec"]["km"])
            if abs(given - p["dist"]) / max(p["dist"], 0.1) > 0.15:
                warn(msgs, f"{' '.join(p['lines'])}: hồ sơ ghi ~{fmt_km(given)} km, đo được {fmt_km(p['dist'])} km "
                           f"({'theo tuyến' if mode == 'theo_tuyen' else 'chim bay'}) — đang in số hồ sơ")
            p["dist"] = given
        if p["spec"].get("an_khoang_cach"):
            p["sub"] = None
        elif p["spec"].get("phu"):
            p["sub"] = p["spec"]["phu"]
        elif VUNG["m"] is not None and p["dist"] < 0.005:
            p["sub"] = "nằm trong khu quy hoạch"
        else:
            p["sub"] = f"cách {name} ~{fmt_dist(p['dist'])}"

    card_full = SP.project_card(name, B.get("the_phu"), False, rel(B.get("logo")))
    card_mini = SP.project_card(name, None, True, rel(B.get("logo")))
    card_side = B.get("phia_the", "tren")             # chọn lại tự động sau khi biết đường nét (xem dưới)
    # ---------------------------------------------------------- chương: khung nhìn + phạm vi vẽ
    B["chuong"] = [ch for ch in B["chuong"] if ch["tuyen"]]
    chapters = []
    for ci, ch in enumerate(B["chuong"]):
        keys = ch["tuyen"]
        spot = bool(ch.get("spotlight"))
        # khu quy hoạch lớn (12.800 ha): ôm cả tâm khu thì mỗi chương nhìn xa ~13 km, line 1–4 km chỉ còn một vạch ngắn →
        # "khung_sat": chương toàn line xuất phát từ mép ranh chỉ khớp theo line + ghim (thẻ dự án được ra ngoài khung)
        tight = bool(B.get("khung_sat")) and not spot and all(B["tuyen"].get(k_, {}).get("tu_vung") for k_ in keys)
        pts = [] if tight else [PM]
        ext = {}
        for key in keys:
            r = routes[key]
            k_pois = [p for p in pois if p["route"] == key]
            for dname in r["dirs"]:
                sg = -1 if dname == "dau" else 1
                far = [abs(p["s"] - r["s_acc"]) for p in k_pois if (p["s"] - r["s_acc"]) * sg >= 0]
                if r.get("ve_km"):
                    e = r["ve_km"] * 1000 * k
                elif far:
                    e = max(max(far) + 2000 * k, ch.get("toi_thieu_km", 5) * 1000 * k)
                else:                                        # không có điểm: vẽ đủ dài để thấy hướng tuyến (mẫu: tới mép khung)
                    e = ch.get("toi_thieu_km_khong_diem", 10) * 1000 * k
                e = min(e, (r["s_acc"] if sg < 0 else r["L"][-1] - r["s_acc"]))
                ext[(key, dname)] = e
                s_end = r["s_acc"] + sg * e
                for ss in np.linspace(r["s_acc"], s_end, 30):
                    pts.append(geo.point_at(r["P"], r["L"], ss))
            for p in k_pois:
                pts.append(p["m_on"])
            if r["zone"] is not None:                        # khoanh vùng: cả vùng nằm trong khung chương
                pts.extend(r["zone"][::max(1, len(r["zone"]) // 120)])
        pts = np.array(pts)
        if spot:
            rmax = np.max(np.linalg.norm(pts - PM, axis=1))
            c, u = PM.copy(), (2 * rmax * 1.10) / (C.SAFE_X1 - C.SAFE_X0)
            c = c - np.array([0, (C.SAFE_Y0 + 150 + C.SAFE_Y1 - 40) / 2 - C.H / 2]) * u
        else:
            # kiểu A (user chốt 17/10): chừa chỗ cho nhãn từng ghim ở MỌI chương, không chỉ spotlight — ghim sát mép thì
            # nhãn bị đẩy lệch sang đứng cạnh ghim khác (GA MỄ TRÌ cách mép trái 187 px, Matrix One 17/10)
            poi_pts = np.array([p["m_on"] for p in pois if p["route"] in keys])
            if tight:                                    # chừa thêm ~600 m quanh line để thấy mép khu quy hoạch + đường xung quanh
                pad = 600 * k
                pts = np.vstack([pts, pts.min(0) - pad, pts.max(0) + pad])
            c, u = fit_with_labels(pts, poi_pts, k, card=None if tight else (PM, card_full, card_side))
            if tight and u < C.TIGHT_MIN_U * k:          # line ngắn (1,3 km) → zoom 2,9 m/px: cú bay giữa 2 chương xa nhau
                u = C.TIGHT_MIN_U * k                    # mất 7 s (ngưỡng máy quay êm) — giữ khung ≥ ~4,4 km bề ngang
            if tight:                                    # thẻ dự án nằm TRỌN trong khung hoặc RA HẲN ngoài, không lấp ló
                c = card_clear(c, u, PM, (card_full, card_mini), card_side)   # mép (9 px thẻ ở chương xã Bình Minh, 10/11)
        chapters.append(dict(i=ci, title=ch["ten"], keys=keys, spot=spot, c=c, u=u, ext=ext, rmax=float(np.max(np.linalg.norm(pts - PM, axis=1)))))

    # ---------------------------------------------------------- khung mở đầu + kết
    if B.get("phoi_canh"):
        pc = B["phoi_canh"]
        b = pc["bounds"]                       # [[lat_bắc, lon_tây], [lat_nam, lon_đông]]
        m0, m1 = geo.ll2m(*b[0]), geo.ll2m(*b[1])
        intro_c, intro_u = fit_view([m0, m1], k, top=C.SAFE_Y0 + 380, bottom=C.SAFE_Y1 - 250, margin=0.0)
        intro_u *= 1.02                                  # mẫu: lô chiếm ~72 % bề ngang
    else:
        intro_c, intro_u = PM.copy(), 2200 * k / C.W
        if VUNG["m"] is not None:                         # vùng lớn: khung mở đầu ôm trọn vùng (Hồ Tây ~5 km²)
            vc, vu = fit_view(VUNG["m"], k, top=C.SAFE_Y0 + 420, bottom=C.SAFE_Y1 - 200, margin=0.06)
            intro_c, intro_u = (vc, vu) if vu > intro_u else (intro_c, intro_u)
    intro_c = intro_c.copy()
    if not B.get("phoi_canh"):
        # khung mở đầu: dự án đứng giữa khung → thẻ đầy đủ phía trái/phải lố vùng an toàn khi dòng phụ dài
        # ("Số 1 Lê Quang Đạo · Nam Từ Liêm" rộng 478 px > 466 px nửa khung, Matrix One 18/10) → lệch tâm máy quay cho thẻ nằm trọn
        cb = card_box(to_screen(PM, intro_c, intro_u), card_full, card_side)
        dx = max(0.0, C.SAFE_X0 + 4 - cb[0]) - max(0.0, cb[2] - (C.SAFE_X1 - 4))
        intro_c[0] -= dx * intro_u

    # ---------------------------------------------------------- dòng thời gian
    cam = []
    sfx = []
    t = 0.0
    cover = None
    if B.get("tieu_de"):
        cover = dict(lines=list(B["tieu_de"]), sub=B.get("tieu_de_phu"), t0=0.0, t1=C.COVER_HOLD + C.COVER_FADE)
        sfx.append(dict(t=0.05, name="cover"))
    intro_end = (cover["t1"] if cover else 0.6) + C.INTRO_HOLD
    if B.get("phoi_canh"):
        intro_end = max(intro_end, C.PLAN_XFADE[1] + 1.0)
    cam.append(dict(t0=0.0, t1=intro_end, c0=intro_c.tolist(), u0=intro_u, c1=intro_c.tolist(), u1=intro_u, mode="hold"))
    t = intro_end
    cur_c, cur_u = intro_c, intro_u
    heads, labels_route, poi_t = [], [], {}
    chapter_rows = []
    max_pan = max_zoom = 0.0
    for ch in chapters:
        D, pmax, zmax = min_move(cur_c, cur_u, ch["c"], ch["u"], k)
        max_pan, max_zoom = max(max_pan, pmax), max(max_zoom, zmax)
        cam.append(dict(t0=t, t1=t + D, c0=list(cur_c), u0=cur_u, c1=list(ch["c"]), u1=ch["u"], mode="move"))
        zr = max(cur_u, ch["u"]) / min(cur_u, ch["u"])
        if zr >= 1.6 or np.linalg.norm(ch["c"] - cur_c) / ch["u"] > 500:
            sfx.append(dict(t=t + D * 0.5, name="move"))
        t_arr = t + D
        ch["t_title"] = t + min(0.3, D * 0.45)         # chữ chương hiện ngay khi chữ cũ tắt (0,3 s vào cú bay) — không để khe chết
        sfx.append(dict(t=ch["t_title"], name="chapter"))
        tr = t_arr + C.FIRST_POP
        if ch["spot"]:
            ch["t_spot"] = t_arr
            sfx.append(dict(t=t_arr + 0.1, name="spot"))
            tr = t_arr + C.SPOT_GROW * 0.6
        ends = []
        for key in ch["keys"]:
            r = routes[key]
            # độ dài trên màn hình của đầu dài nhất (ở khung cuối chương)
            lens = []
            for dname in r["dirs"]:
                e = ch["ext"][(key, dname)]
                lens.append(e / ch["u"])
            Dr = float(np.clip(max(lens) / C.DRAW_SPEED, C.DRAW_MIN, C.DRAW_MAX))
            if r["an_net"]:                                  # vùng giáp ranh: không có line → vùng hiện ngay
                Dr = C.DRAW_MIN
            t_pop = tr
            t0 = tr + C.ICON_WAIT
            t_pop0, t00 = t_pop, t0
            delay2 = C.SECOND_DIR_DELAY
            for di, dname in enumerate(r["dirs"]):
                e = ch["ext"][(key, dname)]
                sg = -1 if dname == "dau" else 1
                Dd = Dr * (e / ch["u"]) / max(lens) if max(lens) > 0 else Dr
                Dd = max(Dd, min(Dr, C.DRAW_MIN))
                if di == 0 and len(r["dirs"]) > 1:
                    # icon chiều 2 chỉ bật khi icon chiều 1 đã chạy ra ≥ 85 px — trễ cố định 0,3 s vẫn chồng khít vì nét
                    # khởi động chậm (ease sin), Đại lộ Thăng Long 17/10
                    e_px = e / ch["u"]
                    # + (t0 − t_pop): icon 1 đứng yên 0,25 s sau khi bật rồi mới chạy
                    delay2 = max(C.SECOND_DIR_DELAY, (t00 - t_pop0) + Dd * ease_draw_inv(min(1.0, C.ICON_R * 2.6 / max(e_px, 1.0))))
                t_pop, t0 = t_pop0 + delay2 * di, t00 + delay2 * di
                heads.append(dict(route=key, chapter=ch["i"], s0=r["s_acc"], s1=r["s_acc"] + sg * e, t_pop=t_pop, t0=t0, t1=t0 + Dd,
                                  icon=r["icon"] or ("metro" if r["kind"] == "metro" else "sanbay" if r["kind"] == "sanbay" else "duong")))
                ends.append(t0 + Dd)
                if not r["an_net"]:
                    sfx.append(dict(t=t_pop + 0.02 + 0.06 * di, name="icon" if di == 0 else "icon2"))
                # thời điểm đầu vẽ chạm từng điểm
                for p in pois:
                    if p["route"] != key or (p["s"] - r["s_acc"]) * sg < 0 or p["key"] in poi_t:
                        continue
                    frac = abs(p["s"] - r["s_acc"]) / e if e > 0 else 1
                    if frac > 1.0:
                        warn(msgs, f"điểm {' '.join(p['lines'])} nằm ngoài đoạn vẽ của chương — hiện ở cuối nét")
                        frac = 1.0
                    poi_t[p["key"]] = t0 + Dd * ease_draw_inv(frac) + 0.04
                    sfx.append(dict(t=poi_t[p["key"]], name="airport" if p["kind"] == "sanbay" else "label"))
            if r["label"]:
                hd = [h for h in heads if h["route"] == key]
                hmain = max(hd, key=lambda h: abs(h["s1"] - h["s0"]))
                labels_route.append(dict(route=key, chapter=ch["i"], t=hmain["t0"] + (hmain["t1"] - hmain["t0"]) * ease_draw_inv(0.45),
                                         s=hmain["s0"] + (hmain["s1"] - hmain["s0"]) * 0.5, text=r["label"], sub=r["label_sub"]))
            tr = tr + C.NEXT_AT * (C.ICON_WAIT + Dr)
        last_lbl = max([poi_t[p["key"]] for p in pois if p["route"] in ch["keys"] and p["key"] in poi_t] +
                       [lr["t"] for lr in labels_route if lr["chapter"] == ch["i"]] + [0])
        t_end = max(max(ends) + C.CHAPTER_TAIL, last_lbl + C.READ_TIME)
        ch["t_end"] = t_end
        # spotlight: camera trôi ra theo vòng tròn
        if ch["spot"]:
            ts = np.arange(t_arr, t_end + 1e-6, 0.2)
            rr = []
            for tt in ts:
                rmax = 0.0
                for h in heads:
                    if h["chapter"] != ch["i"] or tt < h["t0"]:
                        continue
                    e = ease_draw((tt - h["t0"]) / (h["t1"] - h["t0"]))
                    s_now = h["s0"] + (h["s1"] - h["s0"]) * e
                    r_ = routes[h["route"]]
                    for ss in np.linspace(h["s0"], s_now, 12):
                        rmax = max(rmax, float(np.linalg.norm(geo.point_at(r_["P"], r_["L"], ss) - PM)))
                rr.append(rmax)
            rr = np.maximum.accumulate(np.array(rr)) * 1.08 + 900 * k
            ch["spot_r"] = [[float(a), float(b)] for a, b in zip(ts, rr)]
            # máy quay khớp NỘI DUNG ĐANG HIỆN (dự án + nét đã vẽ + điểm đã/sắp bật) — không ép tâm vào dự án,
            # vòng tròn được lệch/tràn mép như mẫu. u chỉ tăng; tâm lọc trung bình 1 s cho êm.
            cs, us = [], []
            for tt in ts:
                vis = [PM]
                vis_poi = []
                for h in heads:
                    if h["chapter"] != ch["i"] or tt + 0.6 < h["t0"]:
                        continue
                    e = ease_draw((tt + 0.6 - h["t0"]) / (h["t1"] - h["t0"]))
                    r_ = routes[h["route"]]
                    s_now = h["s0"] + (h["s1"] - h["s0"]) * e
                    vis += [geo.point_at(r_["P"], r_["L"], ss) for ss in np.linspace(h["s0"], s_now, 16)]
                for p in pois:
                    if p["route"] in ch["keys"] and p["key"] in poi_t and poi_t[p["key"]] <= tt + 0.6:
                        vis_poi.append(p["m_on"])
                if C.EDGE_FIT:                                   # như mẫu: nội dung chạm mép khung, nhãn ở mép được cắt
                    c_t, u_t = fit_view(np.vstack([np.array(vis)] + ([np.array(vis_poi)] if vis_poi else [])), k,
                                        top=C.SAFE_Y0 + 260, bottom=C.SAFE_Y1 - 150, margin=0.0, edge=True)
                else:
                    c_t, u_t = fit_with_labels(np.array(vis), np.array(vis_poi), k, card=(PM, card_mini, card_side),
                                               top=C.SAFE_Y0 + 260, bottom=C.SAFE_Y1 - 150, margin=0.08)
                cs.append(c_t); us.append(u_t)
            us = np.maximum.accumulate(np.maximum(np.array(us), ch["u"] * 0.30))
            cs = np.array(cs)
            win = max(1, int(round(1.0 / 0.2)))
            pad = np.vstack([np.repeat(cs[:1], win, 0), cs, np.repeat(cs[-1:], win, 0)])
            ker = np.ones(2 * win + 1) / (2 * win + 1)
            cs = np.stack([np.convolve(pad[:, i], ker, "valid") for i in range(2)], 1)[:len(ts)]
            u_need = us
            for i in range(1, len(u_need)):
                lim = u_need[i - 1] * (1 + C.MAX_ZOOM_PCT / 100 * 0.25) ** (0.2 * C.FPS)
                u_need[i] = min(u_need[i], lim)
            ch["u_end"] = float(u_need[-1])
            # ghép vào camera: cú bay vào chương kết thúc đúng khung đầu của chuỗi trôi
            ch["c"] = cs[0]; ch["u"] = float(u_need[0])
            D2, pm2, zm2 = min_move(np.array(cam[-1]["c0"]), cam[-1]["u0"], cs[0], ch["u"], k)
            cam[-1]["c1"] = list(cs[0]); cam[-1]["u1"] = ch["u"]
            prev_t, prev_u, prev_c = t_arr, float(u_need[0]), cs[0]
            for tt, uu, cc_ in zip(ts[1:], u_need[1:], cs[1:]):
                cam.append(dict(t0=float(prev_t), t1=float(tt), c0=list(prev_c), u0=prev_u, c1=list(cc_), u1=float(uu), mode="lin"))
                prev_t, prev_u, prev_c = tt, float(uu), cc_
            ch["c_end"] = cs[-1]
            # vòng km
            # bậc "tròn" như mẫu (5/10/20/30); tối đa 4 vòng, giữ vòng ngoài cùng
            rings = [x for x in (1, 2, 5, 10, 20, 30, 50, 80) if x * 1000 * k <= rr[-1] * 1.02]
            rings = rings[-4:]
            ch["rings"] = []
            for x in rings:
                rm = x * 1000 * k
                idx = int(np.argmax(rr >= rm)) if (rr >= rm).any() else len(rr) - 1
                ch["rings"].append(dict(km=x, r=rm, t=float(ts[idx])))
            cur_u = ch["u_end"]
        else:
            cam.append(dict(t0=t_arr, t1=t_end, c0=list(ch["c"]), u0=ch["u"], c1=list(ch["c"]), u1=ch["u"], mode="hold"))
            ch["u_end"] = ch["u"]
            cur_u = ch["u"]
        cur_c = ch.get("c_end", ch["c"])
        t = t_end
        chapter_rows.append((ch["title"], t_arr, t_end, D))

    # ---------------------------------------------------------- kết: toàn cảnh + chú giải
    allpts = [PM]
    for h in heads:
        r = routes[h["route"]]
        for ss in np.linspace(h["s0"], h["s1"], 40):
            allpts.append(geo.point_at(r["P"], r["L"], ss))
    if C.EDGE_FIT:                                       # như mẫu: mạng tuyến chạm mép trái/phải
        oc, ou = fit_view(np.vstack([np.array(allpts)] + [np.array([p["m_on"] for p in pois])]), k,
                          top=C.SAFE_Y0 + 330, bottom=C.SAFE_Y1 - 30, margin=0.0, edge=True)
    else:
        oc, ou = fit_with_labels(np.array(allpts), np.array([p["m_on"] for p in pois if not p["spec"].get("an_o_ket")]), k,
                                 half_w=130, up=110, card=(PM, card_mini, card_side),
                                 top=C.SAFE_Y0 + 330, bottom=C.SAFE_Y1 - 30, margin=0.06)   # chừa chỗ tên ngắn
    D, pmax, zmax = min_move(cur_c, cur_u, oc, ou, k)
    max_pan, max_zoom = max(max_pan, pmax), max(max_zoom, zmax)
    t_out0 = t + 0.35
    cam.append(dict(t0=t, t1=t_out0, c0=list(cur_c), u0=cur_u, c1=list(cur_c), u1=cur_u, mode="hold"))
    cam.append(dict(t0=t_out0, t1=t_out0 + D, c0=list(cur_c), u0=cur_u, c1=list(oc), u1=ou, mode="move"))
    if max(cur_u, ou) / min(cur_u, ou) >= 1.6:
        sfx.append(dict(t=t_out0 + D * 0.5, name="move"))
    t_arr = t_out0 + D
    legend_t = t_out0 + D * 0.5                      # chú giải hiện giữa cú lùi máy cuối (cũ: tới nơi + 0,25 s → khe chờ 3 s)
    sfx.append(dict(t=legend_t, name="legend"))
    T = legend_t + C.LEGEND_IN + C.OUTRO_HOLD
    end_card = None
    if B.get("khung_ket"):
        kk = B["khung_ket"]
        end_card = dict(line1=kk.get("dong1", name), line2=kk.get("dong2"), t=T - 0.6)
        T += 2.2
    cam.append(dict(t0=t_arr, t1=T, c0=list(oc), u0=ou, c1=list(oc), u1=ou, mode="hold"))

    # ---------------------------------------------------------- đặt chữ theo từng chương (ở khung cuối chương)
    switch_u = C.CARD_MINI_KM * 1000 * k / C.W           # khung rộng hơn chừng này → thẻ thu gọn thành chip
    if not B.get("phia_the"):
        # chọn 1 phía cho thẻ dự án cả video: ít điểm nét tuyến nằm dưới thẻ nhất, đo ở khung cuối mỗi chương + khung kết
        # (thẻ ở trên che mất đoạn Lê Quang Đạo đi lên SVĐ — user 17/10 "đoạn màu đỏ này là thiếu")
        probe_t = [c_["t_end"] - 0.01 for c_ in chapters] + [T - 0.01, 1.0] + \
                  [(sg["t0"] + sg["t1"]) / 2 for sg in cam if sg["mode"] == "move"]   # cả mở đầu + lúc bay (thẻ tràn mép, Landmark 81)
        sc_side = {}
        for side in C.CARD_SIDES:
            tot = 0
            for tt in probe_t:
                c_, u_ = camera_at(cam, tt, k)
                ps_ = to_screen(PM, c_, u_)
                spr_ = card_full if u_ < switch_u else card_mini
                bx = card_box(ps_, spr_, side)
                for h in heads:
                    if tt < h["t0"]:
                        continue
                    r = routes[h["route"]]
                    pts_ = np.array([to_screen(geo.point_at(r["P"], r["L"], ss), c_, u_) for ss in np.linspace(h["s0"], h["s1"], 160)])
                    tot += int(((pts_[:, 0] > bx[0] - 6) & (pts_[:, 0] < bx[2] + 6) & (pts_[:, 1] > bx[1] - 6) & (pts_[:, 1] < bx[3] + 6)).sum())
                if bx[0] < C.SAFE_X0 or bx[2] > C.SAFE_X1 or bx[1] < C.SAFE_Y0 or bx[3] > C.SAFE_Y1:
                    tot += 400
            sc_side[side] = tot + C.CARD_SIDES.index(side) * 3
        best_side = min(sc_side, key=sc_side.get)
        if best_side != card_side:
            msgs.append(f"(thẻ dự án đặt phía «{best_side}» — ít đè nét nhất: " + ", ".join(f"{a} {b}" for a, b in sc_side.items()) + ")")
            plan_side_retry.append(best_side)
    holds = [sg["u0"] for sg in cam if sg["mode"] in ("hold", "lin")]
    for _ in range(6):                                   # tránh khung đứng yên nằm trong dải hoà ±8 % (thẻ hiện chồng 2 bản)
        bad = [hu for hu in holds if abs(hu / switch_u - 1) < 0.08]
        if not bad:
            break
        switch_u = min(bad) * 0.88
    poi_layout = {}
    poi_short = {}
    poi_collapse = {}
    label_t = {}                                         # lúc NHÃN hiện (có thể trễ hơn lúc ghim bật nếu phải chờ nhãn cũ nhường)
    route_layout = {}
    for p in pois:
        tn = p["spec"].get("ten_ngan")
        p["short"] = tuple(tn) if isinstance(tn, list) else ((tn,) if tn else (p["lines"][0],))

    def drawn_lines(tt, c_, u_):
        out = []
        for h in heads:
            if tt < h["t0"]:
                continue
            e = ease_draw((tt - h["t0"]) / (h["t1"] - h["t0"]))
            r = routes[h["route"]]
            s_now = h["s0"] + (h["s1"] - h["s0"]) * e
            out.append(np.array([to_screen(geo.point_at(r["P"], r["L"], ss), c_, u_) for ss in np.linspace(h["s0"], s_now, 80)]))
        return out
    def add_card_lifetime(L, p, q_ref, t0_, t1_):
        """hộp thẻ dự án ở vài thời điểm trong [t0_, t1_], quy về hệ toạ độ của ghim p tại khung tham chiếu (q_ref)."""
        for tt_ in np.linspace(t0_ + 0.05, max(t0_ + 0.06, t1_ + 0.25), 12):   # tới hết lúc mờ dần
            c_s, u_s = camera_at(cam, tt_, k)
            ps_s = to_screen(PM, c_s, u_s)
            q_s = to_screen(p["m_on"], c_s, u_s)
            cb = card_box(ps_s, card_full if u_s < switch_u else card_mini, card_side)
            d_ = np.asarray(q_ref) - q_s
            L.add_box((cb[0] + d_[0], cb[1] + d_[1], cb[2] + d_[0], cb[3] + d_[1]), C.CARD_HARD)
            # vùng an toàn lúc tt_ quy về khung tham chiếu → giao lại (nhãn không trôi ra mép khi máy còn lùi — Hồ Tây 17/10)
            L.safe = [max(L.safe[0], C.SAFE_X0 + d_[0]), max(L.safe[1], C.SAFE_Y0 + d_[1]),
                      min(L.safe[2], C.SAFE_X1 + d_[0]), min(L.safe[3], C.SAFE_Y1 + d_[1])]

    title_layout = {}
    drawn_so_far = []
    for ch in chapters:
        cc, uu = camera_at(cam, ch["t_end"] - 0.01, k)
        lay = Layout()
        ps = to_screen(PM, cc, uu)
        cspr = card_full if uu < switch_u else card_mini
        lay.add_box(card_box(ps, cspr, card_side), C.CARD_HARD)
        lay.add_box((ps[0] - 22, ps[1] - 22, ps[0] + 22, ps[1] + 22), 3)
        for h in heads:
            if h["chapter"] <= ch["i"]:
                r = routes[h["route"]]
                pts = np.array([to_screen(geo.point_at(r["P"], r["L"], ss), cc, uu) for ss in np.linspace(h["s0"], h["s1"], 120)])
                lay.add_line(pts)
        for q_ in pois:                                  # ghim đang hiện là vật cản cho cả chữ chương (đè ghim SVĐ, 17/10)
            if q_["key"] in poi_t and poi_t[q_["key"]] <= ch["t_end"]:
                qq = to_screen(q_["m_on"], cc, uu)
                lay.add_box((qq[0] - 28, qq[1] - 80, qq[0] + 28, qq[1] + 8), 3)
        # chữ chương
        tspr = SP.chapter_title(ch["title"])
        th, tw = tspr[0].shape[:2]
        cands = [(C.W / 2, C.SAFE_Y0 + 95), (C.SAFE_X0 + tw / 2 + 10, C.SAFE_Y0 + 95), (C.SAFE_X1 - tw / 2 - 10, C.SAFE_Y0 + 95),
                 (C.W / 2, C.SAFE_Y0 + 185), (C.SAFE_X0 + tw / 2 + 10, C.SAFE_Y0 + 185), (C.SAFE_X1 - tw / 2 - 10, C.SAFE_Y0 + 185),
                 (C.W / 2, C.SAFE_Y1 - 110), (C.SAFE_X0 + tw / 2 + 10, C.SAFE_Y1 - 110), (C.SAFE_X1 - tw / 2 - 10, C.SAFE_Y1 - 110),
                 (C.W / 2, C.H * 0.40), (C.W / 2, C.H * 0.62)]
        best = None
        for j, (x, y) in enumerate(cands):
            b = (x - tw / 2 + 30, y - th / 2 + 25, x + tw / 2 - 30, y + th / 2 - 25)
            sc = lay.score(b) + j * 3
            if best is None or sc < best[0]:
                best = (sc, (x, y), b)
        if best[0] > 60:
            warn(msgs, f"chữ chương «{ch['title']}» chật chỗ (chồng lấn {best[0]:.0f})")
        title_layout[ch["i"]] = [float(best[1][0]), float(best[1][1])]
        lay.add_box(best[2], 2)
        tb = best[2]
        # ---- nhãn tuyến TRƯỚC (dò dọc nét, lệch vuông góc) — làm vật cản cho nhãn điểm
        pin_bx = []
        for q_ in pois:
            if q_["key"] in poi_t and poi_t[q_["key"]] <= ch["t_end"]:
                qq = to_screen(q_["m_on"], cc, uu)
                lay.add_box((qq[0] - 24, qq[1] - 76, qq[0] + 24, qq[1] + 6), 2)
                pin_bx.append((qq[0] - 30, qq[1] - 82, qq[0] + 30, qq[1] + 10))
        base_boxes, base_lines = list(lay.boxes), lay.lines.copy()      # cho lượt 2 đặt lại nhãn tuyến (xem cuối chương)
        for q_ in pois:                                  # nhãn tuyến tránh xa ghim điểm — chỗ đó dành cho tên ga/cầu
            if q_["route"] in ch["keys"] and q_["key"] in poi_t:
                qq = to_screen(q_["m_on"], cc, uu)
                lay.add_box((qq[0] - 190, qq[1] - 240, qq[0] + 190, qq[1] + 60), 1.5)
        def box_dist(bx, P_):
            dx = np.maximum(np.maximum(bx[0] - P_[:, 0], 0), P_[:, 0] - bx[2])
            dy = np.maximum(np.maximum(bx[1] - P_[:, 1], 0), P_[:, 1] - bx[3])
            return float(np.min(np.hypot(dx, dy))) if len(P_) else 1e9

        scr_lines = {}
        for h in heads:
            if h["chapter"] <= ch["i"]:
                r = routes[h["route"]]
                scr_lines.setdefault(h["route"], []).append(
                    np.array([to_screen(geo.point_at(r["P"], r["L"], ss), cc, uu) for ss in np.linspace(h["s0"], h["s1"], 160)]))
        scr_lines = {k_: np.vstack(v) for k_, v in scr_lines.items()}
        def place_route_label(L, lr):
            r = routes[lr["route"]]
            spr = SP.route_label(lr["text"], r["color"], lr["sub"])
            h_, w_ = spr[0].shape[:2]
            # dò CẢ HAI nhánh vẽ (tuyến vẽ 2 chiều), nhánh dài được ưu tiên nhẹ — chỉ dò nhánh dài thì hết chỗ, TUYẾN 3 phải
            # chọn giữa đè ghim SVĐ và đè nhãn GA ĐHQG trong khi nhánh đông còn trống (Matrix One 18/10)
            hds = sorted([h for h in heads if h["route"] == lr["route"]], key=lambda h: -abs(h["s1"] - h["s0"]))
            best_r = None
            for hi, hd, fr in [(hi, hd, fr) for hi, hd in enumerate(hds) for fr in (0.35, 0.5, 0.65, 0.8, 0.25, 0.15, 0.9)]:
                s_ = hd["s0"] + (hd["s1"] - hd["s0"]) * fr
                a = to_screen(geo.point_at(r["P"], r["L"], s_), cc, uu)
                b2 = to_screen(geo.point_at(r["P"], r["L"], s_ + 200 * k * np.sign(hd["s1"] - hd["s0"])), cc, uu)
                tv = b2 - a
                nv = np.array([-tv[1], tv[0]]) / (np.linalg.norm(tv) + 1e-9)
                for sgn in (1, -1):
                    cpos = a + nv * sgn * (h_ / 2 + 22) + nv * sgn * abs(nv[0]) * (w_ / 2 - h_ / 2) * 0.9
                    bx = (cpos[0] - w_ / 2, cpos[1] - h_ / 2, cpos[0] + w_ / 2, cpos[1] + h_ / 2)
                    sc = L.score(bx) + abs(fr - 0.5) * 20 + hi * 8
                    # ghim là vật cản CỨNG: phạt theo tỷ lệ diện tích thì chạm mép ghim chỉ ~20 điểm, thua vùng chừa cho nhãn ga
                    # (~600) → "Nhổn – Cầu Giấy" đè đầu ghim SVĐ (Matrix One 18/10)
                    if any(min(bx[2], p_[2]) > max(bx[0], p_[0]) and min(bx[3], p_[3]) > max(bx[1], p_[1]) for p_ in pin_bx):
                        sc += C.LABEL_ON_PIN_PENALTY
                    # nhãn tuyến đứng cạnh NÉT KHÁC hơn nét của mình → đọc nhầm (LÊ QUANG ĐẠO nằm trên Đại lộ Thăng Long, 17/10)
                    d_own = box_dist(bx, scr_lines.get(lr["route"], np.zeros((0, 2))))
                    for k2, P2 in scr_lines.items():
                        if k2 != lr["route"] and box_dist(bx, P2) + 10 < d_own:
                            sc += C.WRONG_PIN_PENALTY
                    if best_r is None or sc < best_r[0]:
                        best_r = (sc, s_, (cpos - a).tolist(), bx, hd)
            hd = best_r[4]
            lr["s"] = float(best_r[1]); lr["off"] = best_r[2]
            lr["t"] = hd["t0"] + (hd["t1"] - hd["t0"]) * ease_draw_inv(min(1, abs(best_r[1] - hd["s0"]) / max(abs(hd["s1"] - hd["s0"]), 1))) + 0.05
            L.add_box(best_r[3], 2)
            route_layout[lr["route"]] = best_r[2]
            return best_r[0]

        ch_rlabels = [x for x in labels_route if x["chapter"] == ch["i"]]
        for lr in ch_rlabels:
            place_route_label(lay, lr)

        def base_layout(tt):
            c_, u_ = camera_at(cam, tt, k)
            L2 = Layout()
            ps_ = to_screen(PM, c_, u_)
            cs_ = card_full if u_ < switch_u else card_mini
            L2.add_box(card_box(ps_, cs_, card_side), C.CARD_HARD)
            L2.add_box((ps_[0] - 22, ps_[1] - 22, ps_[0] + 22, ps_[1] + 22), 3)
            L2.add_box(tb, 2)
            L2.add_pin(ps_ + np.array([0, 37]))            # ghim dự án (neo nhãn = mũi ghim; tâm ghim dự án ≈ mũi − 37)
            for ln in drawn_lines(tt, c_, u_):
                L2.add_line(ln)
            for q_ in pois:                                        # ghim đang hiện (mọi chương)
                # ghim đang hiện HOẶC sẽ bật trong lúc nhãn này còn đứng — không thì nhãn đặt lên chỗ ghim sắp mọc
                # (GA PHÙNG KHOANG che ghim AEON Hà Đông, Matrix One 17/10)
                if q_["key"] in poi_t and poi_t[q_["key"]] <= tt + C.FULL_HOLD:
                    qq = to_screen(q_["m_on"], c_, u_)
                    L2.add_box((qq[0] - 24, qq[1] - 76, qq[0] + 24, qq[1] + 6), 2)
                    L2.add_pin(qq)
            for lr in ch_rlabels:                                  # nhãn tuyến đang hiện HOẶC sẽ hiện khi nhãn này còn đứng
                if lr["t"] <= tt + C.FULL_HOLD:
                    r = routes[lr["route"]]
                    a = to_screen(geo.point_at(r["P"], r["L"], lr["s"]), c_, u_) + np.array(lr["off"])
                    sp_ = SP.route_label(lr["text"], r["color"], lr["sub"])
                    hh, ww = sp_[0].shape[:2]
                    L2.add_box((a[0] - ww / 2, a[1] - hh / 2, a[0] + ww / 2, a[1] + hh / 2), 2)
            return c_, u_, L2

        # ---- nhãn điểm ĐẦY ĐỦ: đặt theo camera lúc hiện; nhãn cũ đang đứng chỗ đó thì NHƯỜNG (thu về tên ngắn sớm)
        cps = sorted([p for p in pois if p["route"] in ch["keys"] and p["key"] in poi_t], key=lambda p: poi_t[p["key"]])
        dense = len(cps) >= 4
        for p in cps:
            p["scale"] = 0.86 if dense else 1.0
        for p in cps:
            ti = poi_t[p["key"]]
            poi_collapse[p["key"]] = min(ti + C.FULL_HOLD, ch["t_end"])
            # chương spotlight: máy quay còn lùi ra trong lúc nhãn đứng → đặt theo khung LÚC NHÃN SẮP THU GỌN (cụm ghim chật
            # nhất); đặt theo lúc mới hiện thì về sau nhãn trôi đè lên cụm quanh dự án (CẦU NHẬT TÂN, Matrix One 17/10)
            tt = min(ti + C.FULL_HOLD, ch["t_end"]) - 0.01 if ch["spot"] else min(ti + 0.6, ch["t_end"])
            c_, u_, L2 = base_layout(tt)
            for q_ in cps:                                         # nhãn ngắn của điểm đã thu gọn trước đó
                if q_ is p or not poi_short.get(q_["key"]) or poi_collapse.get(q_["key"], 1e9) > tt:
                    continue
                qq = to_screen(q_["m_on"], c_, u_)
                sp_ = SP.poi_label(q_["short"], routes[q_["route"]]["color"], None, True)
                L2.add_box(label_box(qq, sp_[0].shape[1::-1], sp_[1], poi_short[q_["key"]]), 2)
            for q_ in cps:                                         # nhãn đầy đủ khác ĐANG đứng → né trước, chỉ nhường khi hết chỗ
                if q_ is p or q_["key"] not in poi_layout or poi_collapse[q_["key"]] <= ti:
                    continue
                qq = to_screen(q_["m_on"], c_, u_)
                sp_ = SP.poi_label(q_["lines"], routes[q_["route"]]["color"], q_["sub"], False, q_["scale"])
                L2.add_box(label_box(qq, sp_[0].shape[1::-1], sp_[1], poi_layout[q_["key"]]), 1.5)
            q = to_screen(p["m_on"], c_, u_)
            add_card_lifetime(L2, p, q, ti, min(ti + C.FULL_HOLD, ch["t_end"]))
            spr = SP.poi_label(p["lines"], routes[p["route"]]["color"], p["sub"], False, p["scale"])
            sc, off, b = place_poi(L2, q, spr, allow_edge=C.EDGE_FIT and ch["spot"])
            if sc > 150 and p["scale"] > 0.84:                  # chật → thử cỡ nhỏ hơn ở chỗ sát ghim
                spr2 = SP.poi_label(p["lines"], routes[p["route"]]["color"], p["sub"], False, 0.82)
                sc2, off2, b2 = place_poi(L2, q, spr2, allow_edge=C.EDGE_FIT and ch["spot"])
                if sc2 < sc:
                    p["scale"], sc, off, b, spr = 0.82, sc2, off2, b2, spr2
            if sc > C.FULL_FAIL_SCORE:
                # không có chỗ hợp lệ SÁT ghim → bỏ nhãn đầy đủ (đặt đại thì đứng cạnh ghim khác / tràn mép — Cầu Chương Dương,
                # Hồ Tây 17/10); chỉ còn tên ngắn ngay cạnh ghim nếu vừa, không thì chỉ còn ghim
                poi_collapse[p["key"]] = ti
                label_t[p["key"]] = ti
                warn(msgs, f"nhãn {' '.join(p['lines'])} (chương {ch['i'] + 1}) không có chỗ sát ghim (chồng lấn {sc:.0f}) — chỉ hiện tên ngắn")
                continue
            poi_layout[p["key"]] = [float(off[0]), float(off[1])]
            if sc > 150:
                warn(msgs, f"nhãn {' '.join(p['lines'])} (chương {ch['i'] + 1}) chật chỗ — điểm chồng lấn {sc:.0f}")
            for q_ in cps:                                         # nhãn đầy đủ cũ bị đè → nhường
                if q_ is p or q_["key"] not in poi_layout or poi_collapse[q_["key"]] <= ti:
                    continue
                qq = to_screen(q_["m_on"], c_, u_)
                sp_ = SP.poi_label(q_["lines"], routes[q_["route"]]["color"], q_["sub"], False, q_["scale"])
                ob = label_box(qq, sp_[0].shape[1::-1], sp_[1], poi_layout[q_["key"]])
                if min(ob[2], b[2]) - max(ob[0], b[0]) > 0 and min(ob[3], b[3]) - max(ob[1], b[1]) > 0:
                    poi_collapse[q_["key"]] = max(label_t.get(q_["key"], poi_t[q_["key"]]) + 1.2, ti - 0.35)
                    # nhãn mới hiện sau khi nhãn cũ mờ hết (0,3 s) — Keangnam mờ dần đè Bến xe 0,8 s (Matrix One 17/10)
                    label_t[p["key"]] = max(label_t.get(p["key"], ti), poi_collapse[q_["key"]] + 0.32)
            if label_t.get(p["key"], ti) > ti:
                poi_collapse[p["key"]] = min(max(label_t[p["key"]] + C.FULL_HOLD, poi_collapse[p["key"]]), ch["t_end"])
            # dành chỗ nhãn ngắn ngay khi thu gọn sớm
        # ---- nhãn NGẮN cho điểm thu gọn trước khi chương tắt: đặt ở camera cuối chương
        # nhãn ngắn hiện từ lúc thu gọn tới hết chương → phải né MỌI nhãn đầy đủ còn đứng trong khoảng đó (không chỉ
        # nhãn đứng tới cuối) và các nhãn ngắn đã đặt (GA LÊ ĐỨC THỌ ngắn đè GA MỄ TRÌ đầy đủ, Matrix One 17/10)
        c_e, u_e, _ = base_layout(ch["t_end"] - 0.01)
        placed_short = []
        for p in sorted(cps, key=lambda x: poi_collapse[x["key"]]):
            if poi_collapse[p["key"]] >= ch["t_end"] - 1e-6:
                poi_short.pop(p["key"], None)
                continue
            t_s = poi_collapse[p["key"]]
            _, _, Le = base_layout(ch["t_end"] - 0.01)
            for q_ in cps:
                if q_ is p or q_["key"] not in poi_layout:
                    continue
                if poi_t[q_["key"]] < ch["t_end"] and poi_collapse[q_["key"]] > t_s:      # khoảng hiện chồng nhau
                    qq = to_screen(q_["m_on"], c_e, u_e)
                    sp_ = SP.poi_label(q_["lines"], routes[q_["route"]]["color"], q_["sub"], False, q_["scale"])
                    Le.add_box(label_box(qq, sp_[0].shape[1::-1], sp_[1], poi_layout[q_["key"]]), 2)
            for b_ in placed_short:
                Le.add_box(b_, 2)
            q = to_screen(p["m_on"], c_e, u_e)
            add_card_lifetime(Le, p, q, poi_collapse[p["key"]], ch["t_end"])
            spr = SP.poi_label(p["short"], routes[p["route"]]["color"], None, True)
            sc, off, b = place_poi(Le, q, spr, near_only=True, allow_edge=C.EDGE_FIT and ch["spot"])
            if sc > C.SHORT_MAX_SCORE:                 # không có chỗ sát ghim → ẩn tên ngắn (ghim vẫn còn)
                poi_short.pop(p["key"], None)
                continue
            poi_short[p["key"]] = [float(off[0]), float(off[1])]
            placed_short.append(b)
        # ---- lượt 2: đặt LẠI nhãn tuyến khi đã biết chỗ thật của nhãn điểm (đầy đủ + tên ngắn). Lượt 1 chỉ đoán bằng vùng chừa
        # quanh ghim, không phủ hết 8 chỗ kề ghim → "VÀNH ĐAI 3" đè "TT HỘI NGHỊ" (nhãn nằm DƯỚI ghim), "TUYẾN 3" đè "GA ĐHQG"
        # (Matrix One 18/10). Nhãn tuyến dò được dọc cả nét nên nhường cho nhãn điểm (chỉ có chỗ kề ghim).
        if ch_rlabels:
            L = Layout()
            L.boxes, L.lines = list(base_boxes), base_lines.copy()
            for q_ in cps:
                qq = to_screen(q_["m_on"], cc, uu)
                col = routes[q_["route"]]["color"]
                if q_["key"] in poi_layout and poi_t[q_["key"]] < ch["t_end"]:
                    sp_ = SP.poi_label(q_["lines"], col, q_["sub"], False, q_["scale"])
                    L.add_box(label_box(qq, sp_[0].shape[1::-1], sp_[1], poi_layout[q_["key"]]), 4)
                if poi_short.get(q_["key"]):
                    sp_ = SP.poi_label(q_["short"], col, None, True)
                    L.add_box(label_box(qq, sp_[0].shape[1::-1], sp_[1], poi_short[q_["key"]]), 4)
            for lr in ch_rlabels:
                if place_route_label(L, lr) > 150:
                    warn(msgs, f"nhãn tuyến {lr['text']} (chương {ch['i'] + 1}) chật chỗ")

    # nhãn ngắn ở khung kết
    lay = Layout()
    ps = to_screen(PM, oc, ou)
    cm = card_mini if ou >= switch_u else card_full
    lay.add_box(card_box(ps, cm, card_side), C.CARD_HARD)
    lay.add_box((ps[0] - 22, ps[1] - 22, ps[0] + 22, ps[1] + 22), 3)
    lg_items = tuple((routes[k_]["name"], routes[k_]["color"]) for ch in B["chuong"] for k_ in ch["tuyen"]
                     if B["tuyen"][k_].get("chu_giai", True))           # đường đi tới tiện ích không vào chú giải (đỡ rối)
    lg = SP.legend(lg_items)
    lgw, lgh = lg[0].shape[1], lg[0].shape[0]
    legend_y = C.SAFE_Y0 + 10
    lay.add_box((C.W / 2 - lgw / 2, legend_y, C.W / 2 + lgw / 2, legend_y + lgh), 5)
    for h in heads:
        r = routes[h["route"]]
        lay.add_line(np.array([to_screen(geo.point_at(r["P"], r["L"], ss), oc, ou) for ss in np.linspace(h["s0"], h["s1"], 120)]))
    final_labels = {}
    lay.add_pin(ps + np.array([0, 37]))
    for q_ in pois:
        qq = to_screen(q_["m_on"], oc, ou)
        lay.add_box((qq[0] - 24, qq[1] - 76, qq[0] + 24, qq[1] + 6), 2)
        lay.add_pin(qq)
    for p in sorted(pois, key=lambda p: -(p["spec"].get("uu_tien", 1))):
        if p["spec"].get("an_o_ket"):
            continue
        q = to_screen(p["m_on"], oc, ou)
        lines = p["short"]
        spr = SP.poi_label(lines, routes[p["route"]]["color"], None, True)
        sc, off, b = place_poi(lay, q, spr, near_only=True, allow_edge=C.EDGE_FIT)
        if sc > C.SHORT_MAX_SCORE_OUTRO:
            continue
        cb = card_box(ps, cm, card_side)                 # tên ngắn KHÔNG được chạm thẻ dự án (AEON đè thẻ 15 %, 17/10)
        if min(b[2], cb[2]) - max(b[0], cb[0]) > 0 and min(b[3], cb[3]) - max(b[1], cb[1]) > 0:
            continue
        lay.add_box(b, 2)
        final_labels[p["key"]] = dict(lines=list(lines), off=[float(off[0]), float(off[1])])

    # ---------------------------------------------------------- đo độ êm toàn bộ đường máy quay
    tt_ = np.arange(0, T, 1 / C.FPS)
    cu = [camera_at(cam, x, k) for x in tt_]
    cc_ = np.array([a for a, b in cu]); uu_ = np.array([b for a, b in cu])
    pan_all = np.linalg.norm(np.diff(cc_, axis=0), axis=1) / uu_[:-1]
    zoom_all = np.abs(np.diff(np.log(uu_))) * 100
    max_pan, max_zoom = float(pan_all.max()), float(zoom_all.max())
    if max_pan > C.MAX_PAN_PX or max_zoom > C.MAX_ZOOM_PCT:
        i1 = int(np.argmax(pan_all)); i2 = int(np.argmax(zoom_all))
        warn(msgs, f"máy quay vượt ngưỡng êm: lia {max_pan:.1f} px/khung lúc {tt_[i1]:.1f} s, zoom {max_zoom:.1f} %/khung lúc {tt_[i2]:.1f} s")

    # ---------------------------------------------------------- vòng km: bỏ vòng nhỏ, chọn góc nhãn
    for ch in chapters:
        if not ch.get("rings"):
            continue
        c_, u_ = camera_at(cam, ch["t_end"] - 0.01, k)
        ps_ = to_screen(PM, c_, u_)
        L3 = Layout()
        L3.add_box(card_box(ps_, card_full if u_ < switch_u else card_mini, card_side), C.CARD_HARD)
        for ln in drawn_lines(ch["t_end"] - 0.01, c_, u_):
            L3.add_line(ln)
        for q_ in pois:
            if q_["key"] in poi_t and poi_t[q_["key"]] <= ch["t_end"]:
                qq = to_screen(q_["m_on"], c_, u_)
                L3.add_box((qq[0] - 24, qq[1] - 76, qq[0] + 24, qq[1] + 6), 2)
        keep = []
        for rg in ch["rings"]:
            Rpx = rg["r"] / u_
            if Rpx < C.RING_MIN_PX:
                continue
            best = None
            for deg in (28, -28, 152, 208, 62, 118, -62, -118, 0, 180):
                a_ = math.radians(deg)
                x, y = ps_[0] + Rpx * math.cos(a_), ps_[1] + Rpx * math.sin(a_)
                bx = (x - 55, y - 20, x + 55, y + 20)
                sc = L3.score(bx) + abs(deg - 28) * 0.05
                if not (C.SAFE_X0 < bx[0] and bx[2] < C.SAFE_X1 and C.SAFE_Y0 < bx[1] and bx[3] < C.SAFE_Y1):
                    sc += 1000
                if best is None or sc < best[0]:
                    best = (sc, deg, bx)
            rg["ang"] = best[1]
            L3.add_box(best[2], 2)
            keep.append(rg)
        ch["rings"] = keep

    # ---------------------------------------------------------- khung kết: ẩn ghim chồng nhau
    c_o, u_o = oc, ou
    kept = [to_screen(PM, c_o, u_o)]
    outro_hide = set()
    for p in sorted(pois, key=lambda p: (-(p["spec"].get("uu_tien", 1)), -p["dist_crow"])):
        q = to_screen(p["m_on"], c_o, u_o)
        if any(np.linalg.norm(q - kq) < C.OUTRO_PIN_GAP for kq in kept):
            outro_hide.add(p["key"])
            final_labels.pop(p["key"], None)
        else:
            kept.append(q)

    # ---------------------------------------------------------- ghim CŨ (chương trước) chồng ghim mới → mờ đi trong chương đó
    pin_hide = {}
    prev_end = 0.0
    for ch in chapters:
        c_, u_ = camera_at(cam, ch["t_end"] - 0.01, k)
        kept = [to_screen(PM, c_, u_)] + [to_screen(p["m_on"], c_, u_) for p in pois
                                          if p["route"] in ch["keys"] and p["key"] in poi_t]
        olds = [p for p in pois if p["route"] not in ch["keys"] and p["key"] in poi_t and poi_t[p["key"]] <= prev_end]
        for p in sorted(olds, key=lambda p: (-(p["spec"].get("uu_tien", 1)), -p["dist_crow"])):
            q = to_screen(p["m_on"], c_, u_)
            if any(np.linalg.norm(q - kq) < C.OUTRO_PIN_GAP for kq in kept):
                pin_hide.setdefault(p["key"], []).append([prev_end, ch["t_end"]])
            else:
                kept.append(q)
        prev_end = ch["t_end"]

    # gộp khoảng ẩn liền nhau + nối tới hết video nếu khung kết cũng ẩn ghim đó — tránh ghim tắt/bật/tắt (nhấp nháy)
    for key_, iv in pin_hide.items():
        iv.sort()
        merged = [list(iv[0])]
        for a, b in iv[1:]:
            if a <= merged[-1][1] + 0.6:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        if key_ in outro_hide and merged[-1][1] >= chapters[-1]["t_end"] - 0.01:
            merged[-1][1] = T + 1.0
        pin_hide[key_] = merged

    def hidden(key, tt):
        return any(a <= tt <= b for a, b in pin_hide.get(key, []))

    # ---------------------------------------------------------- ghim chồng nhau trong chương → cảnh báo
    for ch in chapters:
        c_, u_ = camera_at(cam, ch["t_end"] - 0.01, k)
        vis = [p for p in pois if p["key"] in poi_t and poi_t[p["key"]] <= ch["t_end"] and not hidden(p["key"], ch["t_end"] - 0.01)]
        for i_ in range(len(vis)):
            for j_ in range(i_ + 1, len(vis)):
                a_, b_ = to_screen(vis[i_]["m_on"], c_, u_), to_screen(vis[j_]["m_on"], c_, u_)
                if np.linalg.norm(a_ - b_) < C.PIN_MIN_GAP:
                    warn(msgs, f"ghim {' '.join(vis[i_]['lines'])} và {' '.join(vis[j_]['lines'])} chồng nhau ở chương {ch['i'] + 1} "
                               f"({np.linalg.norm(a_ - b_):.0f} px) — bỏ bớt một điểm hoặc gộp tên")
    if SP.MISSING:
        warn(msgs, "font thiếu glyph, đã thay: " + ", ".join(f"«{c}» ({f})" for c, f in sorted(SP.MISSING)))

    # ---------------------------------------------------------- SFX: bỏ trùng gần nhau
    sfx.sort(key=lambda e: e["t"])
    clean = []
    for e in sfx:
        if clean and e["name"] == clean[-1]["name"] and e["t"] - clean[-1]["t"] < C.SFX_GAP:
            continue
        clean.append(e)

    plan = dict(
        meta=dict(W=C.W, H=C.H, fps=C.FPS, duration=round(T, 3), brief=os.path.abspath(brief_path), k=k,
                  khung_sat=bool(B.get("khung_sat"))),          # verify: thẻ dự án được ra ngoài khung (chương sát line)
        project=dict(name=name, sub=B.get("the_phu"), ll=list(proj_ll), m=PM.tolist(), logo=rel(B.get("logo")), switch_u=switch_u,
                     vung=(VUNG["m"].tolist() if VUNG["m"] is not None else None),
                     card_side=card_side),
        # phoi_canh.giu = lớp quy hoạch GIỮ suốt video (không tan khi máy lùi ra); do_dam = độ đục; vien = viền vàng theo ảnh
        masterplan=(dict(img=rel(B["phoi_canh"]["anh"]), bounds=B["phoi_canh"]["bounds"], xfade=list(C.PLAN_XFADE),
                         t_out=([T + 10, T + 11] if B["phoi_canh"].get("giu") else
                                [cam[1]["t0"] if len(cam) > 1 else intro_end, (cam[1]["t0"] + cam[1]["t1"]) / 2 if len(cam) > 1 else intro_end + 1]),
                         opacity=float(B["phoi_canh"].get("do_dam", 1.0)), ring=bool(B["phoi_canh"].get("vien", True)))
                    if B.get("phoi_canh") else None),
        watermark=B.get("watermark") or None,
        cover=cover,
        routes={k_: dict(name=r["name"], color=r["color"], kind=r["kind"], P=r["P"].tolist(), how=r["how"], glow=r.get("glow", False),
                         an_net=r.get("an_net", False)) for k_, r in routes.items()},
        # khoanh vùng (xã, cụm CN): hiện khi line chạm mép vùng (hoặc ngay khi vào chương nếu giáp ranh), đậm trong chương,
        # nhạt bớt sau đó nhưng giữ tới hết video
        zones=[dict(route=k_, color=r["color"], ring=r["zone"].tolist(), chapter=zc["i"], t_dim=zc["t_end"],
                    t_in=min([poi_t[p["key"]] for p in pois if p["route"] == k_ and p["key"] in poi_t] or [zc["t_title"] + 0.6]) - 0.25)
               for k_, r in routes.items() if r.get("zone") is not None
               for zc in [next((ch for ch in chapters if k_ in ch["keys"]), chapters[0])]],
        heads=heads,
        pois=[dict(key=p["key"], route=p["route"], kind=p["kind"], lines=list(p["lines"]), sub=p["sub"], m=list(map(float, p["m_on"])),
                   t=poi_t.get(p["key"]), t_label=label_t.get(p["key"], poi_t.get(p["key"])), off=poi_layout.get(p["key"]), short=list(p["short"]), off_short=poi_short.get(p["key"]), t_collapse=poi_collapse.get(p["key"]), scale=p.get("scale", 1.0), chapter=next((ch["i"] for ch in chapters if p["route"] in ch["keys"]), 0),
                   final=final_labels.get(p["key"]), outro_hide=p["key"] in outro_hide, hide=pin_hide.get(p["key"], []), dist=p["dist"], dist_mode=p["dist_mode"],
                   dist_crow=p["dist_crow"], dist_along=p["dist_along"]) for p in pois],
        route_labels=labels_route,
        chapters=[dict(i=ch["i"], title=ch["title"], t_title=ch["t_title"], t_end=ch["t_end"], pos=title_layout[ch["i"]], spot=ch["spot"],
                       t_spot=ch.get("t_spot"), spot_r=ch.get("spot_r"), rings=ch.get("rings"), c=list(ch["c"]),
                       last=(ch["i"] == len(chapters) - 1)) for ch in chapters],
        camera=cam,
        outro=dict(t=t_arr, legend_t=legend_t, legend_items=[list(x) for x in lg_items], legend_y=legend_y, c=list(oc), u=ou, t_move=t_out0),
        end_card=end_card,
        sfx=clean,
        motion=dict(max_pan=max_pan, max_zoom=max_zoom),
        warnings=msgs,
    )
    return plan, routes, pois, chapters, chapter_rows


def review(plan, routes, pois, chapters, rows):
    print("\n══════════ BẢNG DUYỆT NỘI DUNG ══════════")
    print(f"Thời lượng {plan['meta']['duration']:.1f} s · {C.W}×{C.H} · {C.FPS} khung/s")
    if plan["cover"]:
        print(f"Bìa: {' / '.join(plan['cover']['lines'])}" + (f"  ·  {plan['cover']['sub']}" if plan['cover']['sub'] else ""))
    for (title, t0, t1, D), ch in zip(rows, chapters):
        print(f"\n▶ Chương {ch['i'] + 1}: «{title}»  {t0:.1f}–{t1:.1f} s" + ("  [spotlight + vòng km]" if ch["spot"] else ""))
        if ch.get("rings"):
            print("   vòng: " + ", ".join(f"{r['km']} km" for r in ch["rings"]))
        for key in ch["keys"]:
            r = routes[key]
            print(f"   ─ {r['name']} ({r['color']}, icon {('tàu' if r['kind'] == 'metro' else 'máy bay' if r['kind'] == 'sanbay' else 'ô tô')}) — nguồn: {r['how']}"
                  + (f" — nhãn «{r['label']}{(' / ' + r['label_sub']) if r['label_sub'] else ''}»" if r["label"] else ""))
            for p in [p for p in pois if p["route"] == key]:
                pp = next(x for x in plan["pois"] if x["key"] == p["key"])
                tt = f"{pp['t']:.1f} s" if pp["t"] is not None else "—"
                mode = "theo tuyến" if p["dist_mode"] == "theo_tuyen" else "chim bay"
                print(f"      • {' / '.join(p['lines'])}  →  «{p['sub'] or '(không ghi km)'}»  [{mode}; chim bay {fmt_dist(p['dist_crow'])} · theo tuyến {fmt_dist(p['dist_along'])}] lúc {tt}")
    print(f"\nKết: toàn cảnh + chú giải {len(plan['outro']['legend_items'])} dòng lúc {plan['outro']['legend_t']:.1f} s"
          + (f" + khung kết «{plan['end_card']['line1']}»" if plan["end_card"] else ""))
    print(f"Máy quay: lia tối đa {plan['motion']['max_pan']:.1f} px/khung (ngưỡng {C.MAX_PAN_PX}), "
          f"zoom tối đa {plan['motion']['max_zoom']:.1f} %/khung (ngưỡng {C.MAX_ZOOM_PCT})")
    print(f"SFX: {len(plan['sfx'])} tiếng — " + ", ".join(sorted({e['name'] for e in plan['sfx']})))
    if plan["warnings"]:
        print("\n⚠ CẦN XEM:")
        for w in plan["warnings"]:
            print("   - " + w)
    print("══════════════════════════════════════════")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", required=True)
    ap.add_argument("--work", required=True)
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    plan, routes, pois, chapters, rows = build(a.brief, a.work)
    if plan_side_retry:                                   # khung đã khớp theo phía thẻ mặc định → dựng lại theo phía chọn được
        side = plan_side_retry[-1]
        plan_side_retry.clear()
        plan, routes, pois, chapters, rows = build(a.brief, a.work, side_override=side)
        plan["warnings"].insert(0, f"thẻ dự án đặt phía «{side}» (ít đè nét tuyến nhất)")
    geo.save_json(os.path.join(a.work, "plan.json"), plan)
    review(plan, routes, pois, chapters, rows)
    print(f"● Đã ghi {os.path.join(a.work, 'plan.json')}")


if __name__ == "__main__":
    main()
