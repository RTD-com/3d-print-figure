#!/usr/bin/env python3
"""离线仓库检查；仅标准库、无网络、无业务执行、无写入。Python 3.8+。"""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS = {'$schema', '$id', 'title', 'description', 'default', 'examples', '$comment'}
KEYWORDS = ANNOTATIONS | {'type', 'enum', 'const', 'required', 'properties',
    'additionalProperties', 'items', 'prefixItems', 'minItems', 'maxItems',
    'minLength', 'maxLength', 'pattern', 'minimum', 'maximum', 'uniqueItems',
    'allOf', 'anyOf', 'oneOf', 'not', '$defs', 'definitions', '$ref', 'format'}


def validate_schema(value, schema, path='$', root_schema=None):
    """项目所用 JSON Schema 子集；不支持的约束报错，绝不静默跳过。"""
    if schema is True:
        return []
    if schema is False:
        return [path + ': schema forbids this value']
    if not isinstance(schema, dict):
        return [path + ': invalid schema']
    root_schema = root_schema or schema
    errors = [path + ': unsupported keyword ' + key for key in schema if key not in KEYWORDS]
    if '$ref' in schema:
        ref = schema['$ref']
        if not ref.startswith('#/'):
            return errors + [path + ': only local schema $ref is supported: ' + ref]
        target = root_schema
        try:
            for part in ref[2:].split('/'):
                target = target[part.replace('~1', '/').replace('~0', '~')]
        except (KeyError, TypeError):
            return errors + [path + ': unresolved $ref ' + ref]
        errors += validate_schema(value, target, path, root_schema)
    kinds = {'null': value is None, 'boolean': isinstance(value, bool),
        'integer': isinstance(value, int) and not isinstance(value, bool),
        'number': isinstance(value, (int, float)) and not isinstance(value, bool),
        'string': isinstance(value, str), 'array': isinstance(value, list),
        'object': isinstance(value, dict)}
    expected = schema.get('type')
    if expected and not any(kinds.get(t, False) for t in ([expected] if isinstance(expected, str) else expected)):
        return errors + [path + ': expected type ' + str(expected)]
    if 'enum' in schema and value not in schema['enum']:
        errors.append(path + ': value outside enum')
    if 'const' in schema and value != schema['const']:
        errors.append(path + ': value differs from const')
    if isinstance(value, dict):
        for key in schema.get('required', []):
            if key not in value:
                errors.append(path + ': missing ' + key)
        props = schema.get('properties', {})
        for key, child in value.items():
            rule = props.get(key, schema.get('additionalProperties', True))
            errors += validate_schema(child, rule, path + '.' + key, root_schema)
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0) or len(value) > schema.get('maxItems', float('inf')):
            errors.append(path + ': invalid item count')
        if schema.get('uniqueItems') and len({json.dumps(x, sort_keys=True, ensure_ascii=False) for x in value}) != len(value):
            errors.append(path + ': duplicate items')
        prefix = schema.get('prefixItems', [])
        for index, child in enumerate(value):
            rule = prefix[index] if index < len(prefix) else schema.get('items', True)
            errors += validate_schema(child, rule, path + '[' + str(index) + ']', root_schema)
    if isinstance(value, str):
        if len(value) < schema.get('minLength', 0) or len(value) > schema.get('maxLength', float('inf')):
            errors.append(path + ': invalid string length')
        if 'pattern' in schema and re.search(schema['pattern'], value) is None:
            errors.append(path + ': pattern mismatch')
        if 'format' in schema:
            if schema['format'] == 'date-time':
                from datetime import datetime
                try:
                    datetime.fromisoformat(value.replace('Z', '+00:00'))
                except ValueError:
                    errors.append(path + ': invalid date-time')
            elif schema['format'] not in ('uri', 'uri-reference'):
                errors.append(path + ': unsupported format ' + schema['format'])
            elif schema['format'] == 'uri' and not urlsplit(value).scheme:
                errors.append(path + ': invalid URI')
    if kinds['number'] and (value < schema.get('minimum', -float('inf')) or value > schema.get('maximum', float('inf'))):
        errors.append(path + ': outside numeric bounds')
    for branch in schema.get('allOf', []):
        errors += validate_schema(value, branch, path, root_schema)
    for keyword in ('anyOf', 'oneOf'):
        if keyword in schema:
            passes = sum(not validate_schema(value, branch, path, root_schema) for branch in schema[keyword])
            if (keyword == 'anyOf' and passes == 0) or (keyword == 'oneOf' and passes != 1):
                errors.append(path + ': ' + keyword + ' mismatch')
    if 'not' in schema and not validate_schema(value, schema['not'], path, root_schema):
        errors.append(path + ': forbidden by not')
    return errors


def markdown_links(text):
    # Code fences contain example links, not live repository references.
    text = re.sub(r'^\s*(`{3,}|~{3,}).*?^\s*\1\s*$', '', text, flags=re.M | re.S)
    for match in re.finditer(r'!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+["\'][^\n]*?["\'])?\)', text):
        yield match.group(1).strip('<>')
    for match in re.finditer(r'^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)', text, re.M):
        yield match.group(1).strip('<>')


def runtime_resources(text):
    """Literal runtime resource paths in prose and command examples, rooted at skillRoot."""
    pattern = r'(?<![\w.-])((?:scripts|references|assets[\\/]templates)[\\/](?:[\w.-]+[\\/])*[\w.-]+\.(?:py|ps1|mjs|bat|json|md))\b'
    return {match.group(1).replace('\\', '/') for match in re.finditer(pattern, text)}


def resource_target(md, link, root):
    parsed = urlsplit(link)
    if parsed.scheme or link.startswith(('#', '//')):
        return None
    path = unquote(parsed.path).replace('\\', '/')
    # Explicit runtime paths and visible placeholders are not repository resources.
    if not path or any(x in path for x in ('<', '>', '{', '}', '*')):
        return None
    if re.match(r'^(?:\./)?(?:1\.Codex|2\.DSH|3\.图片|4\.模型文件|5\.打印|手办|projects)/', path):
        return None
    base = root if md == root / 'codex-skill' / 'SKILL.md' else md.parent
    return (base / path).resolve()


def missing_links(md, root):
    return [(str(md.relative_to(root)), link) for link in markdown_links(md.read_text(encoding='utf-8'))
            if resource_target(md, link, root) is not None and not resource_target(md, link, root).exists()]


def package_files(root, spec):
    files = {}
    entry = spec['entry']
    files['SKILL.md'] = root / entry
    for item in spec['files']:
        source = root / item
        if not source.is_file():
            raise ValueError('missing release file: ' + item)
        files[item] = source
    return files


def check_package_closure(root, spec):
    files = package_files(root, spec)
    missing = []
    for target, source in files.items():
        if not source.is_file():
            missing.append('missing entry: ' + str(source))
            continue
        if source.suffix != '.md':
            continue
        for resource in runtime_resources(source.read_text(encoding='utf-8')):
            if resource not in files:
                missing.append(target + ': unpackaged runtime resource ' + resource)
        for link in markdown_links(source.read_text(encoding='utf-8')):
            resolved = resource_target(source, link, root)
            if resolved is None:
                continue
            try:
                relative = resolved.relative_to(root).as_posix()
            except ValueError:
                missing.append(target + ': external local dependency ' + link)
                continue
            if relative not in files:
                missing.append(target + ': unpackaged dependency ' + link)
    return missing



def tracked_file_error(root, rel):
    path = root / rel
    parts = {part.casefold() for part in Path(rel).parts}
    name = path.name.casefold()
    private_dirs = {'手办', 'projects', '.dsh', '.agents', '.tmp', 'downloads',
                    'browser-profile', 'browser-profiles', '.browser-profile', '.browser-profiles'}
    private_suffixes = {'.glb', '.gltf', '.stl', '.blend', '.obj', '.fbx', '.3mf', '.zip',
                        '.png', '.jpg', '.jpeg', '.webp', '.log', '.jsonl', '.pem', '.key',
                        '.p12', '.pfx', '.ppk'}
    if (parts & private_dirs or rel.startswith(('docs/evidence/', 'docs/reports/', 'docs/archive/'))
            or name in {'cookies', 'login data', 'local state', 'metadata.json', 'model-url.json', '.env'}
            or name.startswith('.env.') or re.search(r'\.blend\d+$', name)
            or path.suffix.lower() in private_suffixes or path.is_symlink()):
        return 'private or runtime file tracked: ' + rel
    if not path.is_file():
        return None
    if path.stat().st_size > 10 * 1024 * 1024:
        return 'large file tracked (>10 MiB): ' + rel
    credentials = rb'-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|[?&](?:q-signature|x-amz-signature)=[a-f0-9]{32,}'
    if re.search(credentials, path.read_bytes(), re.I):
        return 'credential pattern in tracked file: ' + rel
    return None


def run(root=ROOT):
    root = Path(root).resolve()
    checks = []
    def record(name, errors=(), detail=''):
        checks.append({'name': name, 'status': 'fail' if errors else 'pass', 'errors': list(errors), 'detail': detail})
    for rel in ('SKILL.md', 'codex-skill/SKILL.md'):
        path = root / rel
        try:
            text = path.read_text(encoding='utf-8')
            front = re.match(r'^---\r?\n(.*?)\r?\n---(?:\r?\n|$)', text, re.S)
            errors = []
            if not front:
                errors.append('missing frontmatter')
            else:
                fields = dict(re.findall(r'^(name|description):\s*(.+)$', front.group(1), re.M))
                if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', fields.get('name', '')) or len(fields.get('name', '')) > 64:
                    errors.append('name must be lowercase-hyphenated and 1..64 chars')
                if not 1 <= len(fields.get('description', '').strip()) <= 1024:
                    errors.append('description must be 1..1024 chars on one line')
            record('frontmatter:' + rel, errors)
        except (OSError, UnicodeError) as exc:
            record('frontmatter:' + rel, [str(exc)])
    md_errors = []
    json_errors = []
    data = {}
    syntax_errors = []
    files = [p for p in root.rglob('*') if p.is_file() and not any(part in ('.git', '__pycache__', '.venv', 'node_modules', '.tmp') for part in p.relative_to(root).parts)]
    for path in files:
        try:
            if path.suffix == '.md':
                md_errors += [file + ': ' + link for file, link in missing_links(path, root)]
            if path.suffix in ('.md', '.py', '.ps1', '.mjs', '.json', '.yml', '.bat') and path.read_bytes().startswith(b'\xef\xbb\xbf'):
                syntax_errors.append(str(path.relative_to(root)) + ': UTF-8 BOM forbidden')
            if path.suffix == '.json':
                data[path] = json.loads(path.read_text(encoding='utf-8'))
            if path.suffix == '.py':
                ast.parse(path.read_text(encoding='utf-8'), filename=str(path), feature_version=8)
        except (OSError, UnicodeError, ValueError, SyntaxError) as exc:
            (json_errors if path.suffix == '.json' else syntax_errors).append(str(path.relative_to(root)) + ': ' + str(exc))
    record('markdown-links', md_errors)
    record('json-parse', json_errors, str(len(data)) + ' JSON files')
    schema_errors = []
    schema_count = 0
    for path, value in data.items():
        if path.name.endswith('.schema.json'):
            # Validate schemas' own examples as well as standalone fixtures.
            for example in value.get('examples', []):
                schema_count += 1
                schema_errors += [path.name + ': ' + e for e in validate_schema(example, value)]
        elif isinstance(value, dict) and isinstance(value.get('$schema'), str) and not urlsplit(value['$schema']).scheme:
            target = (path.parent / value['$schema']).resolve()
            if target not in data:
                schema_errors.append(str(path.relative_to(root)) + ': missing schema ' + value['$schema'])
            else:
                schema_count += 1
                schema_errors += [str(path.relative_to(root)) + ': ' + e for e in validate_schema(value, data[target])]
    record('schema-examples', schema_errors, str(schema_count) + ' examples (documented local subset; not full meta-schema validation)')
    record('python-syntax', syntax_errors)
    node = shutil.which('node')
    if node:
        errors = []
        for path in files:
            if path.suffix == '.mjs':
                proc = subprocess.run([node, '--check', str(path)], capture_output=True, text=True, timeout=30)
                if proc.returncode:
                    errors.append(str(path.relative_to(root)) + ': ' + proc.stderr.strip())
        record('node-syntax', errors)
    else:
        checks.append({'name': 'node-syntax', 'status': 'skip', 'detail': 'node unavailable', 'errors': []})
    ps = shutil.which('pwsh') or shutil.which('powershell')
    if ps:
        errors = []
        for path in files:
            if path.suffix == '.ps1':
                literal = str(path).replace("'", "''")
                code = "$e=$null;$t=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('" + literal + "',[ref]$t,[ref]$e);if($e.Count){$e | ForEach-Object {$_.Message};exit 1}"
                proc = subprocess.run([ps, '-NoProfile', '-NonInteractive', '-Command', code], capture_output=True, text=True, timeout=30)
                if proc.returncode:
                    errors.append(str(path.relative_to(root)) + ': ' + proc.stdout.strip() + proc.stderr.strip())
        record('powershell-syntax', errors)
    else:
        checks.append({'name': 'powershell-syntax', 'status': 'skip', 'detail': 'PowerShell unavailable', 'errors': []})
    release_errors = []
    manifest = root / 'assets' / 'install-manifest.json'
    try:
        spec = data[manifest]
        for name, package in spec['packages'].items():
            release_errors += [name + ': ' + e for e in check_package_closure(root, package)]
    except (KeyError, OSError, ValueError) as exc:
        release_errors.append(str(exc))
    record('release-closure', release_errors)
    git = shutil.which('git')
    if git:
        proc = subprocess.run([git, '-C', str(root), 'ls-files', '-z', '--cached'], capture_output=True, timeout=30)
        errors = []
        if proc.returncode:
            errors.append('git ls-files failed')
        else:
            for raw in proc.stdout.split(b'\0'):
                if not raw:
                    continue
                error = tracked_file_error(root, raw.decode('utf-8'))
                if error:
                    errors.append(error)
        record('tracked-sensitive-files', errors)
    else:
        checks.append({'name': 'tracked-sensitive-files', 'status': 'skip', 'detail': 'git unavailable', 'errors': []})
    return {'ok': all(c['status'] != 'fail' for c in checks), 'checks': checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='仅输出 JSON')
    args = parser.parse_args()
    result = run()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for check in result['checks']:
            print('[{}] {} {}'.format(check['status'].upper(), check['name'], check.get('detail', '')))
            for error in check['errors']:
                print('  ' + error)
        print('selfcheck: ' + ('PASS' if result['ok'] else 'FAIL'))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
