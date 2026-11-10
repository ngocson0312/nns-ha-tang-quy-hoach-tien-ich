"""Lấy toạ độ các tuyến vẽ màu trên một ẢNH (ảnh quy hoạch / ảnh chụp màn hình có vẽ tuyến trên nền vệ tinh).

Dùng khi tuyến cần vẽ KHÔNG có trong OSM (tuyến quy hoạch, đường đang chuẩn bị đầu tư).

  python trace_lines.py --image anh.png --near 20.96,105.98 --palette "metro8=#2FC85E,vd4=#CC75FF,gb=white"
         --out tuyen.json [--points diem_khop.json] [--zooms 12,13,14] [--radius-km 30]

Khớp ảnh lên vệ tinh:
  * tự động (mặc định): SIFT + CLAHE ảnh với mosaic Esri quanh --near, thử nhiều mức zoom, chọn mức nhiều
    điểm khớp nhất, RANSAC phép đồng dạng (không xoay nếu ảnh nhìn thẳng hướng bắc — vẫn để tự do góc).
  * tay: --points là JSON [{"px":[x,y],"ll":[lat,lon]}, …] ≥ 3 điểm (cho bản đồ quy hoạch dạng vẽ, không phải vệ tinh).

Tách tuyến: pixel KHÁC ảnh vệ tinh (lớp vẽ đè) ∩ gần màu tuyến (ΔE Lab) → bỏ cụm ngắn (chữ, icon) → lấy xương
→ đường dài nhất mỗi cụm → nối các khúc bị nhãn che (khe ≤ --gap px) → đổi ra lat/lon → làm mượt nhẹ.
In ra độ tin cậy cho từng tuyến; ảnh kiểm tra *_trace.jpg vẽ lại tuyến đã lấy để NHÌN.
"""
import argparse, json, math, os, sys
from collections import deque
import numpy as np, cv2
from skimage.morphology import skeletonize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo


def hex2bgr(h):
    h = h.strip().lstrip("#")
    return np.array([int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)], np.uint8)


def to_lab(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32) * [100 / 255, 1, 1] - [0, 128, 128]


def georef_auto(img, near, radius_km, zooms):
    clahe = cv2.createCLAHE(3.0, (8, 8))
    prep = lambda im: clahe.apply(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
    sift = cv2.SIFT_create(20000)
    kf, df = sift.detectAndCompute(prep(img), None)
    lat, lon = near
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * math.cos(math.radians(lat)))
    best = None
    for z in zooms:
        mos, org, mpp = geo.mosaic(z, lat - dlat, lat + dlat, lon - dlon, lon + dlon)
        km, dm = sift.detectAndCompute(prep(mos), None)
        if dm is None or df is None:
            continue
        mt = cv2.BFMatcher().knnMatch(df, dm, k=2)
        good = [a for a, b in (m for m in mt if len(m) == 2) if a.distance < 0.78 * b.distance]
        if len(good) < 12:
            print(f"  z{z}: {len(good)} cặp, bỏ")
            continue
        A = np.float32([kf[g.queryIdx].pt for g in good])
        B = np.float32([km[g.trainIdx].pt for g in good])
        M, inl = cv2.estimateAffinePartial2D(A, B, method=cv2.RANSAC, ransacReprojThreshold=4)
        n = int(inl.sum()) if inl is not None else 0
        print(f"  z{z}: {n}/{len(good)} điểm khớp")
        if M is not None and (best is None or n > best[0]):
            best = (n, len(good), M, org, mpp, mos)
    if best is None:
        raise SystemExit("⛔ Không khớp được ảnh lên vệ tinh. Ảnh có phải nền vệ tinh không? Dùng --points để khớp tay.")
    n, ng, M, org, mpp, mos = best
    # ảnh px → mét Mercator
    T = np.array([[mpp, 0, org[0]], [0, mpp, org[1]], [0, 0, 1]]) @ np.vstack([M, [0, 0, 1]])
    s = math.hypot(M[0, 0], M[1, 0]) * mpp
    ang = math.degrees(math.atan2(M[1, 0], M[0, 0]))
    conf = n / max(ng, 1)
    print(f"  → chọn: {n} điểm khớp ({conf:.0%}), {s / geo.scale_k(lat):.1f} m thật/px ảnh, xoay {ang:+.2f}°")
    # mosaic chiếu về khung ảnh để tìm lớp vẽ đè
    Minv = cv2.invertAffineTransform(M)
    back = cv2.warpAffine(mos, Minv, (img.shape[1], img.shape[0]), flags=cv2.INTER_AREA)
    return T, back, dict(inliers=n, ratio=conf, m_per_px=s / geo.scale_k(lat), rot=ang)


def georef_points(pts):
    A = np.float32([p["px"] for p in pts])
    B = np.float32([geo.ll2m(*p["ll"]) for p in pts])
    M, _ = cv2.estimateAffine2D(A, B) if len(pts) >= 4 else (cv2.getAffineTransform(A[:3], B[:3]), None)
    return np.vstack([M, [0, 0, 1]]), None, dict(inliers=len(pts), ratio=1.0)


def longest_path(skel_pts):
    """đường dài nhất (theo số bước 8-lân cận) trong một cụm xương; trả list (y, x)."""
    S = set(map(tuple, skel_pts))
    nb = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    def bfs(src):
        prev = {src: None}
        q = deque([src])
        last = src
        while q:
            u = q.popleft(); last = u
            for dy, dx in nb:
                v = (u[0] + dy, u[1] + dx)
                if v in S and v not in prev:
                    prev[v] = u; q.append(v)
        return last, prev

    a, _ = bfs(next(iter(S)))
    b, prev = bfs(a)
    path = [b]
    while prev[path[-1]] is not None:
        path.append(prev[path[-1]])
    return path


def _tangent(c, head):
    k = min(len(c) - 1, 8)
    return (c[0] - c[k]) if head else (c[-1] - c[-1 - k])


def join_chains(chains, gap, keep=40, occluded=None, far=3.0):
    """nối khúc theo đầu mút gần nhau (≤ gap px) và cùng hướng; trả list chuỗi (N×2, x y), dài nhất trước.
    Chỉ xét `keep` khúc dài nhất (chữ/viền nhãn vụn không bao giờ là tuyến) — tránh bùng nổ O(n³).
    Khe dài tới far×gap vẫn được nối nếu occluded(pa, pb) = True (đoạn nối nằm dưới thẻ/nhãn vẽ đè)."""
    ch = sorted((np.array(c, float) for c in chains), key=lambda c: -len(c))[:keep]
    while len(ch) > 1:
        best = None
        for i in range(len(ch)):
            for j in range(i + 1, len(ch)):
                a, b = ch[i], ch[j]
                # 4 cách ghép đầu/đuôi; mỗi cách: (khoảng cách, chuỗi ghép nếu chọn)
                for ea, eb in ((False, True), (False, False), (True, True), (True, False)):
                    pa = a[0] if ea else a[-1]
                    pb = b[0] if eb else b[-1]
                    d = float(np.linalg.norm(pa - pb))
                    if best is not None and d >= best[0]:
                        continue
                    if d > gap and not (occluded is not None and d <= far * gap and occluded(pa, pb)):
                        continue
                    ta = _tangent(a, ea)                 # hướng đi RA khỏi a tại đầu nối
                    tb = -_tangent(b, eb)                # hướng đi VÀO b tại đầu nối
                    v = pb - pa
                    cos1 = np.dot(ta, tb) / (np.linalg.norm(ta) * np.linalg.norm(tb) + 1e-9)
                    cos2 = 1.0 if d < 3 else np.dot(ta, v) / (np.linalg.norm(ta) * np.linalg.norm(v) + 1e-9)
                    if cos1 < 0.3 or cos2 < 0.2:
                        continue
                    A_ = a[::-1] if ea else a            # để đầu nối nằm ở CUỐI A_
                    B_ = b if eb else b[::-1]            # để đầu nối nằm ở ĐẦU B_
                    best = (d, i, j, A_, B_)
        if best is None:
            break
        _, i, j, A_, B_ = best
        ch = [c for k, c in enumerate(ch) if k not in (i, j)] + [np.vstack([A_, B_])]
    return sorted(ch, key=lambda c: -len(c))


def graph_route(mask, gap, min_len, occluded=None, far=3.0, via=None):
    """xương của mặt nạ màu → đồ thị pixel; thêm cạnh 'cầu' từ mỗi đầu nét tới nét khác trong vòng gap px
    (hoặc far×gap nếu đoạn cầu nằm dưới lớp vẽ đè) với chi phí ×2; tuyến = đường dài nhất (Dijkstra 2 lượt)
    trong cụm lớn nhất. Trả (polyline N×2 x,y | None, độ phủ, số khúc)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra, connected_components
    from scipy.spatial import cKDTree
    n0, lbl0, st0, _ = cv2.connectedComponentsWithStats(mask, 8)
    keep = np.zeros(n0, bool)
    for k in range(1, n0):
        x, y, w, h, area = st0[k]
        keep[k] = max(w, h) >= 8
    mask = keep[lbl0]
    # loại mảng DÀY (linh vật, icon đặc, thẻ/bảng trắng): nét tuyến chỉ dày vài px. Ngưỡng tự suy từ nửa bề
    # dày trung vị của chính các nét (đa số xương thuộc về tuyến), tối thiểu 3,5 px.
    dt = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5)
    sk0 = skeletonize(mask)
    half = float(np.median(dt[sk0])) if sk0.any() else 2.0
    thick = max(3.5, 2.2 * half)
    core = (dt >= thick).astype(np.uint8)
    if core.any():
        r = int(round(thick + 2))
        core = cv2.dilate(core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
        mask = mask & ~core.astype(bool)
        n0, lbl0, st0, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    sk = skeletonize(mask)
    ys, xs = np.nonzero(sk)
    N = len(ys)
    if N < min_len:
        return None, 0, 0
    idx = -np.ones(sk.shape, np.int64); idx[ys, xs] = np.arange(N)
    comp = lbl0[ys, xs]
    rows, cols, wts = [], [], []
    deg = np.zeros(N, int)
    for dy, dx, w in ((0, 1, 1.0), (1, 0, 1.0), (1, 1, 1.4142), (1, -1, 1.4142)):
        y2, x2 = ys + dy, xs + dx
        ok = (y2 >= 0) & (y2 < sk.shape[0]) & (x2 >= 0) & (x2 < sk.shape[1])
        j = np.full(N, -1); j[ok] = idx[y2[ok], x2[ok]]
        m = j >= 0
        rows += list(np.nonzero(m)[0]); cols += list(j[m]); wts += [w] * int(m.sum())
        np.add.at(deg, np.nonzero(m)[0], 1); np.add.at(deg, j[m], 1)
    ends = np.nonzero(deg <= 1)[0]
    P = np.stack([xs, ys], 1).astype(float)
    tree = cKDTree(P)
    for e in ends:
        for j in tree.query_ball_point(P[e], far * gap):
            if comp[j] == comp[e]:
                continue
            d = float(np.linalg.norm(P[j] - P[e]))
            if d > gap and not (occluded is not None and occluded(P[e], P[j])):
                continue
            rows.append(e); cols.append(j); wts.append(2.0 * d + 1.0)
    G = coo_matrix((wts, (rows, cols)), shape=(N, N)).tocsr()
    G = G.maximum(G.T)
    if via:
        # đi qua lần lượt các điểm gợi ý (px ảnh): đường ngắn nhất dọc nét giữa từng cặp điểm liên tiếp
        nodes = [int(tree.query(np.asarray(v, float))[1]) for v in via]
        path_idx = []
        for u, v in zip(nodes, nodes[1:]):
            dist, pred = dijkstra(G, indices=u, return_predecessors=True)
            if not np.isfinite(dist[v]):
                return None, 0, 0
            seg = [v]
            while seg[-1] != u:
                seg.append(int(pred[seg[-1]]))
            path_idx += seg[::-1][(1 if path_idx else 0):]
        path = P[path_idx]
        snap = max(float(np.linalg.norm(P[n] - np.asarray(v, float))) for n, v in zip(nodes, via))
        return path, snap, len(set(comp[path_idx]))
    nc, cl = connected_components(G, directed=False)
    sizes = np.bincount(cl)
    big = int(np.argmax(sizes))
    sel = np.nonzero(cl == big)[0]
    if len(sel) < min_len:
        return None, 0, 0
    d0 = dijkstra(G, indices=int(sel[0]))
    a = int(sel[np.argmax(np.where(np.isfinite(d0[sel]), d0[sel], -1))])
    da, pred = dijkstra(G, indices=a, return_predecessors=True)
    b = int(sel[np.argmax(np.where(np.isfinite(da[sel]), da[sel], -1))])
    path = [b]
    while path[-1] != a and pred[path[-1]] >= 0:
        path.append(int(pred[path[-1]]))
    path = P[path[::-1]]
    cover = len(path) / float(len(sel))
    npieces = len(set(comp[sel]))
    return path, cover, npieces


def trace(img, back, T, palette, tol, gap, min_len, near_lat, vias=None):
    lab = to_lab(img)
    over = np.ones(img.shape[:2], bool)
    if back is not None:
        dE = np.linalg.norm(lab - to_lab(back), axis=2)
        over = dE > 22
    Lc = lab[..., 0]; Cc = np.linalg.norm(lab[..., 1:], axis=2)
    # chỉ loại đốm trắng GỌN-ĐẶC (ruột ghim, chữ trắng) — viền trắng dài mảnh của chính nét tuyến thì giữ
    wm = ((Lc > 80) & (Cc < 16) & over).astype(np.uint8)
    nW, lW, sW, _ = cv2.connectedComponentsWithStats(wm, 8)
    blob = np.zeros_like(wm)
    for k in range(1, nW):
        x, y, w, h, area = sW[k]
        if 6 <= max(w, h) <= 70 and area / float(w * h) >= 0.3:
            blob[lW == k] = 1
    whiteish = cv2.dilate(blob, np.ones((7, 7), np.uint8)).astype(bool)

    def occluded(pa, pb):
        n = max(2, int(np.linalg.norm(pb - pa) / 2))
        xs = np.linspace(pa[0], pb[0], n).astype(int).clip(0, img.shape[1] - 1)
        ys = np.linspace(pa[1], pb[1], n).astype(int).clip(0, img.shape[0] - 1)
        return over[ys, xs].mean() >= 0.7

    res, dbg = {}, img.copy()
    for name, col in palette.items():
        if col.lower() in ("white", "trang", "trắng"):
            L = lab[..., 0]; C = np.linalg.norm(lab[..., 1:], axis=2)
            m = (L > 82) & (C < 14)
            colbgr = np.array([255, 255, 255], np.uint8)
        else:
            colbgr = hex2bgr(col)
            ref = to_lab(colbgr.reshape(1, 1, 3))[0, 0]
            m = np.linalg.norm(lab - ref, axis=2) < tol
        m &= over
        if col.lower() not in ("white", "trang", "trắng"):
            m &= ~whiteish                     # bỏ ghim/nhãn cùng màu (ruột trắng, viền trắng)
        m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        via = (vias or {}).get(name)
        main, cover, npieces = graph_route(m, gap, min_len, occluded, via=via)
        if main is None:
            print(f"  ⚠ {name}: không thấy nét nào gần màu {col}")
            continue
        P = np.array([(T @ [x, y, 1])[:2] for x, y in main])
        P = geo.smooth(geo.resample(P, 25 * geo.scale_k(near_lat)), 5)
        ll = [list(map(float, geo.m2ll(*p))) for p in P]
        km = geo.geolen(ll) / 1000
        if via:
            res[name] = dict(color=col, latlon=ll, km=round(km, 2), via_snap_px=round(cover, 1), n_pieces=npieces)
            warn = "  ⚠ điểm gợi ý cách nét xa — kiểm lại" if cover > 12 else ""
            print(f"  ✓ {name}: {km:.1f} km theo {len(via)} điểm gợi ý (lệch bám tối đa {cover:.0f} px), {npieces} khúc{warn}")
        else:
            res[name] = dict(color=col, latlon=ll, km=round(km, 2), cover=round(cover, 2), n_pieces=npieces)
            print(f"  ✓ {name}: {km:.1f} km, nối từ {npieces} khúc, đường chính phủ {cover:.0%} chiều dài nét cùng màu")
        cv2.polylines(dbg, [np.int32(main)], False, (0, 0, 0), 7, cv2.LINE_AA)
        cv2.polylines(dbg, [np.int32(main)], False, tuple(int(v) for v in colbgr), 3, cv2.LINE_AA)
        cv2.circle(dbg, tuple(np.int32(main[0])), 7, (255, 255, 255), -1)
    return res, dbg


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--near", help="lat,lon gần vùng ảnh (khớp tự động)")
    ap.add_argument("--radius-km", type=float, default=30)
    ap.add_argument("--zooms", default="12,13")
    ap.add_argument("--points", help="JSON điểm khớp tay")
    ap.add_argument("--palette", required=True, help='"ten=#RRGGBB,ten2=white"')
    ap.add_argument("--tol", type=float, default=26)
    ap.add_argument("--gap", type=float, default=45)
    ap.add_argument("--min-len", type=int, default=25)
    ap.add_argument("--via", default="", help='"ten=x1,y1;x2,y2;… | ten2=…" điểm gợi ý (px ảnh) theo thứ tự đi')
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    img = cv2.imread(a.image)
    if img is None:
        raise SystemExit(f"⛔ Không đọc được ảnh {a.image}")
    palette = dict(kv.split("=", 1) for kv in a.palette.split(","))
    print(f"● Khớp ảnh {os.path.basename(a.image)} ({img.shape[1]}×{img.shape[0]}) lên vệ tinh…")
    if a.points:
        T, back, info = georef_points(geo.load_json(a.points))
        near_lat = geo.m2ll(*(T @ [img.shape[1] / 2, img.shape[0] / 2, 1])[:2])[0]
    else:
        near = tuple(map(float, a.near.split(",")))
        T, back, info = georef_auto(img, near, a.radius_km, [int(z) for z in a.zooms.split(",")])
        near_lat = near[0]
    print("● Tách tuyến theo màu…")
    vias = {}
    for part in filter(None, a.via.split("|")):
        k, v = part.split("=", 1)
        vias[k.strip()] = [tuple(map(float, q.split(","))) for q in v.split(";")]
    res, dbg = trace(img, back, T, palette, a.tol, a.gap, a.min_len, near_lat, vias)
    geo.save_json(a.out, dict(source=os.path.abspath(a.image), georef=info, image_to_merc=T.tolist(), routes=res))
    dp = os.path.splitext(a.out)[0] + "_trace.jpg"
    cv2.imwrite(dp, dbg)
    print(f"● Đã ghi {a.out} + ảnh kiểm {dp} — hãy NHÌN ảnh kiểm trước khi dùng.")


if __name__ == "__main__":
    main()
