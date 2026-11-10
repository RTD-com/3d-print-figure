#!/usr/bin/env python
"""按固定八视角清单生成接触表，不将已有接触表当作输入。"""
import argparse
from pathlib import Path
import sys

from lib.contact_sheet import make_sheet
from lib.view_spec import selected_files


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', default='')
    parser.add_argument('--cols', type=int, default=3)
    parser.add_argument('--thumb', type=int, default=512)
    parser.add_argument('--expected', type=int, default=8)
    parser.add_argument('--views', default='')
    args = parser.parse_args(argv)
    root = Path(args.input)
    out = Path(args.output) if args.output else root / 'contact-sheet.png'
    try:
        names = selected_files(args.expected, args.views)
        files = [{'path': root / name, 'name': name} for name in names if (root / name).is_file() and (root / name).resolve() != out.resolve()]
        if not files:
            print('no expected view images', file=sys.stderr)
            return 1
        make_sheet(files, out, args.cols, args.thumb)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(str(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
