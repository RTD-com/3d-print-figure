#!/usr/bin/env python
"""逐图校验固定视角：解码、尺寸、正方形、透明或白底；输出报告和接触表。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image

from lib.contact_sheet import make_sheet
from lib.view_spec import ASPECT_RATIO, EXPECTED, MIN_BACKGROUND_RATIO, WHITE_CHANNEL_MIN, selected_files


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def background_stats(image, mode):
    has_alpha = 'A' in image.getbands() or 'transparency' in image.info
    rgba = image.convert('RGBA')
    total = image.width * image.height
    transparent = rgba.getchannel('A').histogram()[0]
    info = {'hasAlpha': has_alpha, 'transparentPixels': transparent,
            'transparentRatio': transparent / total}
    if mode == 'transparent':
        info['backgroundOk'] = has_alpha and info['transparentRatio'] > MIN_BACKGROUND_RATIO
    else:
        def white(pixel):
            return pixel[3] == 255 and min(pixel[:3]) >= WHITE_CHANNEL_MIN
        count = sum(1 for pixel in rgba.getdata() if white(pixel))
        corners = [rgba.getpixel(point) for point in ((0, 0), (image.width - 1, 0), (0, image.height - 1), (image.width - 1, image.height - 1))]
        info['whiteRatio'] = count / total
        info['whiteCorners'] = all(white(pixel) for pixel in corners)
        info['backgroundOk'] = info['whiteRatio'] > MIN_BACKGROUND_RATIO and info['whiteCorners']
    return info


def validate(in_dir, expected=8, views=None, alpha_mode='transparent'):
    files = []
    in_dir = Path(in_dir)
    names = selected_files(expected, views)
    for name in names:
        path = in_dir / name
        entry = {'file': name, 'exists': path.is_file(), 'ok': False}
        if entry['exists']:
            try:
                with Image.open(path) as image:
                    if image.format != 'PNG':
                        raise ValueError('预期 PNG 编码')
                    image.verify()
                with Image.open(path) as image:
                    image.load()
                    entry.update({'width': image.width, 'height': image.height,
                                  'colorMode': image.mode, 'bytes': path.stat().st_size,
                                  'sha256': sha256(path), **background_stats(image, alpha_mode)})
                    entry['square'] = image.width / image.height == ASPECT_RATIO
                    entry['ok'] = entry['square'] and entry['backgroundOk']
            except Exception as exc:
                entry['error'] = '{}: {}'.format(type(exc).__name__, exc)
        files.append(entry)
    sizes = {(entry.get('width'), entry.get('height')) for entry in files}
    checks = {'expectedImages': expected, 'actualImages': sum(entry['exists'] for entry in files),
              'sameDimensions': len(sizes) == 1 and all(entry.get('width') for entry in files),
              'square': all(entry.get('square', False) for entry in files),
              'allPngCrcOk': all(entry.get('width') and not entry.get('error') for entry in files),
              'backgroundOk': all(entry.get('backgroundOk', False) for entry in files),
              'trueTransparentBackground': alpha_mode == 'transparent' and all(entry.get('backgroundOk', False) for entry in files)}
    return {'tool': 'validate_views.py', 'input': str(in_dir), 'alphaMode': alpha_mode,
            'thresholds': {'minBackgroundRatioExclusive': MIN_BACKGROUND_RATIO, 'aspectRatio': '1:1', 'whiteChannelMin': WHITE_CHANNEL_MIN},
            'ok': all(entry['ok'] for entry in files) and checks['sameDimensions'], 'checks': checks, 'files': files}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--report', default='')
    parser.add_argument('--sheet', default='')
    parser.add_argument('--expected', type=int, default=8)
    parser.add_argument('--views', help='逗号分隔 slot 或完整文件名；子集需同时设置 --expected')
    parser.add_argument('--alpha-mode', choices=('transparent', 'white'), default='transparent')
    args = parser.parse_args(argv)
    try:
        report = validate(args.input, args.expected, args.views, args.alpha_mode)
    except ValueError as exc:
        parser.error(str(exc))
    root = Path(args.input)
    report_path = Path(args.report) if args.report else root / '校验报告.json'
    sheet = Path(args.sheet) if args.sheet else root / 'contact-sheet.png'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    make_sheet([{'path': root / entry['file'], 'name': entry['file'], 'ok': entry['ok']} for entry in report['files'] if entry.get('width')], sheet)
    print(json.dumps({'ok': report['ok'], 'report': str(report_path), 'sheet': str(sheet), 'alphaMode': args.alpha_mode}, ensure_ascii=False))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
