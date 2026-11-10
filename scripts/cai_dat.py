"""Cài skill vào Claude Code bằng một lệnh (CAI_DAT.bat / CAI_DAT.command gọi file này).

    python scripts/cai_dat.py                 # cài cho mọi dự án: ~/.claude/skills/<skill>
    python scripts/cai_dat.py --du_an D:/abc  # chỉ cho một dự án: D:/abc/.claude/skills/<skill>

Làm 4 việc: chép thư mục skill vào đúng chỗ (giải nén lồng mấy lớp cũng được) → cài thư viện Python →
thiếu ffmpeg thì hỏi rồi cài (winget / brew) → chạy kiểm tra máy.
"""
import argparse, os, platform, shutil, subprocess, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)   # in đúng thứ tự khi gọi lồng nhau / qua ống dẫn
except Exception:
    pass

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEN = os.path.basename(SKILL)
BO_QUA = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", "Thumbs.db")


def hoi(cau):
    try:
        return input(f"{cau} (c/k): ").strip().lower() in ("c", "co", "có", "y", "yes")
    except EOFError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--du_an", help="thư mục dự án (bỏ trống = cài cho mọi dự án ở ~/.claude/skills)")
    ap.add_argument("--khong_hoi", action="store_true", help="không hỏi, không tự cài ffmpeg")
    a = ap.parse_args()

    print(f"=== Cài skill «{TEN}» cho Claude Code ===\n")
    if sys.version_info < (3, 10):
        print(f"⛔ Python {platform.python_version()} quá cũ — cần 3.10 trở lên: https://www.python.org/downloads/")
        sys.exit(1)

    # 1. chép skill vào .claude/skills
    goc = os.path.abspath(a.du_an) if a.du_an else os.path.expanduser("~")
    dich = os.path.join(goc, ".claude", "skills", TEN)
    print(f"1. Chép skill → {dich}")
    if os.path.normcase(os.path.abspath(dich)) == os.path.normcase(SKILL):
        print("   (đã nằm đúng chỗ — bỏ qua)")
    else:
        os.makedirs(os.path.dirname(dich), exist_ok=True)
        shutil.copytree(SKILL, dich, dirs_exist_ok=True, ignore=BO_QUA)
        print("   ✓ xong")

    # 2. thư viện Python
    print("\n2. Cài thư viện Python (lần đầu mất vài phút)…")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r",
                        os.path.join(dich, "requirements.txt")])
    if r.returncode != 0:
        print("   ⛔ pip báo lỗi — xem dòng lỗi phía trên (thường do mạng, hoặc cần chạy lại cửa sổ với quyền quản trị).")
        sys.exit(1)
    print("   ✓ xong")

    # 3. ffmpeg
    print("\n3. ffmpeg")
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        print("   ✓ đã có")
    else:
        he = platform.system()
        lenh = (["winget", "install", "-e", "--id", "Gyan.FFmpeg", "--accept-source-agreements", "--accept-package-agreements"]
                if he == "Windows" and shutil.which("winget") else
                ["brew", "install", "ffmpeg"] if he == "Darwin" and shutil.which("brew") else None)
        if lenh and not a.khong_hoi and hoi(f"   Chưa có ffmpeg. Cài bằng «{' '.join(lenh[:4])}…» ngay bây giờ?"):
            subprocess.run(lenh)
            print("   → cài xong thì ĐÓNG cửa sổ này, mở lại Claude Code để nhận ffmpeg.")
        else:
            print("   ✗ chưa có — cài tay: Windows `winget install Gyan.FFmpeg` · macOS `brew install ffmpeg` · "
                  "Ubuntu `sudo apt install ffmpeg`")

    # 4. kiểm tra
    print("\n4. Kiểm tra máy")
    r = subprocess.run([sys.executable, os.path.join(dich, "scripts", "kiem_tra_cai_dat.py")])
    print()
    if r.returncode == 0:
        print(f"🎉 Xong! Mở Claude Code (thư mục dự án nào cũng được) và gõ:  /{TEN} …")
    else:
        print("Còn mục ✗ ở trên — sửa theo dòng «CẦN SỬA», rồi chạy lại file cài đặt này.")
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
