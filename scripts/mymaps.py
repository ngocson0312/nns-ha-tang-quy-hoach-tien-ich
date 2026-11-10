"""Link Google My Maps (bản đồ quy hoạch) → ranh khu quy hoạch + lớp màu quy hoạch đặt lên vệ tinh.

  python mymaps.py --link "https://www.google.com/maps/d/viewer?mid=..." --work THU_MUC [--dong_ranh_m 150]

Ghi vào <work>/quy_hoach/:
  quy_hoach.json  tên bản đồ, các lớp, loại đất (số lô, diện tích, màu), ranh chính (lat/lon), ranh phụ, tâm, bounds
  quy_hoach.png   ảnh RGBA lớp quy hoạch (màu từng lô như trên My Maps), lưới Mercator đúng bounds → "phoi_canh" của hồ sơ
  quy_hoach_xem.jpg  ảnh soát: lớp quy hoạch + ranh vàng + chú giải loại đất — Claude PHẢI mở ra nhìn

Nguồn: Google chặn tải KML khi chủ bản đồ tắt xuất (HTTP 403) — nhưng trang viewer công khai nhúng sẵn toàn bộ hình học
(`_pageData`): lớp L[12][0][13][0] = các đối tượng [id, điểm, đường, vùng, kiểu, thuộc tính…], L[12][0][13][1] = bảng kiểu
(màu tô / viền). Bản đồ lớn quá ~2000 đối tượng/lớp thì My Maps tự chia lớp — đọc hết mọi lớp.
"""
import argparse, html, json, math, os, re, sys, time
import numpy as np
import cv2
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
BO_TEN = re.compile(r"^logo\b|iquyhoach|watermark", re.I)          # ảnh logo của trang nguồn — không phải lô đất
MAX_PX = 4096                                                       # cạnh dài nhất của quy_hoach.png


def mid_of(link):
    m = re.search(r"[?&]mid=([A-Za-z0-9_\-]+)", link)
    if not m:
        raise SystemExit("⛔ Link không có mid=… — cần link Google My Maps dạng https://www.google.com/maps/d/viewer?mid=…")
    return m.group(1)


def fetch_pagedata(mid, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    cp = os.path.join(cache_dir, f"pagedata_{mid}.json")
    if os.path.exists(cp):
        return geo.load_json(cp)
    url = f"https://www.google.com/maps/d/viewer?mid={mid}"
    print(f"  … tải trang bản đồ {url}")
    r = requests.get(url, headers=UA, timeout=120)
    if r.status_code != 200:
        raise SystemExit(f"⛔ My Maps trả HTTP {r.status_code} — bản đồ chưa chia sẻ công khai? Nhờ user bật 'Bất kỳ ai có đường liên kết'.")
    m = re.search(r'var _pageData = "(.*?)";</script>', r.text, re.S)
    if not m:
        raise SystemExit("⛔ Trang My Maps không có _pageData (Google đổi giao diện?) — cần user xuất KML/KMZ gửi trực tiếp.")
    data = json.loads(json.loads('"' + m.group(1) + '"'))
    geo.save_json(cp, data)
    return data


def _is_pair(x):
    return isinstance(x, list) and len(x) == 2 and all(isinstance(v, (int, float)) for v in x)


def rings_of(x):
    """mọi chuỗi điểm trong một khối hình học My Maps: mỗi điểm bọc dạng [[lat, lon]]."""
    out = []
    if isinstance(x, list) and x and all(isinstance(e, list) and len(e) == 1 and _is_pair(e[0]) for e in x):
        return [[tuple(e[0]) for e in x]]
    if isinstance(x, list):
        for e in x:
            out += rings_of(e)
    return out


def points_of(x):
    out = []
    if _is_pair(x):
        return [tuple(x)]
    if isinstance(x, list):
        for e in x:
            out += points_of(e)
    return out


def feat_name(f):
    try:
        for kv in f[5]:
            if kv and kv[0] in ("tên", "name", "Tên", "Name") and kv[1]:
                return str(kv[1][0]).strip()
        return str(f[5][0][1][0]).strip()
    except Exception:
        return ""


def style_of(S, idx):
    """kiểu My Maps: [icon, [[màu đường, độ dày], …], [[màu tô, độ đục], [màu viền, độ dày], …]]."""
    fill, op, stroke = "9E9E9E", 0.6, "616161"
    try:
        st = S[idx]
        if st and len(st) > 2 and st[2]:
            fill, op = st[2][0][0], float(st[2][0][1])
            stroke = st[2][1][0] if len(st[2]) > 1 and st[2][1] else fill
        elif st and len(st) > 1 and st[1]:
            stroke = fill = st[1][0][0]
    except Exception:
        pass
    return fill, op, stroke


def hex_bgr(h):
    h = h.lstrip("#")
    return int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)


def parse(data):
    m = data[1]
    title = m[2] or ""
    feats, layers = [], []
    for L in m[6] or []:
        lname = L[2] if len(L) > 2 else ""
        n0 = len(feats)
        try:
            block = L[12][0][13]
            F, S = block[0], block[1]
        except Exception:
            F, S = None, None
        if not F:
            layers.append(dict(ten=lname, so=0, ghi_chu="lớp không có hình học nhúng (chỉ khung bao) — bỏ"))
            continue
        for f in F:
            nm = feat_name(f)
            if BO_TEN.search(nm):
                continue
            fill, op, stroke = style_of(S, f[4] if len(f) > 4 and isinstance(f[4], int) else 0)
            if len(f) > 3 and f[3]:
                # một đối tượng vùng = vòng ngoài + LỖ (lô "đất giao thông" là cả mạng đường, các ô phố là lỗ) — tô
                # chung một lần theo chẵn-lẻ, tô từng vòng riêng thì lỗ bị tô kín thành mảng xám giả
                rr = [r for r in rings_of(f[3]) if len(r) >= 3]
                if rr:
                    feats.append(dict(kind="vung", ten=nm, lop=lname, rings=rr, ll=max(rr, key=len), fill=fill, op=op, stroke=stroke))
            elif len(f) > 2 and f[2]:
                for r in rings_of(f[2]):
                    if len(r) >= 2:
                        feats.append(dict(kind="duong", ten=nm, lop=lname, ll=r, fill=stroke, op=1.0, stroke=stroke))
            elif len(f) > 1 and f[1]:
                p = points_of(f[1])
                if p:
                    feats.append(dict(kind="diem", ten=nm, lop=lname, ll=[p[0]], fill=fill, op=1.0, stroke=stroke))
        layers.append(dict(ten=lname, so=len(feats) - n0))
    return title, layers, feats


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--link", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--dong_ranh_m", type=float, default=150, help="khe giữa các lô ≤ chừng này (m) coi là liền (đường nội khu)")
    a = ap.parse_args()
    out_dir = os.path.join(a.work, "quy_hoach")
    os.makedirs(out_dir, exist_ok=True)
    mid = mid_of(a.link)
    data = fetch_pagedata(mid, os.path.join(out_dir, "_tai_ve"))
    title, layers, feats = parse(data)
    polys = [f for f in feats if f["kind"] == "vung"]
    print(f"● Bản đồ: «{title}» — {len(layers)} lớp, {len(polys)} vùng, "
          f"{sum(f['kind'] == 'duong' for f in feats)} đường, {sum(f['kind'] == 'diem' for f in feats)} điểm")
    if not polys:
        raise SystemExit("⛔ Bản đồ không có vùng (polygon) nào — không dựng được ranh quy hoạch. Hỏi user ranh ở đâu.")

    # ---------------------------------------------------------- lưới Mercator
    allp = np.array([p for f in polys for r in f["rings"] for p in r])
    N, S_, W, E = allp[:, 0].max(), allp[:, 0].min(), allp[:, 1].min(), allp[:, 1].max()
    pad = 0.002
    N, S_, W, E = N + pad, S_ - pad, W - pad, E + pad
    m0, m1 = np.array(geo.ll2m(N, W)), np.array(geo.ll2m(S_, E))
    k = geo.scale_k((N + S_) / 2)
    span = m1 - m0
    res = max(span) / MAX_PX                           # Mercator đơn vị / px
    w, h = int(math.ceil(span[0] / res)), int(math.ceil(span[1] / res))
    to_px = lambda ll: ((geo.lls2m(ll) - m0) / res * 8).round().astype(np.int32)   # 3 bit dịch (shift=3) cho nét mịn
    print(f"  lưới {w}×{h} px, {res / k:.1f} m/px · {span[0] / k / 1000:.1f} × {span[1] / k / 1000:.1f} km")

    # ---------------------------------------------------------- ảnh lớp quy hoạch (màu như My Maps)
    img = np.zeros((h, w, 4), np.uint8)
    edge = np.zeros((h, w), np.uint8)
    # vẽ lô to trước, lô nhỏ sau (lô nhỏ nằm trên lô "giao thông" phủ cả khu)
    def area_of(f):                                      # vòng lớn nhất là vòng ngoài; vòng nằm trong nó là lỗ (trừ), ngoài nó là mảng thêm
        ms = sorted((geo.lls2m(r).astype(np.float32) for r in f["rings"]), key=lambda m: -abs(cv2.contourArea(m)))
        A = abs(cv2.contourArea(ms[0]))
        for m in ms[1:]:
            c = m.mean(0)
            A += -abs(cv2.contourArea(m)) if cv2.pointPolygonTest(ms[0], (float(c[0]), float(c[1])), False) >= 0 else abs(cv2.contourArea(m))
        return max(A, 0.0) / (k * k)
    for f in polys:
        f["area_m2"] = area_of(f)
    for f in sorted(polys, key=lambda f: -f["area_m2"]):
        pts = [to_px(r) for r in f["rings"]]
        b, g, r = hex_bgr(f["fill"])
        al = int(255 * min(1.0, 0.35 + 0.65 * f["op"]))
        # tô chẵn-lẻ trên mặt nạ riêng (chỉ trong khung bao của lô) rồi mới đè màu — giữ lỗ trống thật
        allpx = np.concatenate(pts) // 8
        x0, y0 = np.maximum(allpx.min(0) - 2, 0)
        x1, y1 = np.minimum(allpx.max(0) + 3, [w, h])
        if x1 <= x0 or y1 <= y0:
            continue
        tmp = np.zeros((y1 - y0, x1 - x0), np.uint8)
        cv2.fillPoly(tmp, [p - np.array([x0 * 8, y0 * 8]) for p in pts], 255, cv2.LINE_AA, 3)
        sel = tmp > 0
        if sel.any():
            sub = img[y0:y1, x0:x1]
            av = tmp[sel].astype(np.float32) / 255
            sub[sel] = (sub[sel].astype(np.float32) * (1 - av[:, None]) + np.array([b, g, r, al], np.float32) * av[:, None]).astype(np.uint8)
        cv2.polylines(edge, pts, True, 255, 1, cv2.LINE_AA, 3)
    for f in feats:
        if f["kind"] == "duong":
            b, g, r = hex_bgr(f["stroke"])
            cv2.polylines(img, [to_px(f["ll"])], False, (b, g, r, 255), 2, cv2.LINE_AA, 3)
    # viền lô tối mảnh — giống bản vẽ quy hoạch, nhìn rõ từng lô
    e = (edge.astype(np.float32) / 255 * 0.55)[..., None]
    img[..., :3] = (img[..., :3].astype(np.float32) * (1 - e) + np.array([40, 40, 40]) * e).astype(np.uint8)
    cv2.imwrite(os.path.join(out_dir, "quy_hoach.png"), img)

    # ---------------------------------------------------------- ranh khu quy hoạch = hợp mọi lô, nối khe đường nội khu
    rs = 10.0 * k                                       # lưới ranh 10 m/px
    rw, rh = int(math.ceil(span[0] / rs)), int(math.ceil(span[1] / rs))
    mask = np.zeros((rh, rw), np.uint8)
    for f in polys:
        cv2.fillPoly(mask, [((geo.lls2m(r) - m0) / rs).round().astype(np.int32) for r in f["rings"]], 255)
    ks = max(3, int(round(a.dong_ranh_m / 10)) * 2 + 1)
    cl = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ks, ks)))
    cnts, _ = cv2.findContours(cl, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)
    if not cnts:
        raise SystemExit("⛔ Không dựng được ranh.")
    tot = sum(cv2.contourArea(c) for c in cnts)
    main_c = cnts[0]
    parts = [c for c in cnts[1:] if cv2.contourArea(c) >= 0.02 * cv2.contourArea(main_c)]
    to_ll = lambda c: [tuple(round(v, 6) for v in geo.m2ll(*(m0 + p * rs))) for p in c.reshape(-1, 2).astype(float)]
    simp = lambda c: cv2.approxPolyDP(c, 1.5, True)     # ±15 m
    ranh = to_ll(simp(main_c))
    ranh_phu = [to_ll(simp(c)) for c in parts]
    share = cv2.contourArea(main_c) / max(tot, 1)
    # tâm: điểm sâu nhất trong phần ĐẤT QUY HOẠCH thật (không rơi vào lỗ làng xóm hiện hữu giữa khu) — ghim + thẻ dự án
    one = np.zeros_like(cl)
    cv2.drawContours(one, [main_c], -1, 255, -1)
    lots = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    dt = cv2.distanceTransform(cv2.bitwise_and(one, lots), cv2.DIST_L2, 5)
    cy, cx = np.array(one.shape) / 2                     # ưu tiên gần giữa khu: trừ nhẹ theo khoảng cách tới tâm khung
    yy, xx = np.mgrid[0:one.shape[0], 0:one.shape[1]]
    dt = dt - 0.08 * np.hypot(yy - cy, xx - cx)
    yx = np.unravel_index(int(np.argmax(dt)), dt.shape)
    tam = tuple(round(v, 6) for v in geo.m2ll(*(m0 + np.array([yx[1], yx[0]], float) * rs)))
    ha = lambda c: cv2.contourArea(c) * 100 / 1e4      # 10 m/px → 100 m²/px
    print(f"  ranh chính {ha(main_c):.0f} ha ({share * 100:.0f} % tổng), {len(ranh)} đỉnh"
          + (f"; {len(parts)} mảng tách rời: " + ", ".join(f"{ha(c):.0f} ha" for c in parts) if parts else ""))

    # ---------------------------------------------------------- thống kê loại đất
    by = {}
    for f in polys:
        d = by.setdefault(f["ten"] or "(không tên)", dict(ten=f["ten"] or "(không tên)", mau="#" + f["fill"], so_lo=0, dien_tich_ha=0.0))
        d["so_lo"] += 1
        d["dien_tich_ha"] += f["area_m2"] / 1e4
    loai = sorted(by.values(), key=lambda d: -d["dien_tich_ha"])
    for d in loai:
        d["dien_tich_ha"] = round(d["dien_tich_ha"], 1)
    diem = [dict(ten=f["ten"], lop=f["lop"], latlon=list(f["ll"][0])) for f in feats if f["kind"] == "diem" and f["ten"]]
    out = dict(nguon=a.link, mid=mid, tieu_de=title, lop=layers, loai_dat=loai,
               dien_tich_ranh_ha=round(ha(main_c), 1), dien_tich_cac_lo_ha=round(sum(f["area_m2"] for f in polys) / 1e4, 1),
               bounds=[[round(N, 6), round(W, 6)], [round(S_, 6), round(E, 6)]], tam=list(tam),
               ranh=[list(p) for p in ranh], ranh_phu=[[list(p) for p in r] for r in ranh_phu],
               anh="quy_hoach.png", diem=diem[:200], dong_ranh_m=a.dong_ranh_m,
               ghi_chu="ranh = hợp mọi lô quy hoạch, khe ≤ dong_ranh_m coi là liền; sai số mép ~±15 m")
    geo.save_json(os.path.join(out_dir, "quy_hoach.json"), out)

    # ---------------------------------------------------------- ảnh soát
    sc = 1400 / max(w, h)
    small = cv2.resize(img, (int(w * sc), int(h * sc)), interpolation=cv2.INTER_AREA)
    bg = np.full(small.shape[:2] + (3,), 24, np.uint8)
    a_ = small[..., 3:4].astype(np.float32) / 255
    vis = (bg * (1 - a_) + small[..., :3] * a_).astype(np.uint8)
    rp = lambda ll: ((geo.lls2m(ll) - m0) / res * sc).round().astype(np.int32)
    cv2.polylines(vis, [rp(ranh)], True, (0, 215, 255), 3, cv2.LINE_AA)
    for r in ranh_phu:
        cv2.polylines(vis, [rp(r)], True, (0, 160, 255), 2, cv2.LINE_AA)
    c = rp([tam])[0]
    cv2.circle(vis, tuple(int(v) for v in c), 9, (60, 40, 230), -1, cv2.LINE_AA)
    from PIL import Image, ImageDraw, ImageFont
    import common as C
    pim = Image.fromarray(cv2.cvtColor(vis, cv2.COLOR_BGR2RGB))
    lg = Image.new("RGB", (560, pim.height), (24, 24, 24))
    dr = ImageDraw.Draw(lg)
    f1 = ImageFont.truetype(C.F_LEGEND, 20)
    y = 14
    dr.text((14, y), title[:46], font=f1, fill=(255, 220, 90)); y += 34
    for d in loai[:28]:
        dr.rectangle([14, y + 3, 40, y + 21], fill=tuple(int(d["mau"][i:i + 2], 16) for i in (1, 3, 5)))
        dr.text((50, y), f"{d['ten'][:34]} · {d['so_lo']} lô · {d['dien_tich_ha']:.0f} ha", font=f1, fill=(235, 235, 235))
        y += 28
    y += 10
    dr.text((14, y), f"Ranh chính {out['dien_tich_ranh_ha']:.0f} ha (vàng) · chấm đỏ = tâm", font=f1, fill=(255, 220, 90))
    sheet = Image.new("RGB", (pim.width + lg.width, pim.height))
    sheet.paste(pim, (0, 0)); sheet.paste(lg, (pim.width, 0))
    sheet.save(os.path.join(out_dir, "quy_hoach_xem.jpg"), quality=88)
    print(f"● Ghi {out_dir}\\quy_hoach.json + quy_hoach.png + quy_hoach_xem.jpg — Claude MỞ quy_hoach_xem.jpg ra nhìn")
    print(f"  tâm {tam[0]:.6f}, {tam[1]:.6f} · {len(loai)} loại đất · {len(diem)} điểm có tên trên bản đồ")


if __name__ == "__main__":
    main()
