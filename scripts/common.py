"""CẤU HÌNH ĐÃ CHỐT của nns-ban-do-ha-tang — mọi số đo/hằng số dựng nằm ở đây, script khác chỉ import.

Nguồn số đo: video mẫu KB5 "Hạ tầng giao thông quanh The CityOn" (46,7 s, đo 17/10/2026, xem
references/phan-tich-mau.md) + luật máy quay êm user đã chốt cho video bản đồ (memory feedback_ban_do_may_quay_em).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ASSETS = os.path.join(SKILL, "assets")
FONTS = os.path.join(ASSETS, "fonts")
SFX_DIR = os.path.join(ASSETS, "sfx")

# ------------------------------------------------------------------ khung hình
W, H, FPS = 1080, 1920, 30
SAFE_X0, SAFE_X1 = 48, W - 48            # lề trái/phải cho chữ & icon
SAFE_Y0, SAFE_Y1 = 200, 1590             # TikTok/Facebook: đáy ~330 px bị UI che → chữ nằm trên y≈1600
ICON_EDGE = 110                          # icon dẫn nét đi vào dải này của mép khung thì mờ dần rồi tắt

# ------------------------------------------------------------------ màu (mẫu đo từ chú giải của KB5)
PALETTE = {
    "metro": ["#2FC85E", "#1E90FF", "#12B5A8"],
    "duong": ["#FFB800", "#CC75FF", "#FE3A5A", "#FF7A1A"],
    "sanbay": ["#E9EEF5"],
}
WHITE = (255, 255, 255)
INK = (28, 30, 38)                       # chữ tối trên thẻ trắng
PIN_RED = (230, 40, 60)

# ------------------------------------------------------------------ font
F_LABEL = os.path.join(FONTS, "BeVietnamPro-Black.ttf")        # tên ga/cầu/tuyến
F_SUB = os.path.join(FONTS, "BeVietnamPro-Bold.ttf")           # dòng "cách … ~X km", nhãn km
F_LEGEND = os.path.join(FONTS, "BeVietnamPro-SemiBold.ttf")
F_CARD = os.path.join(FONTS, "Montserrat-Black.ttf")           # tên dự án trên thẻ ghim
F_SCRIPT = os.path.join(FONTS, "GreatVibes-Regular.ttf")       # KHÔNG dùng nữa (user 18/10: bỏ chữ uốn lượn, "&" đọc thành "jj")
F_TITLE = os.path.join(FONTS, "BeVietnamPro-Black.ttf")         # chữ chương + dòng phụ bìa: chữ ĐẬM THẲNG, đọc rõ [user chốt 18/10]
F_COVER = os.path.join(FONTS, "BarlowCondensed-BlackItalic.ttf")

# cỡ chữ @1080 (mẫu 720p chữ quá nhỏ → phóng ×1,5 rồi tăng thêm ~15%)
S_LABEL, S_LABEL2, S_SUB = 50, 40, 30
S_ROUTE = 40                             # nhãn tuyến "TUYẾN 8"
S_ROUTE_SUB = 28
S_CHAPTER = 80                           # chữ chương Be Vietnam Pro Black 80 px (thư pháp cũ 118)
CHAPTER_TOP, CHAPTER_BOT = (255, 238, 140), (255, 190, 30)   # chữ chương vàng gradient [user chốt 18/10]
CHAPTER_EDGE = (120, 70, 0)                                 # viền nâu mảnh 2 px
S_KM = 30
S_LEGEND = 34
S_COVER1, S_COVER2, S_COVER3 = 138, 150, 66

CARD_MINI_KM = 4.0                       # khung rộng > 4 km thật → thẻ dự án thu thành chip (mẫu: chip khi lùi ra ~4×
                                         # khỏi cận cảnh 1 km). Ngưỡng cũ 9 km để thẻ to che ga sát nhà (Matrix One 17/10)

# ------------------------------------------------------------------ nét tuyến
LINE_W = 9                               # lõi màu (mẫu 5 px @720 ≈ 7,5 @1080)
LINE_EDGE = 2                            # viền trắng mỏng mỗi bên
LINE_SHADOW = 10
# "line sáng" từ khu quy hoạch tới tiện ích (user 10/11/2026): quầng màu tuyến (độ dày px, sigma mờ, hệ số cộng sáng)
GLOW_LAYERS = ((34, 16, 0.85), (16, 6, 0.75))
ICON_R = 36                              # bán kính huy hiệu phương tiện
DRAW_SPEED = 400                         # px/s trên màn hình — user 18/10 chê chậm (250 cũ: gần nửa video là chờ)
DRAW_MIN, DRAW_MAX = 1.1, 3.0            # s cho một tuyến (cũ 1,8–5)
NEXT_AT = 0.45                           # tuyến sau bắt đầu khi tuyến trước vẽ được 45 % (chạy gối nhau; cũ 75 %)

# ------------------------------------------------------------------ nhịp (s)
COVER_HOLD = 0.9                         # bìa đứng 0,9 s + mờ 0,3 (cũ 1,25)
COVER_FADE = 0.30
PLAN_XFADE = (0.55, 0.95)                # hiện trạng → phối cảnh
INTRO_HOLD = 0.2
CHAPTER_IN, CHAPTER_OUT = 0.40, 0.30
LABEL_POP = 0.30
ICON_WAIT = 0.12                         # icon bật rồi chờ chừng này mới chạy (cũ 0,25)
FIRST_POP = 0.05                         # icon đầu tiên của chương bật ngay khi máy dừng (cũ 0,25)
POI_OFF_ROUTE_M = 300                    # điểm có toạ độ riêng cách tuyến hơn chừng này (m) → ghim đúng vị trí thật
LEADER_MIN = 10 ** 6                     # TẮT đường dẫn nhãn→ghim (user 17/10: "mấy cái này là gì vậy" — gây rối); nhãn
                                         # chỉ được đặt SÁT ghim (8 vị trí kề), chật thì nhỏ lại / thu gọn sớm
SECOND_DIR_DELAY = 0.3                   # tuyến vẽ 2 chiều: icon chiều thứ 2 bật trễ chừng này (không chồng khít icon 1)
FULL_NEAR_SLOTS = 8                      # số vị trí kề ghim được thử cho nhãn đầy đủ
CARD_SIDES = ("tren", "phai", "trai", "duoi")   # thẻ dự án: chọn 1 phía cố định cả video, ít đè nét tuyến nhất
PIN_MIN_GAP = 34                         # px — 2 ghim cùng lúc trên màn hình gần hơn → cảnh báo (ghim chồng)
RING_MIN_PX = 130                        # vòng km có bán kính màn hình nhỏ hơn (ở cuối chương) → bỏ vòng đó
OUTRO_PIN_GAP = 46                       # px — ở khung kết, ghim kém ưu tiên nằm gần ghim khác hơn → ẩn đi cho gọn
FULL_FAIL_SCORE = 900                    # nhãn đầy đủ tệ hơn mức này (tràn mép / đè thẻ / gần ghim khác) → không hiện, chỉ tên ngắn
CARD_HARD = 12                           # trọng số vật cản của thẻ dự án — chữ KHÔNG được chạm thẻ (TUYẾN 1 đè thẻ Landmark 81, 17/10)
LABEL_ON_PIN_PENALTY = 2000              # nhãn tuyến chạm ghim (kể cả 6 px quanh) — "Nhổn – Cầu Giấy" đè ghim SVĐ (Matrix One 18/10)
WRONG_PIN_PENALTY = 400                  # nhãn gần ghim KHÁC hơn ghim mình → đọc nhầm; 120 vẫn thua phạt chồng nét (GA MỄ TRÌ ↔ LÊ ĐỨC THỌ, 17/10)
SHORT_MAX_SCORE = 140                    # điểm chồng lấn tối đa của nhãn ngắn; vượt thì ẩn
SHORT_MAX_SCORE_OUTRO = 320              # khung kết đông nét hơn — nới ngưỡng, vẫn chỉ cho chỗ sát ghim
FULL_HOLD = 2.6                          # nhãn đầy đủ (dòng 'cách … km') đứng 2,6 s rồi thu về tên ngắn (cũ 3,5)
CHAPTER_TAIL = 0.5                       # giữ sau nét cuối của chương (cũ 1,4)
READ_TIME = 1.2                          # nhãn cuối của chương đứng ít nhất chừng này trước khi chương tắt (cũ 1,8)
SPOT_DIM = 0.64                          # ngoài vòng spotlight còn 64 % độ sáng (đo mẫu: 144 → 92)
SPOT_GROW = 0.9
LEGEND_IN = 0.45
OUTRO_HOLD = 2.2                         # khung kết + chú giải (cũ 3,0)

# ------------------------------------------------------------------ máy quay (luật "êm" user đã chốt)
MAX_PAN_PX = 14.0                        # px/khung, đo điểm dưới tâm neo
MAX_ZOOM_PCT = 7.0                       # %/khung
PLAN_MARGIN = 0.96                       # kế hoạch nhắm ≤ 96 % ngưỡng: ORB đo trên file cuối nhiễu ~1–2 % (Vinhomes Olympic
                                         # 10/11: kế hoạch 13,95 → đo p99 14,1 = trượt mục 6)
RHO = 1.42                               # van Wijk & Nuij
MOVE_MIN = 1.2                           # s tối thiểu một cú bay
VIEW_MARGIN = 0.12                       # lề khi khớp khung một chương (tỉ lệ bề rộng)
TIGHT_MIN_U = 4.5                        # m/px tối thiểu của chương "khung_sát" (line từ mép khu quy hoạch) — zoom sát hơn thì
                                         # cú bay sang chương xa mất 7 s (Vinhomes Olympic 10/11/2026: 2,9 m/px, bay 7,2 s)
# USER CHỐT 17/10/2026 (so 2 bản A/B trên The CityOn): KIỂU A — chương spotlight + khung kết CHỪA CHỖ để mọi nhãn
# TRỌN trong vùng an toàn, bản đồ nhìn xa hơn mẫu cũng được → EDGE_FIT = False. KHÔNG tự bật lại.
# True = kiểu B (sát mép như mẫu: điểm xa nhất nằm ở mép, nhãn ghim sát mép bị cắt) — user đã xem và KHÔNG chọn.
EDGE_FIT = False
EDGE_PAD = 40                            # px — điểm xa nhất cách mép khung chừng này (ghim vẫn thấy trọn)
EDGE_CROP_ZONE = 150                     # px — ghim cách mép trái/phải dưới mức này thì nhãn được tràn ra ngoài

# ------------------------------------------------------------------ âm thanh
LUFS = -14.0
TP = -1.5
MUSIC_REL_DB = -2.0                      # nhạc trước master (so với −14) — không có giọng nên nhạc là nền chính
SFX_OVER_MUSIC = 6.0                     # đỉnh RMS 50 ms của SFX cao hơn nhạc tại chỗ đặt (dB) — user: "SFX phải nghe rõ"
AAC_HEADROOM = 1.3                       # trần limiter thấp hơn TP chừng này vì AAC đẩy đỉnh lên ~1,4 dB (đo 17/10)
SFX = {                                  # tên sự kiện → (file, gain dB cộng thêm vào SFX_OVER_MUSIC, lệch thời gian s)
    "icon": ("pop.mp3", 0.0, -0.02),
    "icon2": ("pop-bubble.wav", -1.0, -0.02),
    "label": ("quick-ting.mp3", -2.0, 0.0),
    "chapter": ("quick-swoosh.mp3", 0.0, -0.10),
    "move": ("whoosh.wav", -2.0, 0.0),            # canh ĐỈNH (whoosh.wav đỉnh ở 2,55 s sau onset) vào giữa cú bay — xem SFX_PEAK
    "spot": ("ting.wav", -1.0, 0.0),
    "airport": ("take-off.mp3", -3.0, 0.0),
    "legend": ("new-item.wav", -2.0, 0.0),
    "cover": ("swoosh.mp3", 0.0, 0.0),
}
SFX_NO_MUSIC_REF = -22.0                 # không có nhạc: coi "nền" ở mức này (dB RMS 50 ms) để đặt SFX
SFX_ONLY_PEAK_LUFS_M = -12.0             # không có nhạc: đẩy sao cho độ to TỨC THỜI lớn nhất ≈ mức này (không chuẩn −14 tích phân)
SFX_GAP = 0.18                           # hai tiếng cùng loại không gần hơn
SFX_PEAK = {"move", "airport"}           # loại canh theo ĐỈNH tiếng (dâng chậm) thay vì onset — "tiếng đúng khung hình"

# ------------------------------------------------------------------ chỉ hạ tầng ĐÃ VẬN HÀNH (user chốt 17/10/2026)
# "chỉ ghi hoặc đưa cái gì lên khi đã đi vào hoạt động; cái gì đang làm hoặc đang test thì chưa đưa vào"
RAIL_OPERATING = "^(rail|subway|light_rail|monorail|tram|narrow_gauge)$"          # railway=construction/proposed bị loại
HIGHWAY_NOT_OPERATING = "^(construction|proposed|planned|abandoned|disused|razed)$"
STATUS_OK = ("van_hanh",)                                    # khoá "trang_thai" của tuyến/điểm trong hồ sơ
# đường đi thật (định tuyến trên đồ thị đường OSM): hệ số chi phí theo cấp đường — ưu tiên trục lớn
ROAD_CLASSES = ["motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential"]
ROAD_COST = {"motorway": 0.7, "trunk": 0.75, "primary": 0.85, "secondary": 1.0, "tertiary": 1.2,
             "unclassified": 1.6, "residential": 1.8, "living_street": 1.9, "service": 2.2, "track": 2.6}
ROAD_LOCAL_EXTRA = ["living_street", "service", "track"]     # chỉ trong ROUTE_LOCAL_KM quanh đầu mút / điểm qua
ROUTE_LOCAL_KM = 1.6                                         # quanh 2 đầu mút được đi cả đường nhỏ (tới tận cổng)
ROUTE_BBOX_FRAC = 0.6                                        # khung tìm đường nới = 60 % quãng chim bay (vòng qua cầu/phà)
FERRY_COST = 3.0                                             # phà: chỉ đi khi không có cầu gần (chờ phà, chậm)
XAY_NOI_M = 40                                               # nối ảo đường đang xây ↔ đường đang chạy (chưa có nút giao OSM)

# ------------------------------------------------------------------ cổng duyệt
GATE_EXIT = 2                            # mã thoát khi dừng ở cổng duyệt nội dung
