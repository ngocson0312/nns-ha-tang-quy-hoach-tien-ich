"""Kiểm tra máy đã đủ đồ để chạy skill chưa: Python, thư viện, ffmpeg, mạng tới các nguồn bản đồ.

    python scripts/kiem_tra_cai_dat.py

In ✓ / ✗ từng mục kèm cách sửa. Không cài gì, không ghi file.
"""
import importlib, os, shutil, subprocess, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)   # in đúng thứ tự khi gọi lồng nhau / qua ống dẫn
except Exception:
    pass

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEN_SKILL = os.path.basename(SKILL)

# (tên import, tên gói pip)
THU_VIEN = [("numpy", "numpy"), ("scipy", "scipy"), ("cv2", "opencv-python"), ("PIL", "Pillow"),
            ("requests", "requests"), ("skimage", "scikit-image"), ("fontTools", "fonttools")]
MANG = [("Ảnh vệ tinh Esri", "GET", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/10/450/812"),
        ("Tìm địa điểm (Photon)", "GET", "https://photon.komoot.io/api/?q=Ha%20Noi&limit=1"),
        ("Dữ liệu OpenStreetMap (Overpass)", "OVERPASS", None)]
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
UA = {"User-Agent": f"{TEN_SKILL}-kiem-tra/1.0"}

loi = []
canh_bao = []


def dong(ok, ten, chi_tiet=""):
    print(f"  {'✓' if ok else '✗'} {ten}" + (f" — {chi_tiet}" if chi_tiet else ""))
    return ok


def main():
    print(f"Kiểm tra cài đặt cho skill «{TEN_SKILL}»\n")

    print("1. Python")
    v = sys.version_info
    if not dong(v >= (3, 10), f"Python {v.major}.{v.minor}.{v.micro}", "cần 3.10 trở lên" if v < (3, 10) else ""):
        loi.append("Cài Python 3.10+ tại https://www.python.org/downloads/ (Windows: tick 'Add python.exe to PATH').")

    print("\n2. Thư viện Python")
    thieu = []
    for mod, pip_ten in THU_VIEN:
        try:
            m = importlib.import_module(mod)
            dong(True, pip_ten, getattr(m, "__version__", ""))
        except Exception as e:
            dong(False, pip_ten, f"chưa cài ({type(e).__name__})")
            thieu.append(pip_ten)
    try:
        import cv2
        cv2.SIFT_create()
    except Exception:
        if "opencv-python" not in thieu:
            dong(False, "opencv có SIFT", "bản opencv quá cũ")
            thieu.append("opencv-python")
    if thieu:
        loi.append(f"Cài thư viện: python -m pip install -r \"{os.path.join(SKILL, 'requirements.txt')}\"")

    print("\n3. ffmpeg")
    ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    dong(bool(ff), "ffmpeg", ff or "không thấy trong PATH")
    dong(bool(fp), "ffprobe", fp or "không thấy trong PATH")
    if ff:
        enc = subprocess.run([ff, "-hide_banner", "-encoders"], capture_output=True, text=True, errors="replace").stdout
        flt = subprocess.run([ff, "-hide_banner", "-filters"], capture_output=True, text=True, errors="replace").stdout
        for ten, ok in (("bộ mã hoá libx264", "libx264" in enc), ("bộ lọc alimiter", " alimiter " in flt),
                        ("bộ lọc ebur128 (đo độ to)", " ebur128 " in flt)):
            if not dong(ok, ten):
                loi.append("Bản ffmpeg này thiếu tính năng — cài bản đầy đủ (Windows: gói 'full' của gyan.dev).")
    if not (ff and fp):
        loi.append("Cài ffmpeg: Windows `winget install Gyan.FFmpeg` · macOS `brew install ffmpeg` · Ubuntu `sudo apt install ffmpeg` "
                   "(cài xong mở lại cửa sổ dòng lệnh / Claude Code).")

    print("\n4. Mạng (skill tải ảnh vệ tinh + dữ liệu bản đồ lúc chạy)")
    try:
        import requests
    except Exception:
        dong(False, "bỏ qua — chưa có thư viện requests")
        requests = None
    if requests:
        for ten, kieu, url in MANG:
            if kieu == "OVERPASS":
                ok_any = None
                for u in OVERPASS:
                    try:
                        r = requests.post(u, data={"data": "[out:json][timeout:20];node(1);out;"}, headers=UA, timeout=30)
                        if r.status_code == 200:
                            ok_any = u
                            break
                    except Exception:
                        pass
                if ok_any:
                    dong(True, ten, ok_any)
                else:                                   # máy chủ công cộng hay quá tải; lúc chạy skill tự thử lại 8 lần, 4 máy chủ
                    print(f"  ⚠ {ten} — lúc này mọi máy chủ đều bận/không trả lời")
                    canh_bao.append("Overpass đang bận — skill tự thử lại khi chạy; nếu lần nào cũng báo thế thì kiểm tra tường lửa/proxy.")
                continue
            try:
                r = requests.get(url, headers=UA, timeout=30)
                if not dong(r.status_code == 200, ten, f"HTTP {r.status_code}"):
                    loi.append(f"Không truy cập được {ten} — kiểm tra mạng/tường lửa.")
            except Exception as e:
                dong(False, ten, type(e).__name__)
                loi.append(f"Không truy cập được {ten} — kiểm tra mạng/tường lửa.")

    print("\n5. Thư mục skill")
    for p in ("SKILL.md", os.path.join("assets", "fonts"), os.path.join("assets", "sfx")):
        if not dong(os.path.exists(os.path.join(SKILL, p)), p):
            loi.append("Thiếu file của skill — giải nén lại nguyên thư mục.")
    parent = os.path.dirname(SKILL)
    dung_cho = os.path.basename(parent) == "skills" and os.path.basename(os.path.dirname(parent)) == ".claude"
    dong(dung_cho, "nằm trong thư mục .claude/skills/", "" if dung_cho else
         f"đang ở {parent} — chép thư mục skill vào <dự án>/.claude/skills/ hoặc ~/.claude/skills/ để Claude Code nhận ra")
    if not dung_cho:
        loi.append("Chép thư mục skill vào <dự án>/.claude/skills/ (hoặc ~/.claude/skills/) rồi mở lại Claude Code.")

    print()
    for s_ in dict.fromkeys(canh_bao):
        print(f"⚠ {s_}")
    if loi:
        print("CẦN SỬA:")
        for i, s in enumerate(dict.fromkeys(loi), 1):
            print(f"  {i}. {s}")
        sys.exit(1)
    print("✅ Máy đã sẵn sàng. Mở Claude Code trong thư mục dự án và gõ /" + TEN_SKILL)


if __name__ == "__main__":
    main()
