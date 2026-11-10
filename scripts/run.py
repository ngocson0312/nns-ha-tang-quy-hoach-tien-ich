"""nns-ha-tang-quy-hoach-tien-ich — link bản đồ quy hoạch (Google My Maps) + danh sách tiện ích → video bản đồ.

  Bước 0 (đọc link My Maps → ranh + lớp quy hoạch; tìm toạ độ điểm trong <work>/tien_ich_vao.json; lập du_an.json):
    python run.py --link "<link My Maps>" --work THU_MUC [--ten "Tên in thẻ"] [--duong thang|thuc] [--tu_dong]
  Bước 1 (lập kế hoạch + xem trước, DỪNG ở cổng duyệt nội dung, mã thoát 2):
    python run.py --work THU_MUC
  Bước 2 (dựng hình + âm thanh + ghép + tự kiểm):
    python run.py --work THU_MUC --render [--out video.mp4] [--workers 6]
Không có --link thì chạy y như skill gốc nns-ban-do-ha-tang (--ten "địa điểm" tự khảo sát, hoặc --brief).
"""
import argparse, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C
import geo


def py(script, *args):
    r = subprocess.run([sys.executable, "-u", os.path.join(HERE, script), *args])
    return r.returncode


def preview_times(plan):
    ts = []
    if plan.get("cover"):
        ts.append(0.6)
    if plan.get("masterplan"):
        ts.append(plan["masterplan"]["xfade"][1] + 0.4)
    for ch in plan["chapters"]:
        if ch["spot"]:
            ts.append((ch["t_title"] + ch["t_end"]) / 2)
        ts.append(ch["t_end"] - 0.35)
    ts.append(plan["outro"]["legend_t"] + 1.0)
    return [round(min(t, plan["meta"]["duration"] - 0.05), 2) for t in ts]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", help="hồ sơ du_an.json (bỏ trống → <work>/du_an.json; chưa có thì tự khảo sát theo --ten)")
    ap.add_argument("--ten", help="tên địa điểm/công trình bất kỳ (vd \"Lăng Bác\", \"Hồ Tây\", \"Landmark 81\")")
    ap.add_argument("--vi_tri", help="lat,lon hoặc link Google Maps (khi tên tìm không ra / muốn chỉ đích danh)")
    ap.add_argument("--khao_sat_lai", action="store_true", help="khảo sát lại, ghi đè du_an.json")
    ap.add_argument("--work", required=True)
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--audio-only", action="store_true", help="dùng lại video_cam.mp4 đã dựng, chỉ làm lại âm thanh + ghép + tự kiểm")
    ap.add_argument("--link", help="link Google My Maps bản đồ quy hoạch (viewer?mid=…)")
    ap.add_argument("--duong", choices=["thang", "thuc"], default="thuc", help="line tới tiện ích: bám đường thật (mặc định) | thẳng chim bay")
    ap.add_argument("--tu_dong", action="store_true", help="tự khảo sát tiện ích quanh khu quy hoạch (gợi ý cho Claude chọn)")
    ap.add_argument("--nhac", help="file nhạc nền của user")
    a = ap.parse_args()
    os.makedirs(a.work, exist_ok=True)
    a.brief = a.brief or os.path.join(a.work, "du_an.json")
    qh = os.path.join(a.work, "quy_hoach", "quy_hoach.json")
    if a.link:                                               # ===== luồng QUY HOẠCH + TIỆN ÍCH
        if not os.path.exists(qh) and py("mymaps.py", "--link", a.link, "--work", a.work):
            return 1
        vao, ti = os.path.join(a.work, "tien_ich_vao.json"), os.path.join(a.work, "tien_ich.json")
        if a.tu_dong and py("tien_ich.py", "--work", a.work, "--tu_dong", "--vao", vao + ".chua_co"):
            return 1
        if not os.path.exists(vao):
            print(f"⛔ Chưa có {vao} — Claude viết danh sách điểm (tên, địa chỉ, link/toạ độ) từ lời user rồi chạy lại.")
            return 1
        if (not os.path.exists(ti) or os.path.getmtime(ti) < os.path.getmtime(vao)) and py("tien_ich.py", "--work", a.work):
            return 1
        if not os.path.exists(a.brief):
            args = ["--work", a.work, "--duong", a.duong] + (["--ten", a.ten] if a.ten else []) + (["--nhac", a.nhac] if a.nhac else [])
            if py("lap_ho_so.py", *args):
                return 1
            print("● Hồ sơ nháp đã lập — Claude soát du_an.json rồi chạy: run.py --work … (bước 1 xem trước)")
            return C.GATE_EXIT
    elif a.ten and (a.khao_sat_lai or not os.path.exists(a.brief)):
        args = ["--ten", a.ten, "--out", a.brief] + (["--vi_tri", a.vi_tri] if a.vi_tri else [])
        if py("khao_sat.py", *args):
            return 1
    if not os.path.exists(a.brief):
        print("⛔ Chưa có hồ sơ — cho --ten \"tên địa điểm\" (tự khảo sát) hoặc --brief du_an.json"); return 1
    plan_p = os.path.join(a.work, "plan.json")
    if py("plan.py", "--brief", a.brief, "--work", a.work):
        return 1
    plan = geo.load_json(plan_p)
    if py("render.py", "--plan", plan_p, "--prefetch"):
        return 1
    brief = geo.load_json(a.brief)
    bdir = os.path.dirname(os.path.abspath(a.brief))
    music = brief.get("nhac")
    music = music if (music is None or os.path.isabs(music)) else os.path.join(bdir, music)

    if not a.render and not a.audio_only:
        pv = os.path.join(a.work, "xem_truoc")
        os.makedirs(pv, exist_ok=True)
        for f in os.listdir(pv):                     # khung xem trước của lần chạy TRƯỚC (do chính skill sinh) — không xoá thì
            if f.startswith("f_") and f.endswith(".png"):   # tấm ghép trộn khung cũ/mới (gặp ở Matrix One 17/10)
                os.remove(os.path.join(pv, f))
        ts = preview_times(plan)
        py("render.py", "--plan", plan_p, "--frames", ",".join(map(str, ts)), "--outdir", pv)
        subprocess.run([sys.executable, os.path.join(HERE, "sheet.py"), pv, os.path.join(a.work, "xem_truoc")])
        print("\n⛔ CỔNG DUYỆT NỘI DUNG — xem bảng trên + ảnh xem_truoc_*.jpg:")
        print("   chữ trên nhãn, khoảng cách in ra, màu & icon từng tuyến, thứ tự chương, bìa, chú giải.")
        if not music:
            print("   ⚠ hồ sơ CHƯA có nhạc nền (khoá \"nhac\") — video sẽ chỉ có SFX.")
        elif not os.path.exists(music):
            print(f"   ⚠ không thấy file nhạc {music}")
        print("   Duyệt xong chạy lại với --render.")
        return C.GATE_EXIT

    t0 = time.time()
    silent = os.path.join(a.work, "video_cam.mp4")
    if a.audio_only and not os.path.exists(silent):
        print("⛔ chưa có video_cam.mp4 — chạy --render trước"); return 1
    if not a.audio_only and py("render.py", "--plan", plan_p, "--out", silent, "--workers", str(a.workers)):
        return 1
    wav = os.path.join(a.work, "audio.wav")
    stems = os.path.join(a.work, "stems")
    args = ["--plan", plan_p, "--out", wav, "--stems", stems]
    if music and os.path.exists(music):
        args += ["--music", music]
    if py("audio.py", *args):
        return 1
    out = a.out
    if not out:                                              # không ghi đè video cũ: _ban2, _ban3…
        goc = os.path.join(a.work, f"{brief['ten'].replace(' ', '_')}_ha_tang_quy_hoach")
        out, n = goc + ".mp4", 2
        while os.path.exists(out):
            out, n = f"{goc}_ban{n}.mp4", n + 1
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
                    # KHÔNG dùng -shortest: luồng AAC luôn ngắn hơn chút → cắt mất 4 khung cuối (Matrix One nhịp nhanh 18/10)
                    "-af", "apad", "-t", f"{plan['meta']['duration']:.3f}", out], check=True)
    print(f"● Ghép xong → {out} ({time.time() - t0:.0f} s)")
    rc = py("verify.py", "--video", out, "--plan", plan_p, "--stems", stems, "--out", os.path.join(a.work, "verify.json"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
