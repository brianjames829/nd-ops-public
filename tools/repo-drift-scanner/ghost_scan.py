#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_EXCLUDES = {'.git', '.venv', 'venv', '__pycache__', 'node_modules'}
DEFAULT_EXTENSIONS = {'.md', '.txt', '.json', '.jsonl', '.yaml', '.yml', '.py', '.toml'}


@dataclass(frozen=True)
class AuthorityRule:
    pattern: str
    authority: str


@dataclass(frozen=True)
class TruthRule:
    rule_id: str
    description: str
    canonical: str
    stale_patterns: tuple[str, ...]
    severity: int = 10


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    text: str
    rule_id: str
    description: str
    canonical: str
    matched: str
    authority: str
    kind: str
    score: int


class ConfigError(ValueError):
    pass


def load_config(path: Path) -> tuple[list[AuthorityRule], list[TruthRule]]:
    data = json.loads(path.read_text(encoding='utf-8'))
    authority_rules = []
    for item in data.get('authority_rules', []):
        authority_rules.append(AuthorityRule(pattern=item['pattern'], authority=item['authority']))

    truths = []
    for item in data.get('truths', []):
        patterns = tuple(p for p in item.get('stale_patterns', []) if p)
        if not patterns:
            raise ConfigError(f"truth rule {item.get('id', '<unknown>')} has no stale_patterns")
        truths.append(
            TruthRule(
                rule_id=item['id'],
                description=item.get('description', item['id']),
                canonical=item['canonical'],
                stale_patterns=patterns,
                severity=int(item.get('severity', 10)),
            )
        )
    if not truths:
        raise ConfigError('config must contain at least one truth rule')
    return authority_rules, truths


def classify_authority(rel_path: str, rules: Iterable[AuthorityRule]) -> str:
    normalized = rel_path.replace('\\', '/')
    for rule in rules:
        if fnmatch.fnmatch(normalized, rule.pattern):
            return rule.authority
    return 'reference'


def iter_text_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if any(part in DEFAULT_EXCLUDES for part in path.parts):
            continue
        if path.suffix.lower() not in DEFAULT_EXTENSIONS:
            continue
        yield path


def scan(root: Path, authority_rules: list[AuthorityRule], truths: list[TruthRule], *, door: str | None = None) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    file_count = 0
    door_normalized = door.replace('\\', '/') if door else None

    for path in iter_text_files(root):
        rel = path.relative_to(root).as_posix()
        if door_normalized and rel != door_normalized:
            continue
        file_count += 1
        authority = classify_authority(rel, authority_rules)
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except UnicodeDecodeError:
            continue

        for line_number, line in enumerate(lines, start=1):
            lower = line.casefold()
            for truth in truths:
                for stale in truth.stale_patterns:
                    if stale.casefold() not in lower:
                        continue
                    historical = authority in {'historical', 'archive'}
                    kind = 'harmless_ghost' if historical else 'current_drift'
                    score = 0 if historical else truth.severity
                    findings.append(
                        Finding(
                            path=rel,
                            line=line_number,
                            text=line.strip(),
                            rule_id=truth.rule_id,
                            description=truth.description,
                            canonical=truth.canonical,
                            matched=stale,
                            authority=authority,
                            kind=kind,
                            score=score,
                        )
                    )
    return findings, file_count


def haunting_label(score: int) -> str:
    if score <= 10:
        return 'Quiet'
    if score <= 25:
        return 'Whispering'
    if score <= 50:
        return 'Haunted'
    if score <= 100:
        return 'Poltergeist'
    return 'CALL THE ARCHITECT'


def render_text(findings: list[Finding], file_count: int) -> str:
    drift = [f for f in findings if f.kind == 'current_drift']
    harmless = [f for f in findings if f.kind == 'harmless_ghost']
    score = sum(f.score for f in findings)

    out = []
    out.append('╔══════════════════════════════════════════╗')
    out.append('║       THE ARCHIVE REMEMBERS TOO MUCH     ║')
    out.append('╚══════════════════════════════════════════╝')
    out.append('')
    out.append(f'Inspecting {file_count} text files...')
    out.append('')
    out.append(f'CURRENT DRIFT        {len(drift)}')
    out.append(f'HARMLESS GHOSTS      {len(harmless)}')
    out.append(f'HAUNTING SCORE       {score}  [{haunting_label(score)}]')

    for finding in findings:
        out.append('')
        out.append('──────────────────────────────────────────')
        out.append('⚠ GHOST FOUND' if finding.kind == 'current_drift' else '👻 HISTORICAL ECHO')
        out.append('')
        out.append(f'{finding.path}:{finding.line}')
        out.append(f'  {finding.text}')
        out.append('')
        out.append(f'Rule:       {finding.description}')
        out.append(f'Matched:    {finding.matched}')
        out.append(f'Authority:  {finding.authority}')
        out.append(f'Canonical:  {finding.canonical}')
        if finding.kind == 'current_drift':
            out.append('Verdict:    CURRENT DRIFT — review recommended')
        else:
            out.append('Verdict:    HARMLESS GHOST — preserve history')

    out.append('')
    out.append('──────────────────────────────────────────')
    if drift:
        out.append(f'The archive has spoken. {len(drift)} correction(s) deserve attention.')
    else:
        out.append('The archive is quiet. Suspiciously quiet.')
    if harmless:
        out.append(f'{len(harmless)} historical ghost(s) may remain undisturbed.')
    return '\n'.join(out)


def finding_to_dict(f: Finding) -> dict:
    return {
        'path': f.path,
        'line': f.line,
        'text': f.text,
        'rule_id': f.rule_id,
        'description': f.description,
        'canonical': f.canonical,
        'matched': f.matched,
        'authority': f.authority,
        'kind': f.kind,
        'score': f.score,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Find stale statements that conflict with declared current truth.')
    parser.add_argument('root', type=Path, help='Repository or directory to inspect')
    parser.add_argument('--config', type=Path, required=True, help='JSON file containing authority and truth rules')
    parser.add_argument('--door', help='Inspect one relative file path instead of the whole tree')
    parser.add_argument('--json', action='store_true', help='Emit machine-readable JSON instead of theatrical text')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f'root is not a directory: {root}')
    authority_rules, truths = load_config(args.config)
    findings, file_count = scan(root, authority_rules, truths, door=args.door)

    if args.json:
        payload = {
            'root': str(root),
            'file_count': file_count,
            'current_drift_count': sum(f.kind == 'current_drift' for f in findings),
            'historical_ghost_count': sum(f.kind == 'harmless_ghost' for f in findings),
            'haunting_score': sum(f.score for f in findings),
            'findings': [finding_to_dict(f) for f in findings],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(render_text(findings, file_count))

    return 2 if any(f.kind == 'current_drift' for f in findings) else 0


if __name__ == '__main__':
    raise SystemExit(main())
