# nns-ban-do-ha-tang — hướng dẫn cài đặt

Skill cho **Claude Code**: gõ tên một địa điểm ở Việt Nam (dự án BĐS, toà nhà, di tích, hồ…) → ra video dọc 9:16
"hạ tầng giao thông quanh <địa điểm>" trên ảnh vệ tinh thật: metro, vành đai, cầu, sân bay, tiện ích đang vận hành,
mỗi điểm có khoảng cách tới địa điểm, máy quay bay êm, SFX, tự kiểm 9 mục trước khi giao.

## Cách nhanh nhất (3 bước)

1. Cài **Python** (https://www.python.org/downloads/ — Windows tick ô **Add python.exe to PATH**) và **Claude Code**.
2. Giải nén zip → mở thư mục `nns-ban-do-ha-tang` → **bấm đúp `CAI_DAT.bat`** (Windows) hoặc **`CAI_DAT.command`** (Mac; máy chặn
   thì chuột phải → Open). Nó tự chép skill vào `~/.claude/skills`, cài thư viện, hỏi cài ffmpeg nếu thiếu, rồi kiểm tra máy.
   Thấy `🎉 Xong!` là được (có cài ffmpeg thì mở lại Claude Code).
3. Mở Claude Code ở **thư mục nào cũng được** và gõ tên địa điểm sau lệnh skill:

```
/nns-ban-do-ha-tang Lăng Bác
/nns-ban-do-ha-tang Chợ Hàn, Đà Nẵng
/nns-ban-do-ha-tang Landmark 81
/nns-ban-do-ha-tang The Matrix One, số 1 Lê Quang Đạo, Nam Từ Liêm, Hà Nội
```

Gõ **tên công trình trước**, địa chỉ / thành phố sau dấu phẩy (giúp chọn đúng khi nhiều nơi trùng tên). Không chắc tên trên bản đồ?
Dán thêm link Google Maps hoặc toạ độ. Skill khảo sát xong sẽ gửi **bảng duyệt + ảnh xem trước** và hỏi vài câu — trả lời là nó dựng.

Phần dưới là cài TAY từng bước (khi không dùng được file bấm đúp).

## Cần có

| Thứ | Ghi chú |
|---|---|
| Claude Code | bản desktop (tab Code) hoặc dòng lệnh `claude` |
| Python 3.10 trở lên | https://www.python.org/downloads/ — Windows nhớ tick **Add python.exe to PATH** |
| ffmpeg + ffprobe | Windows: `winget install Gyan.FFmpeg` · macOS: `brew install ffmpeg` · Ubuntu: `sudo apt install ffmpeg` |
| Internet | lúc chạy skill tải ảnh vệ tinh (Esri) và dữ liệu bản đồ (OpenStreetMap) |

Máy không cần GPU. Một video ~30 s dựng mất khoảng 3–5 phút.

## Cài (5 bước)

1. **Giải nén** file zip → được thư mục `nns-ban-do-ha-tang/`.
2. **Chép thư mục đó vào** một trong hai chỗ:
   - `<thư mục dự án của bạn>/.claude/skills/` — chỉ dùng trong dự án đó, **hoặc**
   - `~/.claude/skills/` (Windows: `C:\Users\<tên bạn>\.claude\skills\`) — dùng ở mọi dự án.

   Chưa có thư mục `.claude/skills` thì tạo mới. Đúng chỗ là có file `.claude/skills/nns-ban-do-ha-tang/SKILL.md`.
3. **Cài thư viện Python** (mở dòng lệnh tại thư mục skill):
   ```
   python -m pip install -r requirements.txt
   ```
4. **Kiểm tra máy**:
   ```
   python scripts/kiem_tra_cai_dat.py
   ```
   Báo `✅ Máy đã sẵn sàng` là xong. Có `✗` thì làm theo dòng "CẦN SỬA" nó in ra.
5. **Mở lại Claude Code** trong thư mục dự án và gõ `/nns-ban-do-ha-tang <tên địa điểm>`.

## Dùng

- Skill tự khảo sát OpenStreetMap, in **bảng duyệt** + **ảnh xem trước**, rồi hỏi bạn vài câu (đúng địa điểm chưa, giữ/bớt
  điểm nào, nhạc nền…). Trả lời xong nó mới dựng video.
- Muốn có nhạc nền: đưa đường dẫn file mp3/wav của bạn khi được hỏi (skill không tự tạo nhạc).
- Tên trùng nhiều nơi / tìm không ra: nói thêm địa chỉ, hoặc dán toạ độ / link Google Maps.
- Video và file làm việc nằm trong thư mục `_bandoht_<tên>/` ở thư mục dự án.
- Ảnh vệ tinh được lưu lại để lần sau nhanh hơn (cài bằng CAI_DAT: `~/.cache/nns_ban_do/`; chép skill vào một dự án:
  `_cache_tiles/` trong dự án đó) — đừng xoá giữa các lần chạy. Muốn đặt chỗ khác: biến môi trường `NNS_TILE_CACHE`.

## Lỗi hay gặp

| Hiện tượng | Cách xử lý |
|---|---|
| Đứng lâu ở bước "hỏi OSM…" | máy chủ Overpass công cộng đang quá tải — skill tự thử lại, cứ chờ (có lúc 5–10 phút) |
| `ffmpeg` not found | cài ffmpeg (bảng trên) rồi **mở lại** Claude Code / cửa sổ dòng lệnh |
| Gõ `/nns-ban-do-ha-tang` không thấy skill | sai chỗ chép — phải có `.claude/skills/nns-ban-do-ha-tang/SKILL.md`; mở lại Claude Code |
| `ModuleNotFoundError` | chạy lại bước 3 bằng đúng `python` mà Claude Code dùng |

## Nguồn dữ liệu & bản quyền

- Ảnh vệ tinh: Esri World Imagery — khi đăng video nên ghi nguồn "Esri, Maxar, Earthstar Geographics".
- Dữ liệu đường, ga, cầu, địa điểm: © OpenStreetMap contributors (ODbL).
- Font trong `assets/fonts/` (Be Vietnam Pro, Barlow Condensed, Montserrat, Great Vibes): giấy phép SIL Open Font License 1.1.
- Hiệu ứng âm thanh trong `assets/sfx/`: để dùng thử. Đăng thương mại thì tự kiểm tra giấy phép hoặc thay bằng file của bạn
  (giữ nguyên tên file).
