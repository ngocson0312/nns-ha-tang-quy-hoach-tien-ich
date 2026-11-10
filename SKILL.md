---
name: nns-ha-tang-quy-hoach-tien-ich
description: Dựng video BẢN ĐỒ QUY HOẠCH + TIỆN ÍCH dọc 9:16 từ 2 đầu vào — (1) LINK GOOGLE MY MAPS bản đồ quy hoạch (viewer?mid=…; skill tự đọc hình học thật của mọi lô từ trang công khai, kể cả khi chủ bản đồ tắt tải KML) và (2) DANH SÁCH TIỆN ÍCH / điểm công cộng quanh khu (user đưa: tên + địa chỉ / link Google Maps / toạ độ / "giao điểm đường A × đường B"; hoặc skill tự khảo sát gợi ý, Claude chọn). Nhân bản từ nns-ban-do-ha-tang (giữ nguyên máy quay êm, chữ, SFX, tự kiểm 9 mục) và thêm: LỚP MÀU QUY HOẠCH từng lô (màu như My Maps) phủ lên ảnh vệ tinh Esri suốt video, RANH khu quy hoạch vàng phát sáng (hợp mọi lô), LINE SÁNG (quầng màu) BÁM ĐƯỜNG ĐI THẬT (OSM, qua cầu / phà thật, lối ra ranh ngắn nhất — KHÔNG chim bay) tới từng điểm + ghim + nhãn "cách <tên> ~7,9 km / ~850 m" theo QUÃNG ĐƯỜNG (dưới 1 km ghi mét), line ghi "QUA CẦU … / QUA PHÀ …", tuyến đường user nhắc (QL21B…) được tô cả tuyến, mỗi địa danh trong dòng user dán = 1 điểm, xã / cụm CN / khu là CỤM → KHOANH VÙNG theo ranh OSM (line dừng ở mép vùng, km tới mép vùng; giáp khu thì chỉ khoanh), mỗi điểm 1 chương zoom sát line của nó (khung_sat), chú giải. Điểm user đưa luôn được vẽ (kể cả hạ tầng đang xây — user là nguồn); toạ độ chỉ khớp tới thôn/xã thì ghi ĐOÁN và hỏi. KHÔNG giọng, chỉ SFX (+ nhạc nếu user đưa). Dừng 1 lần ở CỔNG DUYỆT. Trigger '/nns-ha-tang-quy-hoach-tien-ich', 'làm video quy hoạch từ link my maps này', 'bản đồ quy hoạch + tiện ích xung quanh', 'line từ dự án tới các điểm, ghi khoảng cách', 'video khoảng cách từ khu quy hoạch tới …'.
---

# nns-ha-tang-quy-hoach-tien-ich — khu quy hoạch + tiện ích xung quanh

**Đầu vào** (user 10/11/2026): (1) link Google My Maps bản đồ quy hoạch · (2) các tiện ích / điểm công cộng quanh đó — user đưa,
hoặc "bạn tự nhìn nhận và đưa vào" → `--tu_dong` khảo sát gợi ý, Claude chọn. Yêu cầu cứng: **line sáng từ khu quy hoạch tới
từng điểm, ghi rõ khoảng cách m hoặc km**.

```bash
# 0. đọc link My Maps → <work>/quy_hoach/ (ranh + lớp màu + ảnh soát); Claude MỞ quy_hoach/quy_hoach_xem.jpg ra nhìn
python -I -X utf8 .claude/skills/nns-ha-tang-quy-hoach-tien-ich/scripts/run.py --link "<link My Maps>" --work _htqh_<ten> --ten "<tên in thẻ>"
#    (lần đầu dừng: chưa có <work>/tien_ich_vao.json → Claude viết từ lời user, xem đầu scripts/tien_ich.py; chạy lại lệnh trên
#     → tìm toạ độ (tien_ich.json) + lập du_an.json nháp rồi DỪNG để Claude soát chữ chương / nhãn / chú giải)
# 1. kế hoạch + xem trước → CỔNG DUYỆT
python -I -X utf8 .claude/skills/nns-ha-tang-quy-hoach-tien-ich/scripts/run.py --work _htqh_<ten>
# 2. dựng + tự kiểm (không ghi đè video cũ: _ban2, _ban3…)
python -I -X utf8 .claude/skills/nns-ha-tang-quy-hoach-tien-ich/scripts/run.py --work _htqh_<ten> --render
```
Thêm `--tu_dong` ở lệnh 0 → `tien_ich_goi_y.json` (tiện ích nổi bật, trục lớn, cầu, metro, sân bay ĐANG VẬN HÀNH quanh ranh — bộ khảo
sát của skill gốc, đo từ MÉP RANH). Không tự đưa vào: Claude lọc (bỏ tên rác như "置屋街", điểm nằm trong ranh) rồi chép vào
`tien_ich_vao.json` kèm `latlon`, hỏi user ở cổng duyệt. Line mặc định `--duong thuc` (bám đường thật, qua cầu/phà, được đi cả
cầu/đường ĐANG XÂY theo quy hoạch nếu ngắn hơn — `--chi_van_hanh` để cấm); `--duong thang` (chim bay) CHỈ khi user yêu cầu.

### ĐÃ CHỐT (user 10/11/2026, sau bản 1 Vinhomes Olympic)
1. **"cứ cho đủ đi, dài video ra cũng được"** — user dán địa chỉ kiểu Google Maps ("Vành đai 4 điểm giao cắt với QL21B, Cụm Công
   Nghiệp Thanh Oai / Chi tiết từ Google Maps / Bình Minh, Hà Nội / Đến Sửa chữa xe máy / … / Tầm Tang, Mễ Sở, Hưng Yên") → MỌI
   địa danh là 1 điểm: điểm chính (nút giao, tiệm), ĐƯỜNG (QL21B → `loai: "duong"`, `osm: "21B"`: tô cả tuyến + ghim chỗ cắt ranh,
   "chạy qua khu quy hoạch"), cụm CN / KCN (OSM landuse=industrial), XÃ (relation admin, điểm giữa xã — `is_in` kiểm), THÔN.
   Chỉ bỏ cấp tỉnh / thành phố. Tiệm không có trên OSM → gộp với thôn của nó (1 ghim, nhãn "SỬA CHỮA XE MÁY / TẦM TANG", `doan: true`).
2. **"ai mà bay được, phải có đường đi chuẩn"** — KHÔNG line chim bay. Định tuyến trên mạng đường OSM: chặng đầu xuất phát từ MỌI
   nút đường trong ranh (lối ra ngắn nhất), qua cầu / phà thật (`route=ferry`, chi phí ×3), khoảng cách in = QUÃNG ĐƯỜNG từ mép ranh.
   Cầu dài nhất / phà trên đường → nhãn line "QUA CẦU … / QUA PHÀ …"; không có cầu/phà mà đi đường ĐANG XÂY → "QUA SONG HÀNH
   VÀNH ĐAI 4 / đang xây" (đoạn đang xây luôn ghi trên hình). User chọn **qua cầu Mễ Sở (đang xây) thay phà** → điểm đó `"pha": false`
   trong tien_ich_vao (Mễ Sở 3,5 km, Tầm Tang 5,0 km); mặc định vẫn cho đi cả đường/cầu đang xây theo quy hoạch.
3. **Mỗi điểm 1 chương** khi các line chung đoạn đường (3 line cùng chạy QL21B trong 1 chương → line sau che line trước), xếp chương
   theo lộ trình địa lý (bay ngắn nhất), không theo khoảng cách.
4. **"Nó là 1 cụm, quần thể thì nên khoanh vùng lại xong đi đến, nhìn nó đẹp"** (bản 4 → bản 5) — điểm là CỤM / QUẦN THỂ (xã,
   phường, cụm CN / KCN, khu đô thị) → `"vung": "relation/…" | "way/…"` (hoặc `true` = tự tìm theo tên) trong tien_ich_vao:
   KHOANH VÙNG theo ranh OSM (phủ màu tuyến + quầng + viền, hiện khi line chạm mép, đậm trong chương rồi nhạt bớt, giữ tới khung
   kết), line dừng đúng MÉP vùng, km = quãng đường tới mép vùng, ghim + nhãn ở giữa vùng, chương khung cả vùng. Vùng GIÁP ranh khu
   quy hoạch (xã Bình Minh chung ~1,5 km ranh) → chỉ khoanh vùng, KHÔNG line, nhãn "giáp khu quy hoạch". Điểm ĐƠN LẺ (tiệm, nút
   giao, cầu, ga) giữ ghim + line tới ghim như cũ.
5. **Qua sông bằng cầu đang xây**: trước khi chọn, tra báo tình trạng cầu (cầu Mễ Sở: chưa thông, dự kiến thông xe kỹ thuật 7/2027)
   + OSRM (đường chạy được hôm nay: phà Hồng Vân – Mễ Sở) và nói rõ cho user; cầu cạn vắt qua bãi không có lối xuống giữa cầu →
   line phải xuống chân cầu rồi quay lại (vòng là đường thật). User đã nghe đủ vẫn chọn **giữ cầu Mễ Sở** (10/11).

### Script mới (phần còn lại kế thừa nguyên skill gốc)
| Script | Làm gì |
|---|---|
| `mymaps.py` | link → `_pageData` của trang viewer (KML bị chặn 403 khi chủ tắt xuất) → mọi vùng/đường/điểm + bảng kiểu (màu tô, độ đục). Vẽ `quy_hoach.png` (RGBA, lưới Mercator đúng `bounds`, ≤ 4096 px, tô CHẴN-LẺ giữ lỗ), ranh = hợp mọi lô + đóng khe ≤ `--dong_ranh_m` 150 m (đường nội khu), giản lược ±15 m; tâm = điểm sâu nhất trong ĐẤT QUY HOẠCH thật (không rơi vào lỗ làng xóm giữa khu); thống kê loại đất |
| `tien_ich.py` | `tien_ich_vao.json` → toạ độ: `loai "duong"` + `osm` (tuyến OSM, ghim chỗ cắt / gần ranh) › `latlon` (+ `nguon`, `doan`) › `link` (!3d!4d › q= › @) › `giao` (giao điểm 2 tuyến OSM theo regex tên/ref, gồm cả đoạn đang xây, gần `dia_chi`) › Photon khớp NGUYÊN CỤM tên (giữ dấu) › thôn/xã trong địa chỉ (OSM place=*, ĐOÁN) › Photon địa chỉ (ĐOÁN). Ghi khoảng cách chim bay tới MÉP RANH + điểm ranh gần nhất. `vung` → ranh OSM của cụm/xã (`out geom`, nối way outer), ghim dời vào trong vùng nếu lệch, khoảng cách = mép vùng ↔ mép ranh, `giap_ranh` khi chạm |
| `lap_ho_so.py` | quy_hoach + tien_ich → `du_an.json`: `vung` = ranh, `phoi_canh` = lớp quy hoạch (`giu`, `do_dam` 0,72, `vien` false), mỗi điểm 1 tuyến `tu_vung` + `phat_sang` + nguồn `duong_di {den, tu_ranh, dang_xay, pha}` + `nhan_tu_dong` (cầu/phà), khoảng cách `theo_tuyen`; điểm có `vung` → `vung_dich` + `duong_di.den_vung` (định tuyến tới nút đường trong vùng gần nhất theo quãng đường, cắt ở giao điểm với mép vùng), giáp ranh → `an_net` (không line); loại `duong` → tuyến OSM tô 2 chiều (`ban_kinh_km` 14); chương theo `nhom` đúng thứ tự user / Claude xếp (≤ 3 điểm), `khung_sat`. Không ghi đè hồ sơ đã có (`--lap_lai`) |

### Khoá hồ sơ thêm so với skill gốc
`phoi_canh.giu` (lớp quy hoạch không tan khi máy lùi) · `phoi_canh.do_dam` · `phoi_canh.vien` (false: không viền theo ảnh, có
`vung` lo; đồng thời bỏ lớp phủ vàng trong ranh để màu loại đất không bị ám) · `duong_sang` / `tuyen.phat_sang` (quầng màu
`C.GLOW_LAYERS`) · `tuyen.tu_vung` (vẽ từ đầu nét = mép ranh; "theo tuyến" = độ dài nét) · `khung_sat` (chương toàn line từ ranh
khớp theo line + ghim, thẻ dự án được ra ngoài khung, u ≥ `C.TIGHT_MIN_U` 4,5 m/px) · nhãn `fmt_dist` (< 1 km ghi mét, làm tròn
10 m; trong ranh → "nằm trong khu quy hoạch").

### CỔNG DUYỆT — hỏi một lần (cộng các dialog của skill gốc bên dưới khi liên quan)
| # | Hỏi | Đề xuất |
|---|---|---|
| Q1 | Tên in thẻ / trong "cách <tên> ~…" (tiêu đề My Maps hay kèm tên người đăng, vd "Nga Tây …") + dòng phụ thẻ | tên dự án, "Quy hoạch 1/500 · ~X ha" |
| Q2 | Điểm ĐOÁN (chỉ khớp tới thôn/xã): xin link Google Maps đúng điểm, hoặc chấp nhận ghim mức thôn + chữ nhãn | ghim mức thôn, nhãn tên xã |
| Q3 | Qua sông / đoạn đang xây: đi phà / cầu đang chạy hay cầu đang xây theo quy hoạch (nêu cả 2 quãng đường + ngày dự kiến thông xe tra báo + cầu cạn có lối xuống không) | đường ngắn nhất thật (phà nếu không có cầu đang chạy) |
| Q3b | Điểm nào là CỤM / QUẦN THỂ (xã, cụm CN, khu đô thị) để khoanh vùng | mọi xã / phường / cụm / khu có ranh OSM |
| Q4 | Thêm điểm từ gợi ý tự khảo sát (nêu 3–6 điểm đáng giá nhất) | chỉ điểm user đưa |
| Q5 | Khung: zoom sát từng line (cú bay giữa 2 điểm xa nhau 5–7 s) hay nhìn toàn khu (nhanh, line nhỏ) | zoom sát |
| Q6 | Nhạc nền (file của user) / chỉ SFX · bìa 2 dòng | chỉ SFX · "KẾT NỐI QUANH / <TÊN>" |

### Bẫy đã gặp (riêng phần quy hoạch + tiện ích)
- **KML 403**: `/maps/d/kml?mid=…` bị chặn khi chủ bản đồ tắt xuất → đọc `var _pageData = "…"` của trang viewer (giải mã JSON 2 lần).
  Hình học thật ở `lớp[12][0][13][0]` (mỗi đối tượng `[id, điểm, đường, vùng, idx kiểu, thuộc tính…]`, điểm bọc `[[lat,lon]]`),
  bảng kiểu ở `lớp[12][0][13][1]`; `lớp[4]` chỉ là khung bao — đừng nhầm là dữ liệu.
- **Lô có lỗ** (làng xóm hiện hữu nằm giữa khu): tô KÍN từng vòng thì lỗ thành mảng xám giả → tô CHẴN-LẺ theo từng đối tượng.
  Tô 30 k lô trên ảnh 4096 px chậm → cắt mặt nạ theo khung bao từng lô (5–6 s). Bỏ đối tượng tên kiểu logo / iquyhoach / watermark.
- **Tâm khu rơi vào lỗ**: điểm sâu nhất trong ranh có thể là giữa làng → lấy trong ĐẤT LÔ THẬT, phạt nhẹ xa giữa khung.
- **Photon khớp nhầm** ("Mễ Sở" → tuyến đường sắt đô thị số 8 quy hoạch đi qua Mễ Sở): chỉ nhận khớp NGUYÊN CỤM tên có dấu, loại
  construction/proposed; không ra thì tìm thôn/xã trong địa chỉ bằng OSM `place=*` (ghi ĐOÁN, hỏi user xin link đúng điểm).
- **Tên tiệm/quán nhỏ** ("Sửa chữa xe máy") không có trên OSM (đã quét shop/craft sửa xe 2,5 km) → ghim ở thôn, nhãn tên tiệm + thôn, ĐOÁN.
- **Định tuyến qua sông**: khung tìm đường cũ = 2 điểm đầu-cuối ± 2 km → cắt mất cầu/phà → nới `C.ROUTE_BBOX_FRAC` 60 % quãng chim bay;
  điểm ranh gần đích nhất (chim bay) thường là bờ sông không có đường → `tu_ranh` (đa nguồn từ mọi nút trong ranh) rồi cắt phần trong ranh.
  Cầu đang xây (cầu Mễ Sở) có trong OSM nhưng chưa nối mạng đường ở 2 đầu → không đi được tới thôn bên kia nếu cấm phà.
- **Đường ĐANG XÂY chưa có nút giao trong OSM** (song hành VĐ4 cắt đường Chu Mạnh Trinh không chung nút) → line chạy quá 1,2 km rồi
  quay đầu (vòng gấp khúc) → nối ảo nút đường đang xây (không phải cầu) với nút đường đang chạy ≤ `C.XAY_NOI_M` 40 m. Cao tốc đang xây
  (CT.38) bị loại khỏi định tuyến (chưa biết chỗ lên/xuống), cầu/làn song hành cấp primary vẫn đi. Cầu cạn dài vắt qua bãi (cầu Mễ Sở
  qua Tầm Tang) → line hết cầu rồi quay về theo song hành là ĐÚNG (không xuống giữa cầu được).
- **Thôn trong bãi sông** chỉ nối làng bên bằng đường service/track → quanh mọi đầu mút + điểm qua (1,6 km) cho đi cả loại này
  (`C.ROAD_LOCAL_EXTRA`); vẫn đứt thì thêm `"qua": [[lat,lon]]` (làng bên kia cầu) cho điểm đó.
- **Line chồng nhau**: 3 điểm cùng hướng gom 1 chương → 3 line chung QL21B, line đỏ bị che gần hết → mỗi điểm 1 chương.
- **Tô đường OSM** (QL21B): chuỗi way gần dự án nhất có thể chỉ là 1 nửa (chuỗi bị tách) — đoạn còn lại đã hiện qua line các chương sau.
- **Giao điểm 2 tuyến** (VĐ4 × QL21B): VĐ4 đang xây vẫn tính (user là nguồn) — `giao` lấy cả đoạn construction, ngưỡng 60 m,
  chọn giao điểm gần `dia_chi` nhất.
- **Khu quy hoạch rộng (≥ 10.000 ha)**: chương ôm cả khu → line + ghim bé xíu → `khung_sat` (khớp theo line, đệm 600 m, thẻ dự án
  được ra ngoài); zoom sát quá thì cú bay giữa 2 điểm ở 2 đầu khu kéo 7 s → `TIGHT_MIN_U` 4,5 m/px (còn ~6,5 s). Vẫn dài → hỏi Q5.
- **Màu loại đất bị ám vàng**: lớp phủ vàng trong `vung` của skill gốc chồng lên lớp quy hoạch → tắt khi có `phoi_canh.vien=false`.
- Lỗi in `UnicodeEncodeError cp1252` → luôn chạy `python -I -X utf8`.
- **Overpass `out geom tags` với relation** trả về KHÔNG có members → ranh xã rỗng ("không lấy được vùng") → dùng `out geom;`.
- **Xã sau sáp nhập 2025** là relation `admin_level=6` (không phải 8) và rất rộng (Bình Minh ~3.000 ha, Mễ Sở ~1.770 ha) → ranh xã
  có thể GIÁP luôn khu quy hoạch: đo khoảng cách vùng↔ranh trước, giáp thì không vẽ line (ghi "giáp khu quy hoạch"), đừng in số km
  tới "điểm giữa xã" như bản 4 (4,7 km là sai nghĩa: xã nằm sát khu).
- **Ranh xã ven sông** chạy giữa / mép sông → line qua cầu dừng ngay chỗ chạm ranh xã (Mễ Sở ~850 m), không chạy tiếp vào làng.
- **Tự kiểm lần 1 chỉ ĐẠT 6/9 (Vinhomes Olympic 10/11)**, cả 3 lỗi đều do bộ kiểm / biên chứ không phải bản đồ sai:
  (a) máy quay: kế hoạch 13,95 px/khung sát ngưỡng 14, ORB đo p99 14,1 → kế hoạch nhắm `C.PLAN_MARGIN` 96 % ngưỡng;
  (b) toạ độ khung kết: lùi toàn cảnh 4,8 → 27 m/px dài 2,3 s nên `legend_t + 1` còn rơi vào lúc bay → đo ở `max(legend_t + 1, outro.t + 0,3)`;
  (c) chữ: thẻ dự án nằm ngoài khung suốt các chương `khung_sat` (đúng ý) và lướt qua mép lúc máy lùi → verify bỏ qua thẻ khi nằm
  hẳn ngoài khung, lướt mép lúc máy đang bay ghi vào "cắt ở mép (đã cho phép)"; thẻ cụt mép lúc máy ĐỨNG vẫn là lỗi.
- **Thẻ dự án lấp ló 9 px ở mép phải** lúc máy ĐỨNG (chương xã Bình Minh, bản 5 ĐẠT 8/9) → chương `khung_sat` gọi `card_clear`:
  đẩy tâm máy quay ít nhất (≤ 160 px) cho thẻ ra HẲN ngoài khung; thẻ nằm trọn trong vùng an toàn thì giữ nguyên.

---

# PHẦN KẾ THỪA TỪ nns-ban-do-ha-tang (luật, cấu hình, bẫy — giữ nguyên)

> Quy ước với chủ dự án: trả lời tiếng Việt có dấu; SỐT RUỘT — báo tiến độ ngắn, có ảnh xem trước là gửi.
> BẢN ĐỒ PHẢI CHUẨN: mọi tuyến/điểm có nguồn (OSM / ảnh quy hoạch / toạ độ hồ sơ / My Maps). Không có nguồn → hỏi, không vẽ.
> Sửa theo góp ý: plan → ok → sửa skill → ok → dựng lại.
> Gọi kiểu skill gốc (không có `--link`): `run.py --ten "<địa điểm>" --work …` vẫn chạy y như nns-ban-do-ha-tang.
> Luật "CHỈ HẠ TẦNG ĐÃ VẬN HÀNH" bên dưới áp cho phần TỰ KHẢO SÁT; điểm user đưa luôn được vẽ.

## LUẬT CỨNG — CHỈ HẠ TẦNG ĐÃ VẬN HÀNH [user chốt 17/10/2026]

"Chỉ ghi hoặc đưa cái gì lên khi đã đi vào hoạt động; cái gì đang làm hoặc đang test thì chưa đưa vào."
- Tuyến/ga/cầu/nút giao/sân bay đang xây, chạy thử, quy hoạch → **BỎ HẲN**. Không nét đứt, không chữ "dự kiến".
- Truy vấn OSM đã lọc sẵn: ray chỉ lấy `railway=rail|subway|light_rail|…` (bỏ `construction`/`proposed`), đường bỏ
  `highway=construction|proposed|…` (`common.RAIL_OPERATING`, `HIGHWAY_NOT_OPERATING`). Tuyến chạy một phần (metro 3 chỉ
  Nhổn – Cầu Giấy) tự còn đúng đoạn đã chạy — nhãn phụ ghi đúng đoạn đó.
- OSM có thể chậm cập nhật: hạng mục nào còn nghi → tra báo mới nhất trước khi đưa vào; hồ sơ ghi `"trang_thai": "dang_xay"`
  (hoặc `chay_thu`, `quy_hoach`) thì planner tự bỏ và in "BỎ … chưa vận hành".
- Mẫu KB5 The CityOn toàn hạ tầng tương lai — theo luật này phần lớn bị bỏ; muốn làm kiểu "hạ tầng tương lai" phải HỎI user.

## CẤU HÌNH MẶC ĐỊNH (đo từ mẫu + luật user đã chốt ở các video bản đồ khác — CHƯA có bản user duyệt toàn bộ)

Khi user duyệt một bản: đổi tiêu đề mục này thành "CẤU HÌNH ĐÃ CHỐT — KHÔNG HỎI LẠI" và ghi ngày.
Dòng có **[user chốt <ngày>]** là quyết định của user — không hỏi lại, không tự đổi.

| Lớp | Mặc định | Nguồn |
|---|---|---|
| Khung | 1080×1920, 30 fps, x264 crf 17, bt709 (`out_color_matrix=bt709`) | mẫu 720p → nâng |
| Nền | Esri World Imagery z8–z18, hoà 2 tầng khi chuyển, lọc Gauss khi thu nhỏ > 1,3×; tương phản ×1,04 | mẫu |
| Máy quay | van Wijk ρ 1,42 + ease sin; **lia ≤ 14 px/khung, zoom ≤ 7 %/khung, KHÔNG xoay**, bắc ở trên; cú bay tự kéo dài tới khi đạt ngưỡng | user chốt 17/10 (SongDay v3); mẫu zoom 8,7 %/khung là vượt |
| Bìa | 2 dòng chữ khối nghiêng Barlow Condensed Black Italic: dòng 1 gradient cam-vàng, dòng 2 xanh dương, viền tối; dòng phụ **Be Vietnam Pro Black trắng viền tối, thẳng (bỏ thư pháp — user 18/10)**; **giữ 1,25 s** + mờ 0,3 s | mẫu chỉ 3 khung (thumbnail) — user không thích tiêu đề "mất ngay" |
| Phối cảnh | ảnh RGBA đã cắt theo ranh lô (bounds lat/lon) hoà vào 0,55–0,95 s, viền vàng phát sáng; tan khi máy lùi ra | mẫu |
| Thẻ dự án | thẻ trắng bo góc (logo PNG nếu có, không thì tên 2 dòng Montserrat Black) + dòng phụ; khung rộng > 9 km tự thu thành chip; ghim đỏ viền đen-vàng | mẫu |
| Tuyến | lõi 9 px màu tuyến + viền trắng 2 px + bóng mềm; **vẽ 400 px/s (1,1–3 s/tuyến), vào nhanh rồi chậm dần (ease-out)**; tuyến sau bắt đầu khi tuyến trước vẽ 45 % **[user chốt 18/10: "xem cứ thấy hơi chậm"]** | mẫu ≈ 210–315 px/s — chậm so với ý user |
| Icon dẫn nét | huy hiệu tròn 72 px màu tuyến, viền trắng, glyph tàu / ô tô / máy bay (vẽ vector); bật back-out 0,32 s, nhún 5 px khi chạy; **gần mép khung thì mờ dần** (dải 110 px) | user chọn "icon phương tiện" thay linh vật (17/10); mẫu để linh vật kẹt nửa người ở mép |
| Ghim điểm | giọt nước màu tuyến, ruột trắng có glyph (ga / cầu / nút giao / sân bay) + chấm đen; bật lúc icon chạm điểm | mẫu |
| Nhãn điểm | Be Vietnam Pro Black IN HOA 50 px màu tuyến (đậm hơn) viền trắng 7 px + dòng "cách <dự án> ~X km" Bold 30 trắng viền tối; **đứng 3,5 s rồi thu về tên ngắn**; nhãn mới đè chỗ thì nhãn cũ nhường; tên ngắn chỉ đặt sát ghim, không có chỗ thì ẩn; **mọi nhãn TRỌN trong khung — không cắt ở mép** (máy quay chừa chỗ, xem dòng Spotlight) **[user chốt 17/10, kiểu A]** | mẫu để nguyên mọi nhãn → 29–40 s quá tải chữ |
| Nhãn tuyến | Black 40 px màu tuyến viền trắng ("TUYẾN 8", "KẾT NỐI VÀNH ĐAI R1"), dòng phụ 28 px; đặt lệch vuông góc khỏi nét, tránh xa ghim | mẫu |
| Chữ chương | **Be Vietnam Pro Black 80 px — chữ ĐẬM THẲNG, KHÔNG dùng thư pháp/chữ uốn lượn** (user 18/10: "bỏ mấy kiểu chữ uốn lượn, cho nhìn rõ chữ"; "&" của Great Vibes đọc thành "jj") · **VÀNG gradient (#FFEE8C → #FFBE1E) + viền nâu 4 px [user chốt 18/10]** + quầng tối mềm; vào 0,4 s / ra 0,3 s; tự đặt vào ô trống (8 ứng viên trên/dưới/giữa) | mẫu |
| Spotlight | chương có `"spotlight": true`: ngoài vòng còn 64 % độ sáng, vòng trắng 3 px bung back-out 0,9 s từ dự án, to dần theo nét đang vẽ; vòng km nét đứt ĐỨNG YÊN bậc 1/2/5/10/20/30/50 (≤ 4 vòng) + nhãn km; máy quay khớp nội dung đang hiện và **CHỪA CHỖ CHO NHÃN từng ghim** (`fit_with_labels`, ±170 px ngang / 150 px dọc) — mọi nhãn trọn trong khung, bản đồ nhìn xa hơn mẫu **[user chốt 17/10, kiểu A — `EDGE_FIT = False`]** | mẫu đo −36 %; nét đứt đứng yên = user chốt; user xem cả 2 bản A (trọn nhãn) / B (sát mép như mẫu, nhãn bị cắt) và chọn A |
| Kết | toàn cảnh mọi tuyến **chừa chỗ cho tên ngắn, không cắt nhãn ở mép [user chốt 17/10, kiểu A]** + tên ngắn + chú giải trắng 2 cột (thanh màu 44×12, Be Vietnam Pro SemiBold 34; màu quá sáng có viền xám) giữ 3 s; khung kết tuỳ chọn (`khung_ket`) | mẫu; mẫu ghi "xám" nhưng vẽ trắng — skill lấy đúng màu tuyến |
| Nhịp chương [user chốt 18/10] | chữ chương hiện 0,3 s sau khi máy bắt đầu bay (không đợi tới nơi); icon đầu bật ngay khi máy dừng (0,05 s), chờ 0,12 s rồi chạy; giữ sau nét cuối 0,5 s; nhãn cuối đứng ≥ 1,2 s; nhãn đầy đủ 2,6 s rồi thu gọn; bìa 0,9 s; chú giải hiện giữa cú lùi cuối, khung kết 2,2 s → video ~28–32 s (cũ 43–50 s, gần nửa thời gian là khe chờ) | đo 18/10: 7 khe > 2 s cộng 24 s ở bản cũ |
| Vùng an toàn | chữ trong x 48–1032, y 200–1590 (đáy ~330 px bị UI TikTok/Facebook che) | memory |
| Âm thanh | nhạc của user (ngắn hơn video → lặp NGUYÊN FILE, crossfade 80 ms, không có khe im) + SFX: pop (icon), ting (nhãn), quick-swoosh (chữ chương), whoosh (cú bay lớn), ting (spotlight), take-off (sân bay), new-item (chú giải); **đỉnh SFX = nhạc tại chỗ + 3 dB** (+ gain riêng); master tuyến tính −14 LUFS + alimiter 4× oversample, TP ≤ −1,5 | mẫu hở 0,4 s im ở mỗi mối nối nhạc; SFX mẫu dưới nhạc 7–15 dB = user chê "không thấy SFX" |
| Không tự tổng hợp nhạc | không có file nhạc → chỉ SFX (báo ở cổng duyệt) | user bỏ nhạc tự tạo 13/10 |

## Đầu vào: hồ sơ `du_an.json`

```jsonc
{
 "ten": "The CityOn",                       // tên dự án — in trên thẻ và trong "cách … km"
 "vi_tri": [20.95839, 105.98528],           // lat, lon của ghim dự án (BẮT BUỘC, toạ độ thật)
 "the_phu": "Ga số 11 · tuyến 8",           // dòng phụ trên thẻ (tuỳ chọn)
 "logo": "logo.png",                        // PNG nền trong (tuỳ chọn; không có thì in tên)
 "phoi_canh": {"anh": "phoi_canh.png",      // RGBA đã cắt theo ranh lô, hướng bắc lên (tuỳ chọn)
               "bounds": [[lat_bắc, lon_tây], [lat_nam, lon_đông]]},
 "tieu_de": ["HẠ TẦNG GIAO THÔNG", "QUANH THE CITYON"], "tieu_de_phu": "đường sắt · vành đai · sân bay",
 "nhac": "nhac.mp3",                        // file nhạc của user (tuỳ chọn)
 "watermark": null,                         // chữ thư pháp mờ cố định (tuỳ chọn; mẫu có "Tiến Hiệp")
 "khung_ket": {"dong1": "THE CITYON", "dong2": "Hotline 09xx"},   // tuỳ chọn
 "chuong": [ {"ten": "Phía Bắc · nội đô", "tuyen": ["metro8", "tuyen5"]},
             {"ten": "Đường bộ & cầu", "tuyen": ["vd35", "vd4"], "spotlight": true} ],
 "tuyen": {
   "metro8": {"ten": "Đường sắt tuyến 8",   // tên trong chú giải
              "nhan": "TUYẾN 8", "nhan_phu": null,   // nhãn trên nét (tuỳ chọn)
              "loai": "metro",              // metro → icon tàu · duong → ô tô · sanbay → máy bay
              "mau": "#2FC85E",
              "nguon": {"osm": "^Đường sắt đô thị số 8", "loai": "railway"},   // HOẶC
                       // {"trace": "georef/tuyen.json", "key": "metro8"}       // HOẶC {"latlon": [[lat,lon], …]}
              "huong": "auto",              // auto | dau | cuoi | both — vẽ về phía nào từ điểm gần dự án nhất
              "tu": null, "den": null,      // [lat,lon] tuỳ chọn: điểm bắt đầu vẽ / vẽ về phía điểm này
              "ve_km": null,                // độ dài vẽ cố định (km)
              "diem": [ {"ten": ["GA SỐ 10", "ECOPARK"], "ten_ngan": "GA 10", "loai": "ga",
                         "latlon": [20.9639, 105.9336],   // HOẶC "osm": "^Cầu Mễ Sở$" · "giao": "<khoá tuyến khác>" · "cuoi": true
                         "km": 5.6,                       // số hồ sơ (tuỳ chọn) — lệch > 15 % so số đo thì cảnh báo
                         "cach_tinh": "chim_bay",         // chim_bay (mặc định) | theo_tuyen
                         "an_khoang_cach": false, "an_o_ket": false} ] } } }
```

`loai` điểm: `ga`, `cau`, `nutgiao`, `sanbay`, `diem`. Đường dẫn tương đối tính từ thư mục chứa `du_an.json`.

### Lấy hình học tuyến — thứ tự ưu tiên
1. **OSM theo tên** (`"osm": regex`): skill nối các way (dung sai 250 m, cấm nối quay đầu), chọn chuỗi đi gần dự án nhất. Tuyến đang thi công/quy hoạch thường có trong OSM ("Đường sắt đô thị Số 5…", "Đường cao tốc vành đai 4 vùng thủ đô Hà Nội", "Đường kết nối Sân bay Gia Bình với Thủ đô Hà Nội"). Tra tên thật trước bằng một truy vấn Overpass trong bbox (in tên way + số khúc).
2. **Ảnh có vẽ tuyến** (ảnh quy hoạch, ảnh chụp màn hình bản đồ, khung video mẫu) → `trace_lines.py`:
   ```bash
   python .claude/skills/nns-ha-tang-quy-hoach-tien-ich/scripts/trace_lines.py --image anh.png --near LAT,LON --zooms 12,13 \
     --palette "metro8=#2FC85E,vd4=#CC75FF,gb=white" [--via "metro8=x1,y1;x2,y2;…|vd4=…"] --out georef/tuyen.json
   ```
   Tự khớp ảnh lên vệ tinh (SIFT + CLAHE, chọn zoom nhiều điểm khớp nhất; ảnh vẽ không phải vệ tinh → `--points` khớp tay ≥ 3 điểm),
   tách nét theo màu Lab ∩ lớp vẽ đè, bỏ mảng dày (icon, chữ, thẻ), dựng đồ thị xương + cầu nối khe bị nhãn che, lấy đường dài nhất.
   Tuyến bị nhãn cắt nhiều khúc / có 2 nét cùng màu → **cho `--via` (vài điểm px theo thứ tự đi)**. LUÔN MỞ `*_trace.jpg` RA NHÌN.
3. **Đường đi thật** (`"duong_di": {"den": [lat,lon], "qua": [[lat,lon],…], "hang": "tertiary|primary"}`): định tuyến trên đồ thị đường
   OSM đang vận hành (Dijkstra, ưu tiên trục lớn; trong 1,6 km quanh 2 đầu được đi cả đường nhỏ tới tận cổng). Dùng cho "từ dự án
   tới SVĐ / TTTM / cầu / sân bay". **Nối khúc theo tên làm nét cụt** khi OSM chia đường thành nhiều khúc rời (Lê Quang Đạo cụt cách
   SVĐ 800 m — user chỉ ra). Đích nên là điểm TRÊN đường (đầu đường sát cổng, đầu cầu bên kia sông, nhà ga T2), không phải tâm
   khu đất/đường băng — lệch bám > 400 m thì planner cảnh báo.
4. **Toạ độ tay** (`"latlon"`) từ hồ sơ / KMZ.
5. Không có nguồn nào → **hỏi user**, không vẽ.

## Quy trình khi được gọi

0. **Khảo sát tự động** (`khao_sat.py`, run.py tự gọi khi có `--ten` mà chưa có hồ sơ; ~1–3 phút, phần lớn là chờ Overpass):
   - **Tìm địa điểm**: Photon (photon.komoot.io — Nominatim bị chặn DNS trên máy này) khoanh Việt Nam, bỏ đường/nhà lẻ/cửa hàng;
     chấm điểm = khớp tên (so với MỌI cách gọi: tên user gõ + `ALIAS`) + loại đối tượng + thứ hạng Photon. Ứng viên tốt nhất chỉ là
     điểm lặt vặt → lấy làm MỐC, chọn công trình nổi bật nhất quanh 250 m (wikidata, chiều cao, diện tích). Tên in ra = chữ user gõ.
   - **Vùng**: đối tượng ≥ 1,5 ha (hồ, khu đất, quảng trường) → `vung` (ranh): viền vàng phát sáng, khoảng cách đo từ MÉP vùng,
     đường đi xuất phát từ điểm ranh gần đích nhất. Đối tượng là HỒ → chương "Ven hồ": icon chạy hết bờ, chùa/đền ven bờ bật dọc đường.
   - **Hạ tầng ĐANG VẬN HÀNH** (luật cứng ở trên): metro = ray `subway|light_rail|monorail` + ga trong 90 m quanh ray đó (ga của tuyến
     quy hoạch cũng gắn `railway=stop` — vd "Ga Lê Đức Thọ T5.07"); hai đầu tuyến = cặp ga xa nhau nhất trên TOÀN tuyến đang chạy.
     Trục lớn = vành đai/đại lộ/cao tốc/xa lộ/quốc lộ có đoạn LIỀN ≥ 2,5 km (OSM chỉ gắn tên "Vành đai 1" cho vài khúc → bỏ, kẻo nét
     cụt); thiếu thì lấy trục chính dài gần đó. Cầu lớn = `bridge` + tên "Cầu …" ≥ 450 m, ≤ 15 km, 2 cầu khác hẳn nhau. Sân bay có IATA
     ≤ 40 km, chấm ở nhà ga quốc tế. Tiện ích = có wikidata / TTTM / SVĐ / bệnh viện / đại học / bến xe / hồ ≥ 8 ha / công viên ≥ 5 ha;
     bỏ cơ quan, phòng khám, khách sạn, sông/kênh/rạch, thứ đang xây; hai điểm < 180 m giữ một.
   - **Xếp chương** (≤ 4 điểm có nhãn/chương): Ngay cửa nhà (dự án) | Ngay sát bên (địa danh) | Ven hồ (hồ) · Vành đai & trục lớn ·
     Metro đang chạy · Tiện ích quanh đây · Cầu & sân bay (spotlight). Chương rỗng tự bỏ. Đường đi tới tiện ích không vào chú giải.
   - Hồ sơ viết tay (dự án BĐS có tài liệu bán hàng, logo, phối cảnh) vẫn dùng được: `--brief du_an.json` như cũ.
   **Claude PHẢI soát `du_an.json`** trước cổng duyệt: tên trên nhãn/tên ngắn (tự rút gọn: SVĐ, TTTM, BV, ĐH, KDL, SB; bỏ đuôi
   "Hà Nội/TP.HCM"), điểm nào lạc đề thì xoá, user muốn thêm điểm nào thì thêm (tra toạ độ OSM).
1. **Bước 1 — kế hoạch + xem trước** (~30 s):
   ```bash
   python .claude/skills/nns-ha-tang-quy-hoach-tien-ich/scripts/run.py --brief <du_an.json> --work <thư mục>
   ```
   In BẢNG DUYỆT (chương, tuyến + nguồn, nhãn + khoảng cách chim bay/theo tuyến/hồ sơ, mốc giây, vòng km, ngưỡng máy quay,
   SFX, ⚠ cảnh báo), dựng `xem_truoc_*.jpg` rồi dừng (mã 2). **Claude MỞ ẢNH XEM TRƯỚC RA NHÌN**, sửa hồ sơ tới khi hết ⚠ quan trọng.
   Xem thêm khung bất kỳ: `render.py --plan <work>/plan.json --frames 6.5,24 --outdir <thư mục>` (~1 s/khung).
2. **CỔNG DUYỆT (1 lần)** — gửi bảng + ảnh xem trước, hỏi các dialog. User giục / bảo cứ làm → tự chọn theo đề xuất, nói rõ đã chọn gì.
3. **Bước 2 — dựng + tự kiểm** (~3–4 phút / 32 s, 6 tiến trình): thêm `--render [--out <ra.mp4>]`.
   Ra MP4 + `verify.json`. `ĐẠT 9/9` mới giao; mục trượt → sửa gốc rồi dựng lại.
4. **Giao** file + 1 dòng mỗi lớp (số chương/tuyến/nhãn/SFX, nhạc, LUFS/TP, kết quả tự kiểm), nêu rõ số liệu nào lệch hồ sơ.
   Rồi **bồi nhật ký** cuối file này.

## CÁC DIALOG SKILL PHẢI HỎI (một lần, ở cổng duyệt — LẦN NÀO CŨNG HỎI, lựa chọn cũ chỉ là đề xuất)

| # | Hỏi | Đề xuất mặc định | Bắt buộc |
|---|---|---|---|
| 1 | Đúng địa điểm chưa (khảo sát in OSM đã chọn + các ứng viên khác) + tên in trên thẻ, có logo PNG không | ứng viên điểm cao nhất, tên user gõ | ✔ |
| 2 | Danh sách hạng mục theo chương — thêm/bớt điểm nào | theo khảo sát tự động (hoặc tài liệu bán hàng user gửi) | ✔ |
| 3 | Nguồn hình học từng tuyến (OSM / ảnh / toạ độ) — tuyến OSM không có thì xin ảnh quy hoạch | OSM nếu có | ✔ |
| 4 | Khoảng cách in ra: số hồ sơ hay số đo (chim bay) khi lệch > 15 % | số hồ sơ + báo lệch | ✔ khi lệch |
| 5 | Nhạc nền: file nào (KHÔNG tự tổng hợp) | file trong thư mục dự án | ✔ |
| 6 | Bìa: 2 dòng tiêu đề + dòng phụ | "HẠ TẦNG GIAO THÔNG / QUANH <TÊN>" | |
| 7 | Ảnh phối cảnh cắt theo ranh lô có không | có thì dùng | |
| 8 | Khung kết (tên + hotline) / watermark | không | |

## Tự kiểm (`verify.py`, trên file cuối)
1 định dạng (đếm khung thật) · 2 −14 ±1 LUFS, TP ≤ −1 · 3 không khe im ≥ 0,1 s · 4 từng SFX khớp mẫu sóng trong âm thanh cuối đã trừ nhạc,
lệch ≤ 1 khung · 5 đỉnh SFX ≥ nhạc + 1 dB · 6 máy quay ORB+RANSAC từng cặp khung (p99 trong ngưỡng, tối đa ≤ +15 %) · 7 SIFT khung cuối ↔ Esri
ở mỗi chương, lệch ≤ 3 px · 8 nhãn trong vùng an toàn, chồng nhau ≤ 6 % (chỉ khi `EDGE_FIT = True` thì nhãn ghim sát mép mới được cắt ngang — liệt kê ở `cat_o_mep_da_cho_phep`; kiểu A đã chốt thì mọi nhãn ra ngoài đều tính trượt) · 9 đủ tile.

## Bẫy đã gặp

- **Overpass**: `overpass-api.de` hay báo 502 "at capacity", kumi/private.coffee trả 500 → `geo.overpass` luân phiên 4 mirror; `maps.mail.ru` chạy được (17/10/2026). POST bằng requests (chữ có dấu qua curl Git Bash hỏng âm thầm). Truy vấn điểm dùng `out center` (cầu là way nhiều khúc, `out geom` của 0,7° quanh Hà Nội làm mirror 500).
- **Đường đôi trong OSM** (2 làn ngược chiều) bị nối thành chữ U nếu chỉ xét đầu mút gần → cấm nối quay đầu (`geo._uturn`). Tuyến đang thi công rời khúc 100–250 m → dung sai 250 m. Có nhiều chuỗi → chọn chuỗi **gần dự án nhất**, không phải dài nhất (vành đai 4 dài nhất đi cách dự án 11,8 km, chuỗi đúng 2,6 km). Cầu là way riêng → thêm tên cầu vào regex tuyến (`^(…vành đai 4…|Cầu Mễ Sở)$`) kẻo thủng nét ở cầu.
- **"Theo tuyến" phình 10–45 %** khi tuyến lấy từ ảnh (nét gợn) → mặc định khoảng cách CHIM BAY. Mẫu KB5 ghi Ga 10 ~5,6 km (đo chim bay 5,2), Ga 9 ~10,1 (9,8), Cầu Ngọc Hồi ~11,0 (đo 14,3 — lệch 30 %, có thể mẫu đo theo đường hoặc tới đầu cầu).
- **Tách tuyến từ ảnh**: nối khúc kiểu tham lam nổ O(n³) và nối lung tung → dùng đồ thị xương + Dijkstra; loại đốm trắng gọn-đặc (ruột ghim, chữ) nhưng GIỮ viền trắng dài của chính nét; mảng dày (linh vật, thẻ) loại theo distance transform > 2,2× nửa bề dày trung vị.
- `cv2.warpAffine` với ma trận đích→nguồn phải kèm `WARP_INVERSE_MAP` — quên thì ảnh phối cảnh co lại còn một vòng tí hon.
- **Nhãn đặt theo khung cuối chương là SAI** khi máy quay còn trôi (spotlight): nhãn đúng ở cuối nhưng chồng nhau lúc hiện → đặt từng nhãn theo camera **tại lúc nó hiện**, và cho nhãn cũ nhường/thu gọn.
- **Thẻ dự án hai bản chồng** khi một khung đứng yên rơi đúng ngưỡng đổi thẻ to/nhỏ → `plan.py` dời ngưỡng khỏi mọi khung đứng yên ±8 %, dải hoà hẹp.
- **Đo BPM tự tương quan sai 4 %** (130,8 vs 125,6) → không cắt vòng lặp theo BPM; lặp nguyên file.
- **True peak vượt +1,7 dB** khi limiter chạy ở 48 kHz (SFX pop/ting nhiều cao tần) → limiter ở 192 kHz. Rồi **AAC đẩy đỉnh thêm ~1,4 dB** (WAV −1,8 → MP4 −0,4 dBTP) → trần limiter thấp hơn TP `AAC_HEADROOM` = 1,3 dB; luôn đo TP trên file MP4 cuối.
- **Whoosh dâng chậm**: `whoosh.wav` đỉnh ở 2,55 s sau onset — canh onset thì tiếng to nhất đến khi máy quay đã dừng. Loại trong `SFX_PEAK` canh ĐỈNH vào mốc hình (giữa cú bay). Đo "nghe rõ" phải tìm đỉnh trong 3 s, không phải 0,4 s đầu (đo 0,4 s báo trượt oan −3 dB).
- **Ghim sát mép khung**: nhãn hết chỗ phía trên → bị đẩy sang trái, đứng ngay trên ghim KHÁC (đọc nhầm "Sân bay Gia Bình" thành nút giao). Sửa ở MÁY QUAY: `fit_with_labels` khớp khung chừa ±170 px ngang / 150 px dọc cho nhãn từng ghim; thêm luật nhãn phải gần ghim của nó hơn mọi ghim khác (+120 điểm phạt).
- **Nhãn ngắn đặt xa ghim** thì không biết của ghim nào → chỉ 6 vị trí sát ghim; không vừa thì ẩn tên (ghim vẫn còn).
- Tự kiểm toạ độ: khung spotlight tối + zoom gần có thể chỉ còn 22–24 điểm khớp SIFT mà lệch vẫn chỉ 0,5 px → ngưỡng tối thiểu 15 điểm, phán theo độ lệch (≤ 3 px), đừng phán theo số điểm khớp (ngưỡng 25 từng báo trượt oan).
- Tuyến không có điểm nào (tuyến 5, R1) phải giới hạn `ve_km` hoặc `den`, không thì vẽ hết bán kính, khung chương bị kéo rộng và chữ nhỏ đi.
- **Điểm mốc nằm xa đường** (sân vận động, sân bay, bến xe, TTTM): có `latlon`/`osm` mà cách tuyến > 300 m (`POI_OFF_ROUTE_M`) → ghim + km theo VỊ TRÍ THẬT; mốc giờ vẫn theo chỗ icon chạy qua gần nhất. Kéo ghim vào đường làm sai km (SVĐ Mỹ Đình 0,8 thay vì 1,6 km).
- **Nhãn bị đẩy xa ghim** (ghim chật, sát nhau): có đường dẫn trắng mảnh từ đầu ghim tới mép nhãn khi xa > `LEADER_MIN` px. Ghim DỰ ÁN cũng tính trong luật "gần ghim mình nhất"; phạt nhầm ghim = `WRONG_PIN_PENALTY` 400 (120 thua phạt chồng nét).
- **Mọi chương** (không chỉ spotlight) khớp khung bằng `fit_with_labels` — ghim cách mép < 200 px thì nhãn bị đẩy sang đứng cạnh ghim khác.
- **Đặt nhãn theo THỜI GIAN**: ghim sắp mọc trong lúc nhãn còn đứng cũng là vật cản; nhãn mới né nhãn đầy đủ đang đứng trước, chỉ bắt nhãn cũ nhường khi hết chỗ (không thì nhãn cũ chỉ sống 0,7 s); nhãn ngắn né mọi nhãn đầy đủ còn đứng trong khoảng hiện của nó; chương spotlight đặt theo khung lúc nhãn sắp thu gọn (máy còn lùi ra).
- **Một chương ≤ 3–4 điểm có nhãn**: 6 điểm/chương (VĐ3 + metro 3 + 2A) là quá tải → tách chương. Hai tuyến chạy chồng nhau (Metro 5 dọc Đại lộ Thăng Long) → gộp 1 nét, ghi chú ở nhãn phụ.
- Thẻ dự án: chỉ "The" nhỏ phía trên ("The / Matrix One"), không cắt chữ cuối ra dòng to; thu thành chip khi khung rộng > `CARD_MINI_KM` 4 km (9 km để thẻ to che ga sát nhà). Chú giải tên dài tự co cho vừa khung.
- `run.py` xoá khung xem trước CŨ (do chính nó sinh) mỗi lần chạy — không thì tấm ghép trộn khung cũ/mới.
- **Không có nhạc (chỉ SFX)**: đừng lấy mức nhạc (= 0) làm chuẩn đặt SFX — SFX thành −100 dB rồi master +56 dB. Nền giả `SFX_NO_MUSIC_REF` −22 dB; KHÔNG chuẩn −14 LUFS tích phân (đa phần là lặng) mà đẩy theo độ to TỨC THỜI lớn nhất ≈ −12 LUFS-M; tự kiểm bỏ qua mục "khe im". Đo LUFS-M bằng `ebur128=metadata=1,ametadata=print:key=lavfi.r128.M` (đừng lọc dòng log theo chữ "TARGET" — dòng nào cũng có).
- Chữ chương dài ("Vành đai 3 · Phạm Hùng") tự co cho vừa vùng an toàn.
- **Soát từng khung** (user 17/10: "làm chi tiết vào, để ý từng cái nhỏ nhất"): trước khi giao, dựng khung mỗi 1,2 s + mỗi 0,25 s ở các
  đoạn chuyển (nhãn nhường nhau, icon bật, đổi chương) và NHÌN hết. Lần Matrix One soi ra 15 lỗi mà tự kiểm chưa bắt — đã thêm vào
  tự kiểm: ghim chồng ghim, thẻ dự án vào bộ hộp chữ (chữ đè thẻ / thẻ cụt mép), nhãn tính cả lúc đang mờ dần.
- **Đường dẫn nhãn→ghim (vạch trắng) đã BỎ** — user hỏi "mấy cái này là gì". Nhãn đầy đủ chỉ đặt ở 8 vị trí KỀ ghim; chật thì nhỏ còn
  0,82; nhãn cũ nhường thì nhãn mới CHỜ nhãn cũ mờ hết rồi mới hiện (`t_label`), nhãn ngắn hiện sau khi nhãn đầy đủ tắt hẳn.
- **Thẻ dự án** chọn 1 phía cố định (trên/phải/trái/dưới) ít đè nét tuyến nhất; khung mỗi chương chừa trọn thẻ (AEON: thẻ cụt mép phải).
  Thẻ vẽ SAU icon phương tiện → icon bật ra từ sau thẻ, không đè chữ tên dự án.
- **Nhãn tuyến** phải gần nét của mình hơn mọi nét khác ("LÊ QUANG ĐẠO" từng nằm trên Đại lộ Thăng Long).
- **Tuyến vẽ 2 chiều**: icon chiều 2 chờ icon 1 chạy ra ≥ 2,6 bán kính icon (tính cả 0,25 s đứng chờ) — trễ cố định 0,3 s vẫn chồng.
- **Ghim chồng nhau** (2 điểm < ~100 m, vd Bảo tàng HN – TT Hội nghị): giữ 1 điểm. Ghim chương trước chồng ghim chương mới → mờ đi
  trong chương đó (gộp khoảng ẩn liền nhau, nối tới hết nếu khung kết cũng ẩn — không nhấp nháy). Khung kết ẩn ghim kém ưu tiên
  nằm gần ghim khác < 46 px; tên ngắn ở khung kết không được chạm thẻ dự án.
- **Vòng km**: bỏ vòng bán kính màn hình < 130 px; nhãn km chọn trong 10 góc chỗ ít đè nhất, vẽ trên nét tuyến.
- **Chữ chương** coi ghim đang hiện là vật cản (từng đè ghim SVĐ) — có thêm 3 vị trí hàng 2 phía trên.
- **Font thiếu glyph**: "→" trong Be Vietnam Pro hiện ô trống ở chú giải → `sprites.safe_text` tự thay "–" và cảnh báo.
- **Thẻ dự án là vật cản CỨNG** (`CARD_HARD` 12): chữ không bao giờ chạm thẻ; ở chương spotlight máy còn lùi nên nhãn được kiểm
  thẻ + vùng an toàn suốt thời gian nó hiện (12 mẫu, tới hết lúc mờ). Phía đặt thẻ chọn có tính cả khung mở đầu và giữa các cú bay
  (thẻ "Landmark 81 · Phường Thạnh Mỹ Tây…" dài tràn mép trái lúc mở đầu).
- **Không có chỗ hợp lệ sát ghim** (điểm > `FULL_FAIL_SCORE` 900) → KHÔNG hiện nhãn đầy đủ, chỉ tên ngắn sát ghim (hoặc chỉ ghim).
  Đặt đại thì nhãn đứng cạnh ghim KHÁC — "CẦU CHƯƠNG DƯƠNG" từng nằm giữa 2 ghim metro, cách ghim cầu 300 px (Hồ Tây 17/10).
- **Ghép tiếng KHÔNG dùng `-shortest`**: luồng AAC luôn ngắn hơn chút → cắt mất 4 khung cuối. Dùng `-af apad -t <thời lượng plan>`.
- **Whoosh của cú bay sớm** (nhịp nhanh: cú bay đầu lúc ~1,4 s, đỉnh whoosh ở 2,55 s sau onset) → cắt bớt ĐẦU tiếng (`skip` trong
  cues.json) để đỉnh vẫn rơi giữa cú bay. Tự kiểm so mẫu ở đoạn 0,15 s TO NHẤT của tiếng, không ở 0,15 s đầu (whoosh đầu gần câm → r ≈ 0).
- **Nhãn tuyến đè nhãn điểm / chạm ghim** (Matrix One 18/10: "VÀNH ĐAI 3" đè "TT HỘI NGHỊ", "Nhổn – Cầu Giấy" chạm đầu ghim SVĐ,
  tự kiểm chưa bắt vì không đo chữ↔ghim): nhãn tuyến đặt TRƯỚC nhãn điểm chỉ đoán chỗ bằng vùng chừa quanh ghim — vùng đó không phủ
  8 chỗ kề ghim (nhãn nằm DƯỚI ghim lọt ra ngoài). Nay có **lượt 2**: nhãn điểm chốt xong thì đặt LẠI nhãn tuyến né đúng hộp nhãn điểm
  (đầy đủ + tên ngắn); dò **cả 2 nhánh** vẽ; chạm ghim (±6 px) phạt `LABEL_ON_PIN_PENALTY` 2000 (phạt theo diện tích thì chạm mép
  ghim chỉ ~20 điểm). Vẫn chật (tuyến ngắn kẹp giữa cụm ghim, metro 3 vẽ 2,2 km) → tăng `ve_km` trong hồ sơ cho nét có khúc trống.
- **Thẻ dự án lố mép ở khung mở đầu** khi dòng phụ dài ("Số 1 Lê Quang Đạo · Nam Từ Liêm" 478 px > 466 px nửa khung): dự án đứng
  giữa khung nên thẻ trái/phải không vừa → máy quay mở đầu tự lệch tâm cho thẻ trọn vùng an toàn.
- **Khung "Ngay cửa nhà" nhìn quá xa** khi trục lớn không có điểm vẽ dài (Đại lộ Thăng Long `ve_km` 2,4 → 3 điểm sát nhà dồn vào
  một góc) → `ve_km` 1,4: máy đẩy gần, nhãn tách ra.
- **Tìm địa điểm khớp nhầm khi tên kèm thành phố** (bản zip thử 18/10): "Chợ Hàn Đà Nẵng" ra "Nhà thi đấu Đa Năng" ở Đồng Nai —
  so tên BỎ DẤU ("da nang" khớp "Đa Năng"), chỉ cộng điểm khi khớp NGUYÊN cụm (tên đúng "Chợ Hàn" không được điểm vì câu gõ dài
  hơn), hạng mục SVĐ +4 thắng. Sửa: `tach_ten()` + so tên giữ dấu theo tỷ lệ chữ + thưởng đúng tỉnh/thành; mốc là chợ thì ưu tiên
  công trình mang đúng tên mốc. Thử lại 9/9 câu gõ (Chợ Hàn ×2, Lăng Bác, Hồ Tây, Landmark 81, Matrix One kèm địa chỉ, Cầu Rồng,
  Nhà thờ Đức Bà, Vinhomes Ocean Park).
- **Khảo sát chọn điểm trùng** (Chợ Hàn 18/10): (1) cầu/sân bay đã có chương "Cầu & sân bay" vẫn được gắn làm tiện ích dọc trục
  lớn → `build_brief` giữ chỗ trước cho cầu + sân bay; (2) lọc "< 180 m giữ một" chạy TRƯỚC khi ghim công trình lớn dời về mép gần
  nhất → lọc lần 2 theo ghim cuối + bỏ điểm nằm TRÊN công trình đã chọn (< 80 m tới nét): "Dragon's Tail/Head" là mảnh của Cầu Rồng;
  (3) nhãn 2 dòng ngắt giữa từ ghép ("BẢO TÀNG MỸ / THUẬT") → `LABEL_HEADS` + `LABEL_PAIRS`; (4) khoảng cách sân bay ở bảng khảo sát
  đo tới tâm sân bay, ghim cắm ở nhà ga → đo tới nhà ga.
- **File không có giọng**: Whisper bịa câu "Hãy subscribe cho kênh…" — dấu hiệu chỉ có nhạc, không phải lời thật.
- Video mẫu TikTok: kiểm watermark/end card trước khi đo; mẫu KB5 không có end card.

## Skill này được bồi thêm sau mỗi lần chạy thật

| Ngày | Video | Học được |
|---|---|---|
| 17/10/2026 | Dựng lại The CityOn (thử nội bộ, nhạc = trung vị 3 vòng nhạc mẫu, KHÔNG đăng) → `_bandoht_cityon/work/The_CityOn_ban_do_ha_tang.mp4` 38,6 s | toàn bộ mục "Bẫy đã gặp"; khung mẫu dò ra dự án ở 20,95839 N 105,98528 E (SIFT 1821 điểm khớp z16); tuyến 8/5/R1/VĐ3.5 lấy từ khung 45,5 s của mẫu bằng trace_lines (`--via`), VĐ4 + đường Gia Bình lấy OSM (lệch so nét mẫu trung vị 20–35 m). Tự kiểm lần 1 ĐẠT 6/9 (TP, khe im ở nhạc thử, SFX nhỏ) → sửa gốc → **9/9**: −14,5 LUFS, TP −1,8, 21 SFX lệch 0 ms, lia p99 13,5 px/khung, zoom p99 3,8 %/khung, toạ độ lệch ≤ 0,12 px (≤ 4,5 m) ở 5 khung. Cùng 3 chương nhưng ngắn hơn mẫu (38,6 vs 46,7 s); cú bay đầu tự kéo dài 3,8 s cho đạt ngưỡng êm |
| 17/10/2026 (2) | Góp ý của user trên bản thử The CityOn | user chọn "zoom sát như mẫu, chấp nhận sân bay nằm ở mép, nhãn có thể bị cắt" → thêm `EDGE_FIT` / `EDGE_PAD` / `EDGE_CROP_ZONE` trong `common.py`; chương spotlight + khung kết khớp theo mép khung thật; nhãn ghim sát mép được tràn; verify mục 8 tách "cắt ở mép (đã cho phép)" |
| 17/10/2026 (3) | User so 2 bản A/B | **chốt kiểu A** ("giữ trọn nhãn, bản đồ nhìn xa hơn cũng được") → `EDGE_FIT = False`; kiểu B giữ lại trong mã làm tuỳ chọn nhưng KHÔNG dùng khi chưa được hỏi. Bài học: "giống mẫu" không phải lúc nào cũng thắng — user ưu tiên đọc được chữ hơn khung sát. Bản giao: `_bandoht_cityon/work/The_CityOn_ban_do_ha_tang.mp4` (= kiểu A, 9/9); kiểu B lưu `…_v2_sat_mep.mp4` |
| 17/10/2026 (4) | **The Matrix One** (MIK Group, Lê Quang Đạo – Mễ Trì) → `_bandoht_matrixone/work/The_Matrix_One_ban_do_ha_tang.mp4` — lần chạy thật đầu tiên trên dự án mới | toạ độ dự án lấy từ OSM (relation "The Matrix One" 21,009183 N 105,774146 E); mọi tuyến/ga/điểm từ OSM (metro 5 quy hoạch, 3, 2A; VĐ3; Lê Quang Đạo; VĐ3–Thăng Long ra Nội Bài; Võ Chí Công – Nhật Tân). User: chỉ SFX (không nhạc), SVĐ in "~1 km" theo quảng cáo (đo 1,6), không khung kết, thêm Keangnam/Bảo tàng HN/AEON Hà Đông/cầu Nhật Tân. 4 chương: Ngay cửa nhà · Vành đai 3 · Metro đang chạy · Cầu & sân bay. Các luật đặt nhãn theo thời gian + đường dẫn ở mục Bẫy sinh ra từ lần này |
| 17/10/2026 (5) | The Matrix One — góp ý của user sau bản 1 | (1) "metro 5 có chưa" → luật CHỈ HẠ TẦNG ĐÃ VẬN HÀNH (bỏ metro 5 đang xây; lọc OSM theo trạng thái); (2) "đoạn đỏ từ SVĐ tới toà nhà thiếu" → nguồn `duong_di` định tuyến thật; (3) "mấy cái này là gì" → bỏ vạch dẫn nhãn; (4) "làm chi tiết, để ý từng cái nhỏ nhất" → soát 35 + 12 khung, sửa 15 lỗi nhỏ (xem Bẫy). Bản 1 lưu `The_Matrix_One_v1_co_metro5.mp4` |
| 17/10/2026 (6) | **Gọi bằng tên địa điểm bất kỳ** — user: "đóng lại vào skill, sau này đưa Lăng Bác, Hồ Tây, Landmark 81… là ra video kiểu kia" | thêm `khao_sat.py` + `run.py --ten`; chạy thử Lăng Bác (Hà Nội), Hồ Tây (vùng 530 ha, chương Ven hồ), Landmark 81 (TP.HCM — OSM tên "Vincom Center", metro 1, cầu Sài Gòn 2, Tân Sơn Nhất). Bẫy: Photon lọc chặt mất Landmark 81 → tìm thả lỏng lấy mốc; `out tags` không trả toạ độ node, `out center bb` chỉ giữ bb → hàm `cen()`; ga của tuyến quy hoạch gắn railway=stop → lọc ga theo khoảng cách tới ray đang chạy; đầu tuyến phải lấy trên toàn tuyến (2A từng ra "La Thành – Cát Linh"); khung bao đường dài (Phố đường tàu) thổi điểm diện tích → chỉ cộng cho đối tượng dạng vùng; rút gọn tên bỏ theo CẶP từ cuối ("HOÀNG THÀNH", không "HOÀNG THÀNH THĂNG"); hồ thì giữ điểm ven bờ/trên đảo (Chùa Trấn Quốc) với dòng phụ "ngay bên hồ" |
| 18/10/2026 | User: "xem video cứ thấy hơi chậm" | đo nhịp: bản cũ 1 sự kiện/1,3 s (dày hơn mẫu 1,7 s) nhưng 7 khe > 2 s cộng 24 s ≈ nửa video, toàn ở chuyển chương (chờ sau nét cuối 1,4–1,8 s + bay 1,2–2 s + chữ chương lúc tới nơi) và nét vẽ chậm 250 px/s ease sin. Sửa: bảng "Nhịp chương" + dòng "Tuyến" ở trên; giữ nguyên ngưỡng máy quay êm. Kết quả: Matrix One 43 → 28 s, Lăng Bác 50 → 32 s, Hồ Tây 45 → 28 s, Landmark 81 49 → 29 s; khe còn lại đều nằm trong lúc máy bay/nét đang vẽ |
| 18/10/2026 (2) | User: "mấy chữ title này màu vàng nhé, sửa trong skill, không cần render lại" | chữ chương đổi trắng → vàng gradient + viền nâu (`common.CHAPTER_TOP/BOT/EDGE`); video cũ giữ nguyên |
| 18/10/2026 (3) | User: "bỏ mấy kiểu chữ uốn lượn này đi, cho nhìn rõ chữ… chữ giữa đó không biết là chữ gì" | mọi chữ thư pháp (Great Vibes) → Be Vietnam Pro Black (`common.F_TITLE`): chữ chương 80 px vàng viền nâu 4 px, dòng phụ bìa trắng viền tối. KHÔNG dùng lại font uốn lượn cho chữ cần đọc |
| 18/10/2026 (4) | **The Matrix One gọi bằng tên + địa chỉ** ("Số 1 Lê Quang Đạo, ngã tư Lê Quang Đạo – Mễ Trì") → `_bandoht_matrixone_ten/The_Matrix_One_ban_do_ha_tang.mp4` 27,3 s, nhịp + chữ mới 18/10 | khảo sát tên tìm đúng relation OSM, nhưng bộ điểm tự động lệch bộ user đã chốt (thiếu AEON, cầu Nhật Tân; thừa cầu Chương Dương, Bảo tàng Hậu Cần) → ghép: bộ đã chốt + điểm mới đáng giá của khảo sát (Cung Hữu nghị Việt – Trung 0,5 km, tra báo: khánh thành 11/2017). Dự án đã có hồ sơ cũ thì chép cache `osm/` sang + dùng đúng `vi_tri` cũ → truy vấn trùng khoá, khỏi chờ Overpass (khảo sát thô mất > 10 phút vì mirror chậm). User chọn hết theo đề xuất (dòng phụ thẻ theo địa chỉ user gõ, SVĐ ~1,0 km, chỉ SFX). Tự kiểm lần 1 ĐẠT 8/9 (thẻ lố mép lúc mở đầu) → sửa gốc → 9/9; soát 91 khung file cuối bắt thêm 2 lỗi nhãn tuyến mà tự kiểm không thấy → lượt 2 đặt nhãn tuyến (xem Bẫy) → 9/9: TP −2,7, 34 SFX lệch 0 ms, lia p99 8,8 px/khung, zoom p99 4,9 %, toạ độ lệch ≤ 0,2 px |
| 18/10/2026 (5) | **Đóng zip gửi người khác** (user: "ngta tải về giải nén là chạy được, điền địa điểm nào vào gọi skill ra là chạy ngon") → `Output/chia_se_skill/nns-ban-do-ha-tang.zip` (+ `nns-video-ban-do.zip`); đóng lại: `python tools/dong_goi_skill.py <skill…>` | thêm `CAI_DAT.bat` / `CAI_DAT.command` → `scripts/cai_dat.py` (chép vào `~/.claude/skills`, pip, hỏi cài ffmpeg, kiểm tra) + `scripts/kiem_tra_cai_dat.py` + `requirements.txt` + `HUONG_DAN_CAI_DAT.md`; cache về `~/.cache/nns_ban_do` khi cài cho mọi dự án (`NNS_TILE_CACHE` để tự chọn); font xem trước không còn trỏ C:/Windows. Thử trên venv SẠCH từ zip: Matrix One 9/9; gọi bằng tên "Chợ Hàn Đà Nẵng" lộ 4 lỗi khảo sát → sửa (xem Bẫy): khớp nhầm nhà thi đấu "Đa Năng" ở Đồng Nai, Cầu Sông Hàn hiện 2 lần, "Dragon's Tail/Head" (mảnh của Cầu Rồng) thành tiện ích, nhãn ngắt "MỸ / THUẬT"; sân bay tóm tắt đo tới tâm sân (4,0) thay vì nhà ga cắm ghim (2,7) |
| 10/11/2026 | **Tạo skill** từ nns-ban-do-ha-tang theo yêu cầu user: link My Maps quy hoạch + tiện ích → line sáng + khoảng cách m/km. Chạy thật: "Nga Tây Vinhomes Olympic – Bản đồ quy hoạch 1/500" (21 loại đất, ranh ~12.820 ha, tâm 20,8410 N 105,8329 E) + 2 điểm user đưa (nút giao VĐ4 × QL21B, Bình Minh – Thanh Oai: giao điểm OSM, cách mép ranh ~3,7 km; tiệm sửa xe ở Tầm Tang, Mễ Sở, Hưng Yên: ĐOÁN mức thôn, ~1,3 km) → `_htqh_vinhomes_olympic` | thêm `mymaps.py`, `tien_ich.py`, `lap_ho_so.py`, `fmt_dist`, quầng sáng tuyến, `tu_vung`, `khung_sat`, `phoi_canh.giu/do_dam/vien`; xem trước 20,3 s (lia ≤ 13,9 px/khung, zoom ≤ 4,2 %/khung) — mọi bẫy ở mục "Bẫy đã gặp (riêng phần quy hoạch + tiện ích)" |
| 10/11/2026 (2) | Góp ý user trên bản 1 Vinhomes Olympic: "thiếu nhiều địa điểm, cứ cho đủ đi" + "vẽ đường đi chuẩn, ai mà bay được" + "đổi qua cầu Mễ Sở" → `_ban3` (phà, 42,2 s, 9/9) rồi `_ban4` (qua cầu Mễ Sở) | 6 điểm / 6 chương (QL21B · xã Bình Minh · nút giao VĐ4 · CCN Thanh Oai · tiệm sửa xe Tầm Tang (ĐOÁN mức thôn) · Mễ Sở); định tuyến thật `tu_ranh` + phà + đường/cầu đang xây + nối ảo đường đang xây; loại `duong` tô quốc lộ; nhãn line tự ghi cầu/phà/đường đang xây; khoảng cách theo quãng đường. Bản tự kiểm 1 lần 6/9 → sửa gốc (biên máy quay, thời điểm soát toạ độ, thẻ dự án khi khung_sat) → 9/9 |
| 10/11/2026 (3) | Góp ý user trên bản 4: "đi vòng vèo, sao không qua cầu rẽ trái luôn" + "xã / cụm thì khoanh vùng lại xong đi đến, nhìn nó đẹp" + hỏi "đường đi chuẩn hiện nay" → `_ban5` (8/9: thẻ lấp ló mép) → sửa gốc → `_ban6` | tra báo: cầu Mễ Sở chưa thông xe (dự kiến thông xe kỹ thuật 7/2027); OSRM: đường đi được hôm nay = phà Hồng Vân – Mễ Sở rồi rẽ trái ~1,4 km vào Tầm Tang; OSM: cầu cạn vắt ngay trên Tầm Tang, chân cầu Hưng Yên hạ sau đê ĐT.378 ~250 m → đi cầu thì phải xuống chân cầu rồi quay lại (đường thật). User nghe xong chọn GIỮ CẦU. Thêm loại điểm VÙNG (`vung` → ranh OSM, `den_vung`, `vung_dich`, `an_net`, `zones` trong plan, render phủ màu + quầng + viền): xã Bình Minh (relation, ~3.000 ha) GIÁP ranh khu ~1,5 km → chỉ khoanh + "giáp khu quy hoạch" (bản 4 in sai nghĩa "~4,7 km" tới điểm giữa xã); CCN Thanh Oai (way, 54 ha) line tới mép ~6,5 km; xã Mễ Sở (relation, ~1.770 ha) line qua cầu tới mép xã ~850 m |
