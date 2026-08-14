from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_EXCLUDES = {'.git', '.venv', 'venv', '__pycache__', 'node_modules'}
DEFAULT_EXTENSIONS = {'.md', '.txt', '.json', '.jsonl', '.yaml', '.yml', '.py', '.toml'}
MATCH_MODES = {'substring', 'phrase', 'regex'}
HISTORICAL_AUTHORITIES = {'historical', 'archive'}
INLINE_MARKER = re.compile(r'drift-ignore:\s*([A-Za-z0-9_.-]+)', re.IGNORECASE)
SLUG = re.compile(r'^[A-Za-z0-9_.-]+$')


@dataclass(frozen=True)
class AuthorityRule:
    pattern: str
    authority: str


@dataclass(frozen=True)
class PatternSpec:
    value: str
    match: str = 'substring'


@dataclass(frozen=True)
class TruthRule:
    rule_id: str
    description: str
    canonical: str
    stale_patterns: tuple[PatternSpec, ...]
    severity: int = 10


@dataclass(frozen=True)
class SuppressionRule:
    path: str
    rule_id: str
    reason: str


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
    context_before: tuple[tuple[int, str], ...] = ()
    context_after: tuple[tuple[int, str], ...] = ()
    suppression_source: str | None = None
    suppression_reason: str | None = None


@dataclass(frozen=True)
class ScanResult:
    findings: tuple[Finding, ...]
    suppressed: tuple[Finding, ...]
    file_count: int

    @property
    def drift(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.kind == 'current_drift')

    @property
    def ghosts(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.kind == 'harmless_ghost')

    @property
    def haunting_score(self) -> int:
        return sum(f.score for f in self.findings)


class ConfigError(ValueError):
    pass


def _expect_dict(value: object, where: str) -> dict:
    if not isinstance(value, dict):
        raise ConfigError(f'{where} must be an object')
    return value


def _expect_list(value: object, where: str) -> list:
    if not isinstance(value, list):
        raise ConfigError(f'{where} must be an array')
    return value


def _expect_string(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f'{where} must be a non-empty string')
    return value.strip()


def _reject_unknown(item: dict, allowed: set[str], where: str) -> None:
    unknown = sorted(set(item) - allowed)
    if unknown:
        raise ConfigError(f"{where} contains unknown field(s): {', '.join(unknown)}")


def _parse_pattern(raw: object, where: str) -> PatternSpec:
    if isinstance(raw, str):
        return PatternSpec(_expect_string(raw, where))

    item = _expect_dict(raw, where)
    _reject_unknown(item, {'value', 'match'}, where)
    value = _expect_string(item.get('value'), f'{where}.value')
    mode = item.get('match', 'substring')
    if not isinstance(mode, str) or mode not in MATCH_MODES:
        raise ConfigError(f"{where}.match must be one of: {', '.join(sorted(MATCH_MODES))}")
    if mode == 'regex':
        try:
            re.compile(value, re.IGNORECASE)
        except re.error as exc:
            raise ConfigError(f'{where} has invalid regex: {exc}') from exc
    return PatternSpec(value, mode)


def load_config(path: Path) -> tuple[list[AuthorityRule], list[TruthRule], list[SuppressionRule]]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise ConfigError(f'config file not found: {path}') from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f'config JSON is invalid at line {exc.lineno}, column {exc.colno}: {exc.msg}') from exc

    root = _expect_dict(data, 'config')
    _reject_unknown(root, {'authority_rules', 'truths', 'suppressions'}, 'config')

    authorities: list[AuthorityRule] = []
    seen_patterns: dict[str, str] = {}
    for index, raw in enumerate(_expect_list(root.get('authority_rules', []), 'authority_rules')):
        where = f'authority_rules[{index}]'
        item = _expect_dict(raw, where)
        _reject_unknown(item, {'pattern', 'authority'}, where)
        pattern = _expect_string(item.get('pattern'), f'{where}.pattern')
        authority = _expect_string(item.get('authority'), f'{where}.authority')
        if not SLUG.fullmatch(authority):
            raise ConfigError(f'{where}.authority must contain only letters, numbers, ., _, or -')
        if pattern in seen_patterns:
            previous = seen_patterns[pattern]
            if previous != authority:
                raise ConfigError(
                    f'{where}.pattern duplicates {pattern!r} with conflicting authority '
                    f'{previous!r} vs {authority!r}'
                )
            raise ConfigError(f'{where}.pattern duplicates authority pattern {pattern!r}')
        seen_patterns[pattern] = authority
        authorities.append(AuthorityRule(pattern, authority))

    raw_truths = _expect_list(root.get('truths', []), 'truths')
    if not raw_truths:
        raise ConfigError('config must contain at least one truth rule')

    truths: list[TruthRule] = []
    rule_ids: set[str] = set()
    for index, raw in enumerate(raw_truths):
        where = f'truths[{index}]'
        item = _expect_dict(raw, where)
        _reject_unknown(item, {'id', 'description', 'canonical', 'stale_patterns', 'severity'}, where)
        rule_id = _expect_string(item.get('id'), f'{where}.id')
        if not SLUG.fullmatch(rule_id):
            raise ConfigError(f'{where}.id must contain only letters, numbers, ., _, or -')
        if rule_id in rule_ids:
            raise ConfigError(f'duplicate truth rule id: {rule_id}')
        rule_ids.add(rule_id)

        description = _expect_string(item.get('description', rule_id), f'{where}.description')
        canonical = _expect_string(item.get('canonical'), f'{where}.canonical')
        severity = item.get('severity', 10)
        if isinstance(severity, bool) or not isinstance(severity, int) or severity < 0:
            raise ConfigError(f'{where}.severity must be a non-negative integer')

        raw_patterns = _expect_list(item.get('stale_patterns', []), f'{where}.stale_patterns')
        if not raw_patterns:
            raise ConfigError(f'{where}.stale_patterns must contain at least one pattern')
        patterns = tuple(_parse_pattern(p, f'{where}.stale_patterns[{i}]') for i, p in enumerate(raw_patterns))
        keys = [(p.value.casefold(), p.match) for p in patterns]
        if len(keys) != len(set(keys)):
            raise ConfigError(f'{where}.stale_patterns contains a duplicate pattern/match pair')
        truths.append(TruthRule(rule_id, description, canonical, patterns, severity))

    suppressions: list[SuppressionRule] = []
    for index, raw in enumerate(_expect_list(root.get('suppressions', []), 'suppressions')):
        where = f'suppressions[{index}]'
        item = _expect_dict(raw, where)
        _reject_unknown(item, {'path', 'rule_id', 'reason'}, where)
        path_pattern = _expect_string(item.get('path'), f'{where}.path')
        rule_id = _expect_string(item.get('rule_id'), f'{where}.rule_id')
        reason = _expect_string(item.get('reason'), f'{where}.reason')
        if rule_id not in rule_ids:
            raise ConfigError(f'{where}.rule_id references unknown truth rule: {rule_id}')
        suppressions.append(SuppressionRule(path_pattern, rule_id, reason))

    return authorities, truths, suppressions


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
        if any(part in DEFAULT_EXCLUDES for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in DEFAULT_EXTENSIONS:
            yield path


def _search(pattern: PatternSpec, line: str) -> str | None:
    if pattern.match == 'substring':
        index = line.casefold().find(pattern.value.casefold())
        return None if index < 0 else line[index:index + len(pattern.value)]
    if pattern.match == 'phrase':
        match = re.search(rf'(?<!\w){re.escape(pattern.value)}(?!\w)', line, re.IGNORECASE)
        return match.group(0) if match else None
    match = re.search(pattern.value, line, re.IGNORECASE)
    return match.group(0) if match else None


def _inline_suppression(line: str, previous: str | None, rule_id: str) -> tuple[str, str] | None:
    for source, candidate in (('inline:same-line', line), ('inline:previous-line', previous)):
        if not candidate:
            continue
        if any(m.group(1).casefold() == rule_id.casefold() for m in INLINE_MARKER.finditer(candidate)):
            return source, 'inline drift-ignore marker'
    return None


def _config_suppression(path: str, rule_id: str, rules: Sequence[SuppressionRule]) -> tuple[str, str] | None:
    for rule in rules:
        if rule.rule_id == rule_id and fnmatch.fnmatch(path, rule.path):
            return f'config:{rule.path}', rule.reason
    return None


def _context(lines: list[str], index: int, count: int) -> tuple[tuple[tuple[int, str], ...], tuple[tuple[int, str], ...]]:
    if count <= 0:
        return (), ()
    before = tuple((i + 1, lines[i]) for i in range(max(0, index - count), index))
    after = tuple((i + 1, lines[i]) for i in range(index + 1, min(len(lines), index + count + 1)))
    return before, after


def scan(
    root: Path,
    authority_rules: list[AuthorityRule],
    truths: list[TruthRule],
    suppressions: list[SuppressionRule] | None = None,
    *,
    door: str | None = None,
    included_paths: set[str] | None = None,
    context: int = 1,
) -> ScanResult:
    findings: list[Finding] = []
    suppressed_findings: list[Finding] = []
    file_count = 0
    door = door.replace('\\', '/') if door else None
    included = {p.replace('\\', '/') for p in included_paths} if included_paths is not None else None
    suppressions = suppressions or []

    for path in iter_text_files(root):
        rel = path.relative_to(root).as_posix()
        if door and rel != door:
            continue
        if included is not None and rel not in included:
            continue
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except UnicodeDecodeError:
            continue
        file_count += 1
        authority = classify_authority(rel, authority_rules)

        for index, line in enumerate(lines):
            previous = lines[index - 1] if index else None
            before, after = _context(lines, index, context)
            for truth in truths:
                for pattern in truth.stale_patterns:
                    matched = _search(pattern, line)
                    if matched is None:
                        continue
                    historical = authority in HISTORICAL_AUTHORITIES
                    kind = 'harmless_ghost' if historical else 'current_drift'
                    score = 0 if historical else truth.severity
                    suppression = _inline_suppression(line, previous, truth.rule_id)
                    if suppression is None:
                        suppression = _config_suppression(rel, truth.rule_id, suppressions)
                    finding = Finding(
                        rel, index + 1, line.strip(), truth.rule_id, truth.description,
                        truth.canonical, matched, authority,
                        'suppressed' if suppression else kind,
                        0 if suppression else score, before, after,
                        suppression[0] if suppression else None,
                        suppression[1] if suppression else None,
                    )
                    (suppressed_findings if suppression else findings).append(finding)

    return ScanResult(tuple(findings), tuple(suppressed_findings), file_count)


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
