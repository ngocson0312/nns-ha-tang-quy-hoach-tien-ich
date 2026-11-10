# nns-ha-tang-quy-hoach-tien-ich

Skill Claude Code: **link Google My Maps bản đồ quy hoạch + danh sách tiện ích quanh khu → video BẢN ĐỒ QUY HOẠCH + TIỆN
ÍCH dọc 9:16**. Lớp màu quy hoạch từng lô phủ lên ảnh vệ tinh Esri, ranh khu vàng phát sáng. Line sáng bám ĐƯỜNG ĐI THẬT
(qua cầu / phà thật, không chim bay) tới từng điểm, kèm nhãn "cách <tên> ~X km / ~850 m". Xã / cụm CN được khoanh vùng.
Chỉ có SFX (+ nhạc nếu user đưa), −14 LUFS, tự kiểm 9 mục. Nhân bản từ nns-ban-do-ha-tang.
Hướng dẫn đầy đủ cho Claude: [SKILL.md](SKILL.md).

## Cài trên máy mới (vd máy nhà)

1. Cần: Python 3.10+, git, ffmpeg + ffprobe **bản full** trong PATH.
2. Clone thẳng vào thư mục skill của dự án (Claude Code đọc skill ở `<dự án>\.claude\skills\<tên>\SKILL.md`):

   - Nếu `.claude\skills` của dự án là junction vào repo `SON_VIDEO_AI\skills` (như máy công ty):

     ```bash
     git clone https://github.com/ngocson0312/nns-ha-tang-quy-hoach-tien-ich.git "D:\____TTT_____\SON_AI_VIDEO\SON_VIDEO_AI\skills\nns-ha-tang-quy-hoach-tien-ich"
     ```

   - Nếu không có junction:

     ```bash
     git clone https://github.com/ngocson0312/nns-ha-tang-quy-hoach-tien-ich.git "D:\____TTT_____\SON_AI_VIDEO\.claude\skills\nns-ha-tang-quy-hoach-tien-ich"
     ```

3. Cài thư viện (phải có `-I` vì script chạy bằng `python -I`):

   ```bash
   python -I -m pip install -r "D:\____TTT_____\SON_AI_VIDEO\.claude\skills\nns-ha-tang-quy-hoach-tien-ich\requirements.txt"
   ```

   Kiểm tra: `python -I -X utf8 .claude\skills\nns-ha-tang-quy-hoach-tien-ich\scripts\kiem_tra_cai_dat.py`
   (hoặc chạy `CAI_DAT.bat`, xem `HUONG_DAN_CAI_DAT.md`).

4. Ảnh vệ tinh tải lại vào `<dự án>\_cache_tiles\esri` (cần mạng, dùng chung với nns-ban-do-ha-tang — đừng xoá).
   **Luôn gọi script qua đường `.claude\skills\…`** (không gọi thẳng trong `SON_VIDEO_AI\skills\…`), kẻo cache và
   thư mục dự án bị tính lệch.

## Chạy

Mọi lệnh chạy từ thư mục dự án `D:\____TTT_____\SON_AI_VIDEO`:

```bash
python -I -X utf8 .claude\skills\nns-ha-tang-quy-hoach-tien-ich\scripts\run.py --link "<link My Maps>" --work _htqh_<ten> --ten "<tên in thẻ>"
python -I -X utf8 .claude\skills\nns-ha-tang-quy-hoach-tien-ich\scripts\run.py --work _htqh_<ten>
python -I -X utf8 .claude\skills\nns-ha-tang-quy-hoach-tien-ich\scripts\run.py --work _htqh_<ten> --render
```

Nói với Claude: *"Làm video quy hoạch từ link My Maps `<link>`, tiện ích xung quanh: …"*.

## Đồng bộ máy nhà ↔ máy công ty

- Trước khi làm: `git pull` trong thư mục skill.
- Sửa xong (khi muốn mang sang máy kia): `git add -A`, `git commit -m "…"`, `git push`.
- Dữ liệu job (thư mục `_htqh_*` gồm hồ sơ, cache OSM, video ra) **không** nằm trong repo — chép riêng nếu cần làm tiếp
  job dở (vd `_htqh_vinhomes_olympic`, chép cả thư mục con `osm\` để khỏi hỏi lại Overpass).

## Giấy phép tài nguyên

- Phông trong `assets/fonts`: SIL OFL (xem `OFL*.txt`).
- SFX trong `assets/sfx`: kho sưu tầm từ skill gốc, **chưa rõ giấy phép** — video thương mại nên thay bằng SFX CC0 / đã mua,
  giữ nguyên tên file.
