"""Tự kiểm trên FILE CUỐI (đo, không tin kế hoạch).

  python verify.py --video out.mp4 --plan work/plan.json --stems work/stems [--out work/verify.json]

 1 định dạng      1080×1920, 30 khung/s (đếm khung thật — r_frame_rate có thể nói dối), thời lượng khớp kế hoạch
 2 độ to          −14 ±1 LUFS, true peak ≤ −1 dBTP
 3 khe im         không có đoạn im < −60 dB dài ≥ 0,1 s (trừ 1,6 s fade cuối) — lỗi của video mẫu
 4 SFX đúng chỗ   khớp mẫu sóng từng SFX trong âm thanh cuối (đã trừ nhạc), lệch ≤ 1 khung, tương quan ≥ 0,5
 5 SFX nghe rõ    đỉnh SFX ≥ nhạc + 1 dB tại chỗ đặt
 6 máy quay êm    ORB + RANSAC từng cặp khung: lia ≤ 14 px/khung, zoom ≤ 7 %/khung (p99; tối đa ≤ +15 %)
 7 đúng toạ độ    SIFT khung cuối ↔ ảnh vệ tinh Esri ở 5 thời điểm: lệch ≤ 3 px (≈ vài chục m)
 8 chữ            mọi nhãn trong vùng an toàn, hai nhãn chồng nhau ≤ 6 % diện tích nhãn nhỏ
 9 tile           mọi tile ảnh vệ tinh cần dùng đều có trong cache (không có ô trống)
"""
import argparse, json, math, os, subprocess, sys
import numpy as np, cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import geo
import sprites as SP
import plan as PL
import audio as AU

W, H, FPS = C.W, C.H, C.FPS


def probe(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                          "stream=width,height,avg_frame_rate,nb_read_frames", "-of", "json", video],
                         capture_output=True, text=True).stdout
    s = json.loads(out)["streams"][0]
    a, b = map(int, s["avg_frame_rate"].split("/"))
    return s["width"], s["height"], a / b, int(s["nb_read_frames"])


def check_audio(video, plan, stems, res):
    T = plan["meta"]["duration"]
    tmp = os.path.join(stems, "_final.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-ac", "2", "-ar", str(AU.SR), "-c:a", "pcm_f32le", tmp], check=True)
    I, TP = AU.lufs(tmp)
    meta = geo.load_json(os.path.join(stems, "cues.json"))
    has_music = meta.get("has_music", True)
    if has_music:
        res["2_do_to"] = dict(ok=(abs(I - C.LUFS) <= 1.0 and TP <= -1.0), I=I, TP=TP)
    else:                                                # chỉ SFX: kiểm độ to tức thời lớn nhất + true peak
        M = AU.momentary_max(tmp)
        res["2_do_to"] = dict(ok=(abs(M - C.SFX_ONLY_PEAK_LUFS_M) <= 1.5 and TP <= -1.0), I=I, M_max=M, TP=TP, ghi_chu="không có nhạc")
    out = subprocess.run(["ffmpeg", "-v", "info", "-i", tmp, "-af", "silencedetect=n=-60dB:d=0.1", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    gaps = [float(l.split("silence_start:")[1]) for l in out.splitlines() if "silence_start:" in l]
    gaps = [g for g in gaps if 0.3 < g < T - 1.6]
    if has_music:
        res["3_khe_im"] = dict(ok=not gaps, gaps=gaps)
    else:
        res["3_khe_im"] = dict(ok=True, ghi_chu="không có nhạc — lặng giữa các SFX là đúng")

    fin = AU.load(tmp).mean(1)
    mus = AU.load(os.path.join(stems, "music.wav")).mean(1)
    sfx_st = AU.load(os.path.join(stems, "sfx.wav")).mean(1)
    cues = meta["cues"]
    # căn toàn cục (độ trễ bộ mã hoá AAC) bằng tương quan nhạc ↔ file cuối quanh giây thứ 2–6
    a0, a1 = int(2 * AU.SR), int(6 * AU.SR)
    best = (0, -1)
    for lag in range(-2400, 2401, 16):
        x = fin[a0 + lag:a1 + lag]; y = mus[a0:a1] + sfx_st[a0:a1]
        r = float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-9))
        if r > best[1]:
            best = (lag, r)
    lag0 = best[0]
    for lag in range(lag0 - 16, lag0 + 17):
        x = fin[a0 + lag:a1 + lag]; y = mus[a0:a1] + sfx_st[a0:a1]
        r = float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-9))
        if r > best[1]:
            best = (lag, r)
    lag0 = best[0]
    n = min(len(fin) - max(lag0, 0), len(mus))
    al = fin[max(lag0, 0):max(lag0, 0) + n] if lag0 >= 0 else np.concatenate([np.zeros(-lag0, np.float32), fin])[:n]
    g = float(np.dot(al, mus[:n] + sfx_st[:n]) / (np.dot(mus[:n] + sfx_st[:n], mus[:n] + sfx_st[:n]) + 1e-9))
    resid = al - g * mus[:n]
    rows, bad_t, bad_a = [], 0, 0
    cache = {}
    for cu in cues:
        f = cu["file"]
        if f not in cache:
            y = AU.load(os.path.join(C.SFX_DIR, f)).mean(1)
            on = AU.onset(np.stack([y, y], 1))
            cache[f] = (y, on)
        y_, on_ = cache[f]
        a_ = int((on_ + cu.get("skip", 0.0)) * AU.SR)              # tiếng bị cắt đầu (cú bay sớm) → mẫu so cũng bỏ phần đó
        used = y_[a_:]
        # so mẫu ở đoạn 0,15 s TO NHẤT của tiếng (whoosh dâng chậm: 0,15 s đầu gần như câm → so ở đó luôn ra r ≈ 0)
        wl = int(0.15 * AU.SR)
        hop_ = int(0.025 * AU.SR)
        en_ = [float(np.sum(used[i:i + wl] ** 2)) for i in range(0, max(1, len(used) - wl), hop_)]
        w0 = int(np.argmax(en_)) * hop_ if en_ else 0
        tpl = used[w0:w0 + wl]
        c0 = int(cu["t"] * AU.SR) + w0
        lo, hi = c0 - int(0.12 * AU.SR), c0 + int(0.12 * AU.SR)
        seg = resid[max(0, lo):min(len(resid), hi + len(tpl))]
        if len(seg) < len(tpl) + 10:
            continue
        cc = np.correlate(seg, tpl, "valid")
        en = np.sqrt(np.convolve(seg ** 2, np.ones(len(tpl)), "valid")) * np.linalg.norm(tpl) + 1e-9
        r = cc / en
        j = int(np.argmax(r))
        dt = (max(0, lo) + j - c0) / AU.SR
        # khớp trúng 1 cue CÙNG FILE khác ở gần (2 tiếng giống nhau cách < 0,12 s) cũng là đúng chỗ
        other = [c2["t"] for c2 in cues if c2 is not cu and c2["file"] == f and abs(c2["t"] - (cu["t"] + dt)) <= 1.0 / FPS]
        ok_t = (abs(dt) <= 1.0 / FPS or bool(other)) and r[j] >= 0.45     # 0,45: whoosh chồng tiếng pop vẫn kéo r xuống ~0,49
        # nghe rõ: đỉnh RMS 50 ms của SFX so nhạc trong 0,4 s quanh mốc
        w = int(0.05 * AU.SR)
        span = int(3.0 * AU.SR)                          # cả đoạn đỉnh của whoosh dâng chậm (whoosh.wav đỉnh ở ~1,5 s), không chỉ 0,4 s đầu
        s_seg = sfx_st[c0:c0 + span]
        e_s = [np.sqrt(np.mean(s_seg[i:i + w] ** 2)) for i in range(0, max(1, len(s_seg) - w), w // 2)]
        ip = int(np.argmax(e_s)) * (w // 2)
        s_seg = s_seg[max(0, ip - w * 4):ip + w * 4]
        m_seg = mus[c0 + max(0, ip - w * 4):c0 + ip + w * 4]
        pk = lambda v: 20 * np.log10(max(np.sqrt(np.mean(v[i:i + w] ** 2)) for i in range(0, max(1, len(v) - w), w // 2)) + 1e-9)
        diff = pk(s_seg) - pk(m_seg)
        ok_a = diff >= 1.0
        bad_t += not ok_t; bad_a += not ok_a
        rows.append(dict(t=float(cu["t"]), name=cu["name"], lech_ms=round(float(dt) * 1000, 1), r=round(float(r[j]), 2), tren_nhac_db=round(float(diff), 1)))
    res["4_sfx_dung_cho"] = dict(ok=bad_t == 0, n=len(rows), sai=bad_t, aac_lag_ms=round(lag0 / AU.SR * 1000, 1), chi_tiet=rows)
    res["5_sfx_nghe_ro"] = dict(ok=bad_a == 0, sai=bad_a, chi_tiet=[r for r in rows if r["tren_nhac_db"] < 1.0])
    os.remove(tmp)


def check_camera(video, res):
    cap = cv2.VideoCapture(video)
    orb = cv2.ORB_create(2500)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    prev = None
    pans, zooms, ts = [], [], []
    i = 0
    sc = 360 / W
    while True:
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(cv2.resize(f, (360, 640), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        k, d = orb.detectAndCompute(g, None)
        if prev is not None and d is not None and prev[1] is not None and len(k) > 30:
            ms = bf.match(prev[1], d)
            if len(ms) > 30:
                A = np.float32([prev[0][m.queryIdx].pt for m in ms]); B = np.float32([k[m.trainIdx].pt for m in ms])
                M, inl = cv2.estimateAffinePartial2D(A, B, method=cv2.RANSAC, ransacReprojThreshold=1.5)
                if M is not None and inl.sum() > 40:
                    s = math.hypot(M[0, 0], M[1, 0])
                    c = np.array([180, 320]); q = M @ [180, 320, 1]
                    pans.append(float(np.linalg.norm(q - c)) / sc)
                    zooms.append(abs(math.log(s)) * 100)
                    ts.append(i / FPS)
        prev = (k, d)
        i += 1
    pans, zooms = np.array(pans), np.array(zooms)
    p99p, p99z = float(np.percentile(pans, 99)), float(np.percentile(zooms, 99))
    ok = p99p <= C.MAX_PAN_PX and p99z <= C.MAX_ZOOM_PCT and pans.max() <= 1.15 * C.MAX_PAN_PX and zooms.max() <= 1.15 * C.MAX_ZOOM_PCT
    res["6_may_quay_em"] = dict(ok=bool(ok), lia_p99=round(p99p, 1), lia_max=round(float(pans.max()), 1), lia_max_t=round(ts[int(pans.argmax())], 2),
                                zoom_p99=round(p99z, 2), zoom_max=round(float(zooms.max()), 2), zoom_max_t=round(ts[int(zooms.argmax())], 2))


def check_geo(video, plan, res):
    k = plan["meta"]["k"]
    cam = plan["camera"]
    T = plan["meta"]["duration"]
    # khung kết: đo khi máy ĐÃ dừng (lùi toàn cảnh dài thì legend_t + 1 còn rơi vào lúc bay → lệch giả do nửa khung,
    # Vinhomes Olympic 10/11: 18,65 s đang bay tới 18,8 s → báo lệch 2,7 px)
    times = [ch["t_end"] - 0.4 for ch in plan["chapters"]] + [max(plan["outro"]["legend_t"] + 1.0, plan["outro"]["t"] + 0.3)]
    if plan.get("masterplan"):
        times = [max(0.2, plan["masterplan"]["t_out"][0] - 0.2)] + times
    import render as RD
    clahe = cv2.createCLAHE(3.0, (8, 8))
    prep = lambda im: clahe.apply(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
    sift = cv2.SIFT_create(12000)
    rows = []
    for t in times:
        t = min(t, T - 3.0 / FPS)            # -ss sát giây cuối → ffmpeg không ra khung (Vinhomes Olympic _ban4: 42,25 / 42,27 s)
        fr = b""
        for _ in range(4):
            fr = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                                capture_output=True).stdout
            if len(fr) == H * W * 3:
                break
            t -= 2.0 / FPS
        img = np.frombuffer(fr, np.uint8).reshape(H, W, 3)
        c, u = PL.camera_at(cam, t, k)
        z = RD.levels_for(u)[0][0]
        lat0, lon0 = geo.m2ll(c[0] - W / 2 * u * 1.15, c[1] + H / 2 * u * 1.15)
        lat1, lon1 = geo.m2ll(c[0] + W / 2 * u * 1.15, c[1] - H / 2 * u * 1.15)
        mos, org, mpp = geo.mosaic(z, lat0, lat1, lon0, lon1)
        s_ = min(1.0, 3000 / max(mos.shape[:2]))
        mos_s = cv2.resize(mos, None, fx=s_, fy=s_, interpolation=cv2.INTER_AREA) if s_ < 1 else mos
        kf, df = sift.detectAndCompute(prep(img), None)
        km, dm = sift.detectAndCompute(prep(mos_s), None)
        if df is None or dm is None:
            rows.append(dict(t=round(t, 2), ok=False, note="không có điểm đặc trưng")); continue
        mt = cv2.BFMatcher().knnMatch(df, dm, k=2)
        good = [a for a, b in (m for m in mt if len(m) == 2) if a.distance < 0.75 * b.distance]
        if len(good) < 20:
            rows.append(dict(t=round(t, 2), ok=False, note=f"chỉ {len(good)} cặp khớp")); continue
        A = np.float32([kf[g.queryIdx].pt for g in good]); B = np.float32([km[g.trainIdx].pt for g in good]) / s_
        M, inl = cv2.estimateAffinePartial2D(A, B, method=cv2.RANSAC, ransacReprojThreshold=3)
        gx, gy = np.meshgrid(np.linspace(100, W - 100, 9), np.linspace(250, H - 250, 9))
        P = np.stack([gx.ravel(), gy.ravel(), np.ones(81)], 1)
        true_m = (P @ M.T) * mpp + org                      # mét Mercator theo ảnh vệ tinh
        plan_m = (P[:, :2] - [W / 2, H / 2]) * u + c        # mét Mercator theo camera kế hoạch
        err_px = np.linalg.norm(true_m - plan_m, axis=1) / u
        rows.append(dict(t=round(t, 2), inliers=int(inl.sum()), lech_px_tb=round(float(err_px.mean()), 2),
                         lech_px_max=round(float(err_px.max()), 2), lech_m_tb=round(float(err_px.mean() * u / k), 1),
                         ok=bool(err_px.max() <= 3.0 and inl.sum() >= 15)))   # 22–24 điểm khớp vẫn cho lệch 0,5 px (khung tối spotlight, B 17/10)
    res["7_dung_toa_do"] = dict(ok=all(r.get("ok") for r in rows), chi_tiet=rows)


def label_boxes(plan, t):
    """hộp màn hình mọi nhãn đang hiện (alpha ≥ 0,5) tại t — cùng luật hiện/ẩn với render.py."""
    k = plan["meta"]["k"]
    c, u = PL.camera_at(plan["camera"], t, k)
    scr = lambda m: (np.asarray(m, float) - c) / u + np.array([W / 2, H / 2])
    boxes = []
    routes = {kk: dict(v, P=np.array(v["P"]), L=geo.cumlen(np.array(v["P"]))) for kk, v in plan["routes"].items()}

    def add(name, spr, x, y, edge_ok=False):
        arr, (ax, ay) = spr
        h, w = arr.shape[:2]
        a = arr[..., 3] > 60                             # hộp mực thật, bỏ bóng mờ
        ys, xs = np.nonzero(a)
        if len(xs):
            boxes.append((name, x - ax + xs.min(), y - ay + ys.min(), x - ax + xs.max(), y - ay + ys.max(), edge_ok))

    def near_edge(s, spot):
        return C.EDGE_FIT and spot and (s[0] < C.EDGE_CROP_ZONE or s[0] > W - C.EDGE_CROP_ZONE)
    for q in plan["pois"]:
        if q["t"] is None:
            continue
        ch = plan["chapters"][q["chapter"]]
        col = routes[q["route"]]["color"]
        s = scr(q["m"])
        tc = q.get("t_collapse") if q.get("t_collapse") is not None else ch["t_end"]
        if (q.get("t_label") or q["t"]) + 0.02 <= t <= tc + 0.28 and q["off"]:     # cả lúc đang hiện/mờ dần
            add(" ".join(q["lines"]), SP.poi_label(tuple(q["lines"]), col, q["sub"], False, q.get("scale", 1.0)), s[0] + q["off"][0], s[1] + q["off"][1],
                near_edge(s, ch["spot"]))
        if q.get("off_short") and tc + 0.32 <= t <= ch["t_end"]:
            add(" ".join(q["short"]), SP.poi_label(tuple(q["short"]), col, None, True), s[0] + q["off_short"][0], s[1] + q["off_short"][1],
                near_edge(s, ch["spot"]))
        if q.get("final") and not q.get("outro_hide") and t >= plan["outro"]["t"] + 0.3:
            f = q["final"]
            add(" ".join(f["lines"]), SP.poi_label(tuple(f["lines"]), col, None, True), s[0] + f["off"][0], s[1] + f["off"][1],
                near_edge(s, True))
    for lr in plan["route_labels"]:
        ch = plan["chapters"][lr["chapter"]]
        if lr["t"] + 0.15 <= t <= ch["t_end"]:
            r = routes[lr["route"]]
            q = scr(geo.point_at(r["P"], r["L"], lr["s"])) + np.array(lr["off"])
            add(lr["text"], SP.route_label(lr["text"], r["color"], lr.get("sub")), q[0], q[1])
    for ch in plan["chapters"]:
        if ch["t_title"] + C.CHAPTER_IN * 0.5 <= t <= ch["t_end"]:
            add("chương: " + ch["title"], SP.chapter_title(ch["title"]), ch["pos"][0], ch["pos"][1])
    if t >= plan["outro"]["legend_t"] + C.LEGEND_IN:
        add("chú giải", SP.legend(tuple(tuple(x) for x in plan["outro"]["legend_items"])), W / 2, plan["outro"]["legend_y"])
    # thẻ dự án (để bắt thẻ cụt mép / chữ đè thẻ)
    pr = plan["project"]
    sw = pr["switch_u"]
    spr = SP.project_card(pr["name"], pr["sub"], False, pr["logo"]) if u < sw else SP.project_card(pr["name"], None, True, pr["logo"])
    bx = PL.card_box(scr(pr["m"]), spr, pr.get("card_side", "tren"))
    boxes.append(("thẻ dự án", *bx, False))
    return boxes


def check_text(plan, res):
    T = plan["meta"]["duration"]
    out_rows, ov_rows, cut_rows = [], [], []
    start = plan["cover"]["t1"] if plan.get("cover") else 0
    sat = plan["meta"].get("khung_sat")

    def moving(t):
        for sg in plan["camera"]:
            if sg["t0"] <= t <= sg["t1"]:
                return sg["mode"] != "hold"
        return False
    for t in np.arange(start, T, 0.25):
        b = label_boxes(plan, float(t))
        for n, x0, y0, x1, y1, edge_ok in b:
            out_x = x0 < C.SAFE_X0 - 2 or x1 > C.SAFE_X1 + 2
            out_y = y0 < C.SAFE_Y0 - 2 or y1 > C.SAFE_Y1 + 2
            if sat and n == "thẻ dự án" and (out_x or out_y):
                # khung_sat: chương zoom sát line, thẻ dự án nằm hẳn ngoài khung là đúng ý; lướt qua mép chỉ khi máy đang bay
                if x1 < 0 or x0 > W or y1 < 0 or y0 > H:
                    continue
                if moving(float(t)):
                    cut_rows.append((round(float(t), 2), n)); continue
            if out_y or (out_x and not edge_ok):
                out_rows.append((round(float(t), 2), n))
            elif out_x:
                cut_rows.append((round(float(t), 2), n))         # ghim sát mép, nhãn được cắt (EDGE_FIT)
        for i in range(len(b)):
            for j in range(i + 1, len(b)):
                _, a0, b0, a1, b1, _e = b[i]; _, c0, d0, c1, d1, _e2 = b[j]
                ix = max(0, min(a1, c1) - max(a0, c0)); iy = max(0, min(b1, d1) - max(b0, d0))
                small = min((a1 - a0) * (b1 - b0), (c1 - c0) * (d1 - d0))
                if small > 0 and ix * iy / small > 0.06:
                    ov_rows.append((round(float(t), 2), b[i][0], b[j][0], round(ix * iy / small, 2)))
    uniq = lambda rows, key: list({key(r): r for r in rows}.values())
    out_u = uniq(out_rows, lambda r: r[1]); ov_u = uniq(ov_rows, lambda r: (r[1], r[2])); cut_u = uniq(cut_rows, lambda r: r[1])
    # ghim chồng nhau (cùng lúc trên màn hình, chưa bị ẩn) — ghim đè ghim là rối
    pin_rows = []
    k = plan["meta"]["k"]
    for t in np.arange(start, T, 0.5):
        c, u = PL.camera_at(plan["camera"], float(t), k)
        vis = [q for q in plan["pois"] if q["t"] is not None and q["t"] <= t
               and not (q.get("outro_hide") and t >= plan["outro"]["t_move"] + 0.5)
               and not any(a0 + 0.45 <= t <= a1 - 0.45 for a0, a1 in q.get("hide", []))
               and not (q.get("outro_hide") and t >= plan["outro"]["t_move"] + 0.5)]
        S = [(np.asarray(q["m"]) - c) / u + [W / 2, H / 2] for q in vis]
        for i in range(len(S)):
            for j in range(i + 1, len(S)):
                if np.linalg.norm(S[i] - S[j]) < C.PIN_MIN_GAP:
                    pin_rows.append((round(float(t), 1), " ".join(vis[i]["lines"]), " ".join(vis[j]["lines"])))
    pin_u = uniq(pin_rows, lambda r: (r[1], r[2]))
    res["8_chu"] = dict(ok=not out_u and not ov_u and not pin_u, ghim_chong=[f"{a} ↔ {b} (từ {t} s)" for t, a, b in pin_u],
                        ra_ngoai=[f"{n} (từ {t} s)" for t, n in out_u],
                        chong=[f"{a} ↔ {b} {int(f * 100)} % (từ {t} s)" for t, a, b, f in ov_u],
                        cat_o_mep_da_cho_phep=[f"{n} (từ {t} s)" for t, n in cut_u])


def check_tiles(plan, res):
    import render as RD
    need = RD.needed_tiles(plan)
    miss = [n for n in need if not os.path.exists(os.path.join(geo.TILE_CACHE, f"{n[0]}_{n[1]}_{n[2]}.jpg"))]
    res["9_tile"] = dict(ok=not miss, can=len(need), thieu=len(miss))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--stems", required=True)
    ap.add_argument("--out")
    ap.add_argument("--skip-camera", action="store_true")
    a = ap.parse_args()
    plan = geo.load_json(a.plan)
    res = {}
    w, h, fps, n = probe(a.video)
    T = plan["meta"]["duration"]
    res["1_dinh_dang"] = dict(ok=(w, h) == (W, H) and abs(fps - FPS) < 0.01 and abs(n / FPS - T) <= 0.1, w=w, h=h, fps=fps, khung=n, giay=round(n / fps, 2))
    print("● 1–5 định dạng & âm thanh…"); check_audio(a.video, plan, a.stems, res)
    if not a.skip_camera:
        print("● 6 máy quay (đo từng cặp khung)…"); check_camera(a.video, res)
    print("● 7 toạ độ (SIFT với ảnh vệ tinh)…"); check_geo(a.video, plan, res)
    print("● 8 chữ, 9 tile…"); check_text(plan, res); check_tiles(plan, res)
    names = {"1_dinh_dang": "Định dạng", "2_do_to": "Độ to", "3_khe_im": "Khe im", "4_sfx_dung_cho": "SFX đúng chỗ",
             "5_sfx_nghe_ro": "SFX nghe rõ", "6_may_quay_em": "Máy quay êm", "7_dung_toa_do": "Đúng toạ độ", "8_chu": "Chữ", "9_tile": "Tile"}
    print("\n══════════ TỰ KIỂM FILE CUỐI ══════════")
    npass = 0
    for key in sorted(res):
        r = res[key]
        npass += bool(r["ok"])
        detail = {kk: v for kk, v in r.items() if kk not in ("ok", "chi_tiet")}
        print(f" {'✓' if r['ok'] else '✗'} {names[key]:<14} {json.dumps(detail, ensure_ascii=False, default=float)[:260]}")
        if not r["ok"] and "chi_tiet" in r:
            for row in r["chi_tiet"]:
                if isinstance(row, dict) and (row.get("ok") is False or abs(row.get("lech_ms", 0)) > 1000 / FPS or row.get("r", 1) < 0.5 or row.get("tren_nhac_db", 9) < 1):
                    print("     ", json.dumps(row, ensure_ascii=False, default=float))
    print(f" ⇒ ĐẠT {npass}/{len(res)}")
    print("═══════════════════════════════════════")
    if a.out:
        geo.save_json(a.out, res)
    return 0 if npass == len(res) else 1


if __name__ == "__main__":
    sys.exit(main())
