"""纯 Python 产物防覆盖、确认绑定和打印门，离线可测试。"""
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

PRINT_CHECKS = ('watertight', 'selfIntersection', 'degenerateFaces', 'duplicateVertices',
                'normals', 'volume', 'bbox', 'thinWalls')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_new(paths, force=False):
    existing = [str(path) for path in paths if Path(path).exists()]
    if existing and not force:
        raise FileExistsError('目标已存在，请使用新版本目录或显式 --force: ' + ', '.join(existing))


def validate_g9(gate, confirmation_file, blend):
    if gate != 'G9' or not confirmation_file:
        raise ValueError('export 必须指定 --confirm-gate G9 与 --confirmation-file 用户确认记录')
    record = json.loads(Path(confirmation_file).read_text(encoding='utf-8'))
    try:
        stamp = datetime.fromisoformat(record['confirmedAt'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('确认时间需时区')
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('G9 confirmedAt 必须是含时区的 ISO 时间') from exc
    if record.get('gate') != 'G9' or record.get('shapeAccepted') is not True:
        raise ValueError('G9 用户造型确认 shapeAccepted=true 缺失')
    if record.get('blendSha256') != sha256(blend):
        raise ValueError('G9 确认与当前最终 blend SHA256 不匹配')
    return record


def export_allowed(checks):
    return all(checks.get(name, {}).get('status') == 'pass' for name in PRINT_CHECKS)


def apply_measurement_evidence(checks, checks_file, blend, min_wall_mm):
    """只补脚本无法可靠推断的两项；证据文件、哈希、方法、数值及阈值必须齐全。"""
    if not checks_file:
        return checks
    source = Path(checks_file).resolve()
    report = json.loads(source.read_text(encoding='utf-8'))
    if report.get('blendSha256') != sha256(blend):
        raise ValueError('打印补测报告与最终 blend SHA256 不匹配')
    for name in ('selfIntersection', 'thinWalls'):
        item = report.get('checks', {}).get(name)
        if item is None:
            continue
        if not isinstance(item, dict) or not isinstance(item.get('method'), str) or not item['method'].strip():
            raise ValueError(name + ' 缺少补测 method')
        evidence = item.get('evidence', {})
        path = Path(evidence.get('path', ''))
        path = path if path.is_absolute() else source.parent / path
        if not path.is_file() or evidence.get('sha256') != sha256(path):
            raise ValueError(name + ' 补测证据文件不存在或 SHA256 不匹配')
        if item.get('unit') != ('count' if name == 'selfIntersection' else 'mm'):
            raise ValueError(name + ' 补测单位错误')
        measured = item.get('measured')
        threshold = item.get('threshold')
        if isinstance(measured, bool) or not isinstance(measured, (float, int)) or not math.isfinite(measured):
            raise ValueError(name + ' 缺少实测数值')
        if isinstance(threshold, bool) or not isinstance(threshold, (float, int)) or not math.isfinite(threshold):
            raise ValueError(name + ' 缺少有效阈值')
        if name == 'selfIntersection':
            valid = measured == 0 and threshold == 0
        else:
            valid = isinstance(threshold, (float, int)) and threshold >= min_wall_mm and measured >= threshold
        checks[name] = {'status': 'pass' if valid else 'fail', 'measured': measured,
                        'threshold': threshold, 'unit': item['unit'], 'method': item['method'],
                        'evidence': {'path': str(path.resolve()), 'sha256': evidence['sha256']}}
    return checks
