# Phân tích video KB5 — "Hạ tầng giao thông quanh The CityOn"

Nguồn: `Downloads/ToDay/KB5/2aOboR62TnLLLSsJ9NprIdEceiG4JQZGs5DSSmW0.mp4`
Thông số: 720×1280, 30 khung/s, 46,7 s (1402 khung), H.264 ~2 Mb/s, AAC stereo 44,1 kHz.
Ảnh tóm tắt: `KB5_khung_chinh.jpg`. Dải khung 5 khung/s: `tl_0.jpg` … `tl_7.jpg`.

---

## 1. Loại video

Đây là video **bản đồ hạ tầng**: không người nói, không giọng đọc, không sub. Toàn bộ thông tin nằm trên bản đồ vệ tinh.
Thông điệp duy nhất: dự án nằm **giữa mạng giao thông**. Mỗi tuyến, ga, cầu, sân bay hiện ra đều kèm khoảng cách tới dự án.

## 2. Cấu trúc: một cú bay liền, 6 chặng

Video không có cú cắt nào. Mọi cặp khung liền nhau đều khớp trên 850 điểm ORB. Mốc "cắt cảnh" duy nhất máy dò ra (26,07 s) thực chất là lúc bản đồ tối lại.

| Chặng | Thời gian | Hình | Máy quay |
|---|---|---|---|
| Bìa | 0–0,1 s (3 khung) | Tiêu đề "HẠ TẦNG GIAO THÔNG / QUANH THE CITYON / đường sắt · vành đai · sân bay" đè trên ảnh phối cảnh | đứng |
| Mở | 0,1–2,0 s | Cắt về ảnh vệ tinh hiện trạng (đang là công trường). Thẻ logo hiện ở 0,3 s. Phối cảnh dự án hoà dần lên (0,5–0,85 s), có viền vàng phát sáng | đứng |
| Lùi ra | 2,0–6,5 s | Phối cảnh tan dần. Thẻ logo thu gọn thành chip | zoom ra ×4,3, trôi chậm, rồi zoom ra tiếp ×2,15 |
| **Phía Bắc · nội đô** | 5,2–15,0 s | **Linh vật xanh lá** vẽ Tuyến 8 sang trái, qua Ga số 10 Ecopark (~5,6 km) và Ga số 9 (~10,1 km). **Linh vật xanh dương** vẽ Tuyến 5 lên trên (hướng Long Biên) | đứng yên |
| **Phía Nam** | 15,0–23,4 s | Chữ chương cũ và nhãn tan đi, các đường vẫn giữ. **Linh vật đỏ** vẽ "Kết nối vành đai R1" xuống dưới | lia xuống-phải ~0,77 bề ngang khung, rồi đứng |
| **Đường bộ & cầu** | 23,4–42,5 s | Bản đồ tối lại, vòng spotlight bung ra từ dự án. **Vàng** = Vành đai 3.5 (Cầu Ngọc Hồi ~11 km). **Tím ×2** = Vành đai 4 (Cầu Mễ Sở, Nút giao sân bay ~17,6 km). **Trắng** = đường tới SB Gia Bình. Vòng nét đứt 5/10/20/30 km | zoom vào ×2,75, rồi trôi ra ×1,14 trong 7 s |
| Tổng kết | 42,5–46,7 s | Tắt spotlight. Linh vật và dòng "cách …" tan đi, nhãn rút gọn (GA 9, GA 10). Bảng chú giải 6 màu bật lên, giữ ~3 s | đứng |

Nhịp hình: cứ khoảng 1–1,5 s lại có một phần tử mới xuất hiện.

## 3. Các lớp hình

### 3.1 Nền bản đồ
- Ảnh vệ tinh nhìn thẳng từ trên xuống, hướng Bắc lên trên. Không xoay (góc ≤ 0,1°), không nghiêng 3D.
- Khi zoom xa thấy vệt ghép ảnh lệch màu ở mép phải, do ảnh chụp nhiều đợt.
- Tỉ lệ khoảng cách tương đối khớp. Ở 12,0 s, khoảng cách trên hình từ dự án tới Ga 9 và Ga 10 là 418 px và 218 px, tỉ số 1,92. Hai con số in trên nhãn (10,1 km và 5,6 km) cho tỉ số 1,80, lệch 7%. **Chưa kiểm với toạ độ thật.**

### 3.2 Bìa: chỉ sống 3 khung
- "HẠ TẦNG GIAO THÔNG": gradient cam-vàng, viền nâu đỏ.
- "QUANH THE CITYON": gradient xanh dương, viền navy.
- Font khối đậm, hẹp, nghiêng, kiểu chữ game.
- Dòng phụ "đường sắt · vành đai · sân bay": viết tay trắng, nghiêng khoảng −8°.
- Bìa tắt sau 0,1 s nên nó chỉ dùng làm **thumbnail**; người xem lướt gần như không thấy.

### 3.3 Ghim dự án
- Chấm đỏ có viền đen-vàng, kèm thẻ trắng bo góc mang logo "the cityon" và dòng "Ga số 11 · tuyến 8".
- Khi lùi xa (4,6–5,8 s), thẻ thu gọn thành chip chỉ còn logo, bám theo ghim suốt video.

### 3.4 Linh vật: chữ ký của video
- Một nhân vật duy nhất (đầu tròn, mắt to, tai nghe, số "1" trên trán, giơ hai tay) được đổi 6 màu. **Mỗi màu ứng với một tuyến.**
- Mỗi con bật ra (phóng to nhanh) ngay tại ghim dự án, rồi **chạy dọc tuyến**. Nét đường vẽ ra phía sau đúng theo vị trí linh vật, như vệt chân.
- Tới ga hoặc cầu thì nhãn cùng màu bật ra.
- Vành đai 4 dùng 2 con tím chạy ngược hướng nhau cùng lúc.
- Thời gian vẽ một tuyến: vàng ~1 s; tím, trắng ~1,8 s; xanh lá ~2,8 s; xanh dương ~3,2 s; đỏ ~5 s.

### 3.5 Chữ
- **Tên ga, cầu**: sans tròn rất đậm, IN HOA, tô màu của tuyến, viền trắng và bóng tối. Dòng phụ "cách The Cityon ~X km" chữ nhỏ trắng.
- **Nhãn tuyến**: "TUYẾN 8", "TUYẾN 5 hướng Long Biên", "KẾT NỐI VÀNH ĐAI R1". Riêng nhãn R1 màu đỏ, viền đen dày như con tem.
- **Icon ghim**: tàu (ga), cầu, máy bay (sân bay).
- **Chữ chương** "Phía Bắc · nội đô", "Phía Nam", "Đường bộ & cầu":
  - thư pháp trắng có bóng mờ, hiện mờ dần trong 0,2–0,4 s;
  - đặt vào **vùng trống, ngược hướng tuyến đang vẽ**: Phía Bắc ở góc trên-trái, Phía Nam ở giữa-dưới, Đường bộ ở trên-giữa.
- **"Tiến Hiệp"**: thư pháp trắng mờ, ghim cố định ở 76% chiều cao màn hình suốt 46,7 s. Chữ không đi theo bản đồ nên là **watermark / chữ ký người đăng**, không phải địa danh.

### 3.6 Spotlight bán kính
- 26,0–26,2 s: cả khung tối lại. Một vòng tròn trắng mảnh mọc ra từ ghim.
- Bên trong vòng giữ nguyên độ sáng, bên ngoài tối đi 36% (độ sáng 144 → 92).
- Vòng to dần theo tuyến đang vẽ. Các vòng nét đứt hiện kèm nhãn: 5 km (29,2 s), 10 km (30,8 s), 20 km (34,0 s), 30 km (37,4 s).
- Tắt bằng hoà tan 40,8–41,2 s.

### 3.7 Chú giải
Thẻ trắng bo góc ở đầu khung, 2 cột, 6 dòng:

| Cột trái | Cột phải |
|---|---|
| Đường sắt tuyến 8 (xanh lá) | Vành đai 3.5 (vàng) |
| Đường sắt tuyến 5 (xanh dương) | Vành đai 4 (tím) |
| Kết nối R1 (đỏ) | Đường tới SB Gia Bình (xám) |

### 3.8 Máy quay (đo từng khung)

| Cú | Thời gian | Biên độ | Kiểu chuyển động |
|---|---|---|---|
| Zoom ra 1 | 2,0–2,7 s | ×4,3 | tăng rồi giảm tốc đối xứng; 80% quãng đường trong 0,5 s (2,10→2,60) |
| Zoom ra 2 | 4,6–6,4 s | ×2,15 | tăng tốc dần, dừng gắt |
| Lia | 15,0–17,2 s | xuống-phải ~0,77 khung | êm |
| Zoom vào | 23,4–25,5 s | ×2,75 | tăng rồi giảm tốc đối xứng |
| Trôi ra | 28–35 s | ×1,14 | đều, rất chậm |

Ngoài 5 cú trên, máy đứng yên hẳn để mắt người xem dồn vào linh vật.

Đối chiếu với ngưỡng "máy quay êm" đã chốt cho video bản đồ (lia ≤14 px/khung, zoom ≤7%/khung, xoay ≤0,6°/khung):

| Cú | Kết quả |
|---|---|
| Zoom ra 1 | đỉnh 8,7%/khung; 11 khung vượt 7% (quanh 2,3 s) |
| Lia xuống Phía Nam | ~16 px/khung đo tại tâm khung (quy về 1080 px), sát ngưỡng |
| Các cú còn lại | zoom ≤2,6%/khung; gần như không xoay |

Chỗ xoay 0,8° đo được ở 16,0 s là nhiễu bám điểm (chỉ 1 khung), không phải máy xoay.

## 4. Âm thanh

**Giọng nói:** không có. Whisper chỉ "bịa" ra câu "subscribe…", dấu hiệu quen thuộc của file chỉ có nhạc.

**Nhạc:**
- Một đoạn 15,28 s (8 ô nhịp ở ~125,6 BPM), **lặp đúng 3 lần** (tương quan 0,96).
- Gần như mono: kênh side thấp hơn kênh mid 24 dB.
- Giai điệu vui, sáng: tiếng chuông quanh 1 kHz trên nền trống bass dày.
- Độ to −11,5 LUFS, LRA 0,9 LU, tức nén rất dẹt và to.

**SFX:** tách bằng cách lấy 3 vòng nhạc trừ lẫn nhau. Được khoảng 12 tiếng, nhỏ hơn nhạc 7–15 dB.

| Loại | Mốc | Trùng với hình |
|---|---|---|
| Whoosh / trầm (82–91% năng lượng dưới 200 Hz) | 4,55 s | zoom ra 2 |
| | 23,53 s | zoom vào |
| | 43,1 s | chú giải bật lên |
| Quét lên kiểu hoạt hình | 31,4 s | linh vật trắng + nhãn 2 cầu |
| | 33,4 s | Nút giao sân bay |
| Ding / pop sáng | 7,8 s | Ga 10 |
| | 8,4 s | linh vật xanh dương |
| | 16,1 s | linh vật đỏ |
| | 26,65 s | spotlight bung |
| | 27,9 s | linh vật tím |
| | 39,0 s | Sân bay Gia Bình |
| | 42,3 s | chữ chương tan |

- SFX đặt thưa: nhiều sự kiện không có tiếng, như linh vật xanh lá (6,4 s), nhãn Tuyến 8, Ga 9, Tuyến 5, R1 và các chữ chương.
- Giới hạn của phép đo: chỉ bắt được tiếng không lặp giữa 3 vòng nhạc. Nếu cùng một SFX nằm ở cùng vị trí nhịp trong 2 vòng thì sẽ lọt.

## 5. Lỗi và chỗ non tay

1. **Nhạc hở 2 lần.** Im tuyệt đối 0,40 s ở 30,15 s và ở 45,45 s, đúng các mối nối vòng nhạc. Cuối video nhạc chạy lại 0,8 s rồi bị cắt ngang.
2. **Linh vật bị cắt mép.** Linh vật đỏ đứng nửa người ngoài mép dưới-phải khoảng 1,8 s (21,4–23,2 s). Linh vật trắng và nhãn "Sân bay Gia Bình" bị cắt ở mép phải trong 37–42 s.
3. **Chữ khó đọc.** Video chỉ 720p nên chữ nhỏ ("cách The Cityon ~11,0 km") rất khó đọc trên điện thoại. Đoạn 29–40 s quá tải chữ.
4. **Chú giải lệch màu.** Chú giải ghi đường SB Gia Bình màu xám, nhưng trên bản đồ đường này vẽ màu trắng.
5. **Không có khung kết:** không CTA, không số điện thoại, không giá. Video dừng ở chú giải.
6. **Bìa quá ngắn.** Bìa chỉ có 3 khung nên chỉ dùng được làm thumbnail.

## 6. Công thức tái tạo (không gắn công cụ cụ thể)

**Nguyên liệu:**
- Ảnh vệ tinh của khu vực.
- Ảnh phối cảnh / masterplan dự án, cắt theo ranh lô.
- Logo dự án.
- Một linh vật PNG (đổi được màu).
- Danh sách điểm (ga, cầu, nút giao, sân bay) kèm toạ độ và khoảng cách.
- Nhạc vui khoảng 125 BPM.
- SFX loại pop, ding, whoosh, quét lên.

**Trình tự:**
1. Bìa 3 khung.
2. Ảnh hiện trạng hoà sang phối cảnh.
3. Lùi máy ra 2 nấc.
4. Mỗi chương:
   - chữ chương hiện ở vùng trống;
   - linh vật bật ra rồi chạy vẽ tuyến;
   - nhãn bật lên khi linh vật tới điểm;
   - dọn nhãn, giữ lại đường.
5. Chương cuối: tối nền, bung spotlight và các vòng km.
6. Tổng kết bằng bảng chú giải.

**Số liệu:**
- Cứ 1–1,5 s một phần tử mới.
- Vẽ một tuyến mất 1–5 s.
- Chữ chương hiện mờ dần 0,2–0,4 s; nhãn bật ~0,2 s.
- Vùng ngoài spotlight tối −36%.
- SFX nhỏ hơn nhạc 7–15 dB; nhạc −11,5 LUFS.
