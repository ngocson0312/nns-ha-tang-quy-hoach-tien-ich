"""Ghép các khung PNG xem trước thành tấm (5 khung/tấm) có ghi giây."""
import glob, os, sys
from PIL import Image, ImageDraw, ImageFont


def main():
    src, out = sys.argv[1], sys.argv[2]
    fs = sorted(glob.glob(os.path.join(src, "f_*.png")))
    try:                                    # font đi kèm skill (máy nào cũng có, không phụ thuộc Windows)
        F = ImageFont.truetype(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                            "assets", "fonts", "BeVietnamPro-Bold.ttf"), 28)
    except Exception:
        F = ImageFont.load_default()
    w, h = 432, 768
    outs = []
    for k in range(0, len(fs), 5):
        sel = fs[k:k + 5]
        W = Image.new("RGB", (len(sel) * (w + 6), h + 40), (20, 20, 20))
        d = ImageDraw.Draw(W)
        for i, f in enumerate(sel):
            W.paste(Image.open(f).convert("RGB").resize((w, h)), (i * (w + 6), 40))
            d.text((i * (w + 6) + 6, 4), os.path.basename(f)[2:-4].lstrip("0") + " s", fill=(255, 214, 90), font=F)
        p = f"{out}_{k // 5}.jpg"
        W.save(p, quality=88)
        outs.append(p)
    print("\n".join(outs))


if __name__ == "__main__":
    main()
