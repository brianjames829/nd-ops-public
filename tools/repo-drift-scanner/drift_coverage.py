from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from drift_core import (
    DEFAULT_EXCLUDES,
    DEFAULT_EXTENSIONS,
    DEFAULT_TEXT_FILENAMES,
)

# Broad enough to expose meaningful source-coverage gaps without treating images,
# archives, fonts, or other obvious binary assets as "ignored text".
TEXT_CANDIDATE_EXTENSIONS = {
    '.adoc', '.asciidoc', '.bash', '.bat', '.c', '.cfg', '.cmd', '.conf',
    '.cpp', '.cs', '.css', '.csv', '.go', '.h', '.hpp', '.html', '.ini',
    '.java', '.js', '.jsx', '.kt', '.lua', '.md', '.markdown', '.org',
    '.php', '.properties', '.ps1', '.py', '.r', '.rb', '.rs', '.rst', '.scala',
    '.sh', '.sql', '.swift', '.tex', '.textile', '.toml', '.ts', '.tsx', '.tsv',
    '.txt', '.wiki', '.xml', '.yaml', '.yml', '.json', '.jsonl',
}
HIGH_VALUE_PREFIXES = {
    'readme', 'changelog', 'security', 'contributing', 'roadmap',
    'architecture', 'current_state', 'current-state', 'status', 'version',
}


@dataclass(frozen=True)
class CoverageResult:
    scope: str
    discovered_count: int
    scanned_count: int
    ignored_count: int
    ignored_by_type: tuple[tuple[str, int], ...]
    high_value_ignored: tuple[str, ...]
    undecodable_supported: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            'scope': self.scope,
            'files_discovered': self.discovered_count,
            'files_scanned': self.scanned_count,
            'files_ignored': self.ignored_count,
            'ignored_by_type': dict(self.ignored_by_type),
            'high_value_ignored': list(self.high_value_ignored),
            'undecodable_supported': list(self.undecodable_supported),
        }


def _excluded(root: Path, path: Path) -> bool:
    return any(part in DEFAULT_EXCLUDES for part in path.relative_to(root).parts)


def _supported(path: Path) -> bool:
    return (
        path.suffix.lower() in DEFAULT_EXTENSIONS
        or (not path.suffix and path.name.upper() in DEFAULT_TEXT_FILENAMES)
    )


def _high_value(path: Path) -> bool:
    name = path.name.casefold()
    if not path.suffix and path.name.upper() in DEFAULT_TEXT_FILENAMES:
        return True
    if path.suffix.lower() not in TEXT_CANDIDATE_EXTENSIONS:
        return False
    return any(
        name == prefix
        or name.startswith(prefix + '.')
        or name.startswith(prefix + '_')
        or name.startswith(prefix + '-')
        for prefix in HIGH_VALUE_PREFIXES
    )


def _candidate(path: Path) -> bool:
    if _supported(path):
        return True
    if path.suffix.lower() in TEXT_CANDIDATE_EXTENSIONS:
        return True
    return _high_value(path)


def _scope_files(
    root: Path,
    *,
    door: str | None,
    included_paths: set[str] | None,
) -> tuple[str, list[Path]]:
    normalized_door = door.replace('\\', '/') if door else None
    normalized_included = (
        {p.replace('\\', '/') for p in included_paths}
        if included_paths is not None
        else None
    )

    if normalized_door is not None:
        if normalized_included is not None and normalized_door not in normalized_included:
            return 'door+filtered', []
        path = root / normalized_door
        if path.is_file() and not _excluded(root, path):
            return 'door', [path]
        return 'door', []

    if normalized_included is not None:
        files = []
        for rel in sorted(normalized_included):
            path = root / rel
            if path.is_file() and not _excluded(root, path):
                files.append(path)
        return 'filtered', files

    return 'full', [
        path
        for path in sorted(root.rglob('*'))
        if path.is_file() and not _excluded(root, path)
    ]


def analyze_coverage(
    root: Path,
    *,
    door: str | None = None,
    included_paths: set[str] | None = None,
) -> CoverageResult:
    scope, raw_files = _scope_files(root, door=door, included_paths=included_paths)
    files = [path for path in raw_files if _candidate(path)]

    ignored = Counter()
    high_value_ignored: list[str] = []
    undecodable_supported: list[str] = []
    scanned = 0

    for path in files:
        rel = path.relative_to(root).as_posix()
        if _supported(path):
            try:
                path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                kind = path.suffix.lower() or '[extensionless]'
                ignored[kind] += 1
                undecodable_supported.append(rel)
                if _high_value(path):
                    high_value_ignored.append(rel)
            else:
                scanned += 1
            continue

        kind = path.suffix.lower() or '[extensionless]'
        ignored[kind] += 1
        if _high_value(path):
            high_value_ignored.append(rel)

    discovered = len(files)
    ignored_count = discovered - scanned
    return CoverageResult(
        scope=scope,
        discovered_count=discovered,
        scanned_count=scanned,
        ignored_count=ignored_count,
        ignored_by_type=tuple(sorted(ignored.items())),
        high_value_ignored=tuple(sorted(set(high_value_ignored))),
        undecodable_supported=tuple(sorted(set(undecodable_supported))),
    )


def decorate_report(rendered: str, report: str, coverage: CoverageResult) -> str:
    if report == 'json':
        payload = json.loads(rendered)
        payload['coverage'] = coverage.to_dict()
        return json.dumps(payload, indent=2, ensure_ascii=False) + '\n'

    if report == 'markdown':
        lines = [
            '',
            '## Coverage',
            '',
            f'- **Scope:** `{coverage.scope}`',
            f'- **Text candidates discovered:** {coverage.discovered_count}',
            f'- **Files scanned:** {coverage.scanned_count}',
            f'- **Candidate files ignored:** {coverage.ignored_count}',
        ]
        if coverage.ignored_by_type:
            lines.extend(['', '### Ignored by type', '', '| Type | Files |', '|---|---:|'])
            lines.extend(f'| `{kind}` | {count} |' for kind, count in coverage.ignored_by_type)
        if coverage.high_value_ignored:
            lines.extend(['', '### High-value ignored surfaces', ''])
            lines.extend(f'- `{path}`' for path in coverage.high_value_ignored)
        if coverage.undecodable_supported:
            lines.extend(['', '### Supported files that were not UTF-8 decodable', ''])
            lines.extend(f'- `{path}`' for path in coverage.undecodable_supported)
        return rendered.rstrip() + '\n' + '\n'.join(lines) + '\n'

    lines = [
        '',
        'COVERAGE',
        f'SCOPE                 {coverage.scope}',
        f'FILES DISCOVERED      {coverage.discovered_count}',
        f'FILES SCANNED         {coverage.scanned_count}',
        f'FILES IGNORED         {coverage.ignored_count}',
    ]
    if coverage.ignored_by_type:
        lines.append('')
        lines.append('IGNORED BY TYPE')
        width = max(len(kind) for kind, _ in coverage.ignored_by_type)
        lines.extend(f'{kind:<{width}}  {count}' for kind, count in coverage.ignored_by_type)
    if coverage.high_value_ignored:
        lines.append('')
        lines.append('HIGH-VALUE IGNORED SURFACES')
        lines.extend(f'  {path}' for path in coverage.high_value_ignored)
    if coverage.undecodable_supported:
        lines.append('')
        lines.append('SUPPORTED BUT UNDECODABLE')
        lines.extend(f'  {path}' for path in coverage.undecodable_supported)
    return rendered.rstrip() + '\n' + '\n'.join(lines)
