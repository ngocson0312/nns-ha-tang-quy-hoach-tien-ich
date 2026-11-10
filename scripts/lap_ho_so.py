"""quy_hoach.json (từ link My Maps) + tien_ich.json (điểm đã có toạ độ) → hồ sơ du_an.json cho plan.py.

  python lap_ho_so.py --work THU_MUC [--ten "Vinhomes Olympic"] [--the_phu "…"] [--duong thang|thuc]
                      [--cach_tinh chim_bay|theo_duong] [--nhac nhac.mp3] [--lap_lai]

Mỗi điểm = một tuyến "line sáng" chạy TỪ KHU QUY HOẠCH tới điểm đó + ghim + nhãn "cách <tên> ~X km / ~850 m".
Điểm dạng CỤM / QUẦN THỂ (tien_ich_vao "vung": xã, cụm CN…) → KHOANH VÙNG màu tuyến; line dừng ở MÉP vùng, km tới mép
vùng; vùng giáp ranh khu quy hoạch → chỉ khoanh vùng + nhãn "giáp khu quy hoạch" (không line).
Lớp màu quy hoạch phủ lên vệ tinh suốt video (phoi_canh giu=true), ranh vàng phát sáng.
  --duong thuc (MẶC ĐỊNH — user chốt 10/11/2026 "ai mà bay được, phải có đường đi chuẩn"): line BÁM ĐƯỜNG THẬT OSM,
                xuất phát từ lối ra ranh cho quãng ngắn nhất, qua cầu / phà thật; khoảng cách = QUÃNG ĐƯỜNG ĐI.
                Mặc định được đi cả đường/cầu ĐANG XÂY theo quy hoạch (VĐ4, cầu Mễ Sở…) — line ghi "QUA CẦU … / đang xây";
                --chi_van_hanh để chỉ đi đường đang chạy (phà thay cầu chưa xong).
  --duong thang: line thẳng chim bay — CHỈ khi user yêu cầu.
  loai "duong" (vd QL21B): tô cả tuyến đường OSM + ghim ở chỗ gần/cắt ranh.
Không ghi đè du_an.json đã có (Claude có thể đã sửa tay) — muốn lập lại thì --lap_lai.
"""
import argparse, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo
import khao_sat as KS

MAU = ["#FFB800", "#FE3A5A", "#1E90FF", "#2FC85E", "#CC75FF", "#FF7A1A", "#12B5A8", "#E040FB", "#00BCD4", "#8BC34A"]
GIAO_THONG = ("nutgiao", "cau", "ga", "sanbay")


def ten_tu_tieu_de(t):
    """«Nga Tây Vinhomes Olympic - Bản đồ quy hoạch 1/500 …» → «Nga Tây Vinhomes Olympic» (Claude sửa nếu là tên người đăng)."""
    return re.split(r"\s[-–|]\s", t or "")[0].strip() or "Khu quy hoạch"


def nhan_of(it):
    if it.get("nhan"):
        n = it["nhan"]
        return [x.upper() for x in (n if isinstance(n, list) else [n])]
    return KS.label_lines(KS.tach_ten(it["ten"])[0].upper())


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--ten")
    ap.add_argument("--the_phu")
    ap.add_argument("--duong", choices=["thang", "thuc"], default="thuc")
    ap.add_argument("--chi_van_hanh", action="store_true", help="không đi đường/cầu đang xây (mặc định: đi theo quy hoạch)")
    ap.add_argument("--cach_tinh", choices=["chim_bay", "theo_duong"], default=None)
    ap.add_argument("--nhac")
    ap.add_argument("--do_dam", type=float, default=0.72, help="độ đục lớp màu quy hoạch trên vệ tinh")
    ap.add_argument("--lap_lai", action="store_true")
    a = ap.parse_args()
    out = os.path.join(a.work, "du_an.json")
    if os.path.exists(out) and not a.lap_lai:
        print(f"● Đã có {out} — giữ nguyên (Claude sửa tay được). Lập lại: --lap_lai")
        return 0
    q = geo.load_json(os.path.join(a.work, "quy_hoach", "quy_hoach.json"))
    ti = geo.load_json(os.path.join(a.work, "tien_ich.json"))["diem"]
    ten = a.ten or ten_tu_tieu_de(q["tieu_de"])
    tl = re.search(r"1\s*/\s*(\d{3,5})", q["tieu_de"] or "")
    ha = f"{q['dien_tich_ranh_ha']:,.0f}".replace(",", ".")
    the_phu = a.the_phu or (f"Quy hoạch 1/{tl.group(1)} · ~{ha} ha" if tl else f"Khu quy hoạch · ~{ha} ha")
    cach = a.cach_tinh or ("chim_bay" if a.duong == "thang" else "theo_duong")

    tuyen, nhom = {}, {}
    pts = [x for x in ti if x.get("latlon")]                 # GIỮ thứ tự user đưa (chương theo thứ tự đó)
    for i, it in enumerate(pts):
        key = f"ti{i + 1}"
        lines = nhan_of(it)
        short = it.get("ten_ngan") or KS.short_name(" ".join(lines)).upper()
        mau = it.get("mau") or MAU[i % len(MAU)]
        ten_tuyen = it.get("chu_giai") or ("Tới " + KS.tach_ten(it["ten"])[0])
        if it.get("loai") == "duong":                        # tô cả tuyến đường (QL21B…) + ghim chỗ gần / cắt ranh
            diem = dict(ten=lines if len(lines) > 1 else lines[0], ten_ngan=short, loai="diem", latlon=it["latlon"], uu_tien=2)
            if it.get("trong_ranh") or it.get("cach_ranh_km", 1) < 0.05:
                diem["phu"] = "chạy qua khu quy hoạch"
            tuyen[key] = dict(ten=it.get("chu_giai") or KS.tach_ten(it["ten"])[0], loai="duong", mau=mau, phat_sang=True,
                              nguon={"osm": it["osm"], "loai": "highway", "ban_kinh_km": it.get("ban_kinh_km", 12)},
                              huong=it.get("huong", "both"), ban_kinh_km=it.get("ban_kinh_km", 14), nhan=lines[0] if it.get("nhan_tuyen", False) else None, diem=[diem])
        else:
            if it.get("trong_ranh"):
                print(f"  ⚠ {it['ten']} nằm TRONG khu quy hoạch — ghim không có line, nhãn «nằm trong khu quy hoạch»")
            diem = dict(ten=lines if len(lines) > 1 else lines[0], ten_ngan=short, loai=it.get("loai", "diem"), latlon=it["latlon"],
                        cach_tinh="theo_tuyen" if cach == "theo_duong" else "chim_bay", uu_tien=2)
            if it.get("trong_ranh"):
                diem["phu"] = "nằm trong khu quy hoạch"
            zone = it.get("vung") if isinstance(it.get("vung"), list) else None   # cụm / quần thể → khoanh vùng
            an_net = False
            if zone and it.get("giap_ranh"):                 # vùng GIÁP khu quy hoạch: khoanh vùng, không line, không km
                diem["phu"] = "giáp khu quy hoạch"
                nguon, an_net = {"latlon": [it["diem_ranh_gan"], it["latlon"]]}, True
                ten_tuyen = it.get("chu_giai") if it.get("chu_giai") and not it["chu_giai"].startswith("Tới ") else                     KS.tach_ten(it["ten"])[0] + " (giáp khu quy hoạch)"
            elif a.duong == "thuc":
                nguon = {"duong_di": {"den": it["latlon"], "hang": "tertiary", "tu_ranh": True, "qua": it.get("qua", []),
                                      "dang_xay": not a.chi_van_hanh, "pha": it.get("pha", True)}}
                if zone:                                     # line dừng ở MÉP vùng, km tính tới mép vùng
                    nguon["duong_di"]["den_vung"] = zone
            else:
                nguon = {"latlon": [it["diem_ranh_gan"], it["latlon"]]}
            tuyen[key] = dict(ten=ten_tuyen, loai="sanbay" if it.get("loai") == "sanbay" else "duong",
                              mau=mau, tu_vung=True, phat_sang=True, nguon=nguon, huong="cuoi",
                              nhan_tu_dong=a.duong == "thuc" and not an_net, diem=[diem])
            if zone:
                tuyen[key].update(vung_dich=zone, an_net=an_net)
        g = it.get("nhom") or ("Kết nối giao thông" if it.get("loai") in GIAO_THONG + ("duong",) else "Tiện ích xung quanh")
        nhom.setdefault(g, []).append(key)
    chuong = []
    for g, keys in nhom.items():
        for j in range(0, len(keys), 3):                     # ≤ 3 điểm có nhãn / chương (bẫy skill gốc: 6 điểm là quá tải)
            chuong.append(dict(ten=g, tuyen=keys[j:j + 3]))
    B = dict(ten=ten, vi_tri=q["tam"], the_phu=the_phu, logo=None,
             vung=q["ranh"],
             phoi_canh=dict(anh=os.path.join("quy_hoach", q["anh"]), bounds=q["bounds"], giu=True, do_dam=a.do_dam, vien=False),
             tieu_de=["KẾT NỐI QUANH", ten.upper()], tieu_de_phu=("khoảng cách theo đường đi thật" if a.duong == "thuc" else "khu quy hoạch · khoảng cách chim bay"),
             duong_sang=True, khung_sat=True, nhac=a.nhac, watermark=None, khung_ket=None,
             chuong=chuong, tuyen=tuyen,
             _nguon=dict(my_maps=q["nguon"], tieu_de_ban_do=q["tieu_de"], duong=a.duong, cach_tinh=cach,
                         qua_dang_xay=not a.chi_van_hanh))
    geo.save_json(out, B)
    print(f"● Ghi {out}: «{ten}» · {the_phu} · {len(tuyen)} điểm · {len(chuong)} chương · line {'thẳng (chim bay)' if a.duong == 'thang' else 'bám đường thật' + ('' if a.chi_van_hanh else ' (được qua đoạn đang xây theo quy hoạch)')}")
    for g, keys in nhom.items():
        print(f"  ▶ {g}: " + ", ".join(f"{tuyen[k]['diem'][0]['ten_ngan']}" for k in keys))
    print("  Claude SOÁT du_an.json (tên thẻ, chữ nhãn, chữ chương, bìa) rồi chạy run.py --work … (bước 1 xem trước)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
