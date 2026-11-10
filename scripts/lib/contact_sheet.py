"""共享字体和固定视角接触表；绝不扫描或递归纳入输出图片。"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def font(size):
    for name in ('arial.ttf', 'DejaVuSans.ttf', 'msyh.ttc', 'simhei.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_sheet(images, out, cols=3, thumb=512):
    out = Path(out)
    items = [item for item in images if Path(item['path']).resolve() != out.resolve()]
    if not items:
        return False
    if cols < 1 or thumb < 1:
        raise ValueError('cols/ thumb 必须大于 0')
    rows = (len(items) + cols - 1) // cols
    pad, label_h = 16, 34
    sheet = Image.new('RGB', (cols * thumb + pad * (cols + 1), rows * (thumb + label_h) + pad * (rows + 1)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    for index, item in enumerate(items):
        with Image.open(item['path']) as source:
            img = source.convert('RGBA')
        img.thumbnail((thumb, thumb))
        bg = Image.new('RGBA', (thumb, thumb), (40, 40, 40, 255))
        bg.alpha_composite(img, ((thumb - img.width) // 2, (thumb - img.height) // 2))
        x = pad + index % cols * (thumb + pad)
        y = pad + index // cols * (thumb + label_h + pad)
        sheet.paste(bg.convert('RGB'), (x, y))
        color = (230, 230, 230) if 'ok' not in item else ((0, 220, 0) if item['ok'] else (255, 80, 80))
        draw.text((x, y + thumb + 6), item['name'], fill=color, font=font(22))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return True
