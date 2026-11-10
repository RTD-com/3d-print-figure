#!/usr/bin/env python
"""生成脱敏交付 manifest，全部文件流式 SHA256，排除浏览器资料与签名URL记录。"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

SKIP_DIRS = {'.browser-profile', '.browser-profiles', 'browser-profile', 'browser-profiles', 'profiles', 'profile', 'user data', 'node_modules', '.git', '__pycache__', '.tmp', '.venv'}
SKIP_FILES = {'model-url.json', 'metadata.json'}
SIGNED_QUERY = re.compile(r'https?://[^\s"<>]*[?&](?:[^=&#]*(?:signature|token|credential|expires|authorization|secret|key)[^=&#]*)=', re.I)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def provenance():
    root = Path(__file__).resolve().parents[1]
    manifest = root / 'manifest.json'
    if manifest.is_file():
        value = json.loads(manifest.read_text(encoding='utf-8'))
        return value.get('version', 'unknown'), value.get('sourceCommit', 'unknown')
    skill = (root / 'SKILL.md').read_text(encoding='utf-8')
    match = re.search(r'版本\s+(\d+\.\d+\.\d+)', skill)
    result = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=False)
    return match.group(1) if match else 'unknown', result.stdout.strip() if result.returncode == 0 else 'unknown'


def excluded(path, root, out):
    if path.resolve() == out.resolve() or path.is_symlink():
        return True
    relative = path.relative_to(root)
    if path.name.lower() in SKIP_FILES or any(part.lower() in SKIP_DIRS or part.lower().endswith(('-profile', '-profiles')) for part in relative.parts):
        return True
    if path.suffix.lower() in ('.json', '.txt', '.md', '.log'):
        try:
            with path.open('r', encoding='utf-8') as source:
                # 滚动窗口避免超大日志一次读入内存，也不在清单泄露URL内容。
                tail = ''
                for chunk in iter(lambda: source.read(65536), ''):
                    text = tail + chunk
                    if SIGNED_QUERY.search(text):
                        return True
                    tail = text[-8192:]
        except UnicodeError:
            return True
    return False


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--output', default='')
    args = parser.parse_args(argv)
    root = Path(args.project).resolve()
    if not root.is_dir():
        parser.error('项目目录不存在')
    out = Path(args.output).resolve() if args.output else root / '2.DSH' / 'manifest.json'
    entries = []
    for path in sorted(root.rglob('*')):
        if path.is_file() and not excluded(path, root, out):
            entries.append({'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha256(path)})
    by_top = {}
    for entry in entries:
        top = entry['path'].split('/')[0]
        by_top[top] = by_top.get(top, 0) + entry['bytes']
    version, commit = provenance()
    report = {'schemaVersion': 2, 'skillVersion': version, 'sourceCommit': commit,
              'project': root.name, 'fileCount': len(entries),
              'totalBytes': sum(entry['bytes'] for entry in entries), 'bytesByTopDir': by_top,
              'redaction': 'profile/metadata/model-url/signed-URL records excluded', 'files': entries}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'manifest': str(out), 'fileCount': len(entries), 'totalMB': round(report['totalBytes'] / 1024 / 1024, 1)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
