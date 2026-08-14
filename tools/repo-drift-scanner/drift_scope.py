from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExcludeRule:
    pattern: str
    source: str
    reason: str
    exact: bool = False

    def matches(self, rel_path: str) -> bool:
        normalized = rel_path.replace('\\', '/')
        if self.exact:
            return normalized == self.pattern
        return fnmatch.fnmatch(normalized, self.pattern)


@dataclass(frozen=True)
class ScanBoundary:
    rules: tuple[ExcludeRule, ...] = ()

    def match(self, rel_path: str) -> ExcludeRule | None:
        for rule in self.rules:
            if rule.matches(rel_path):
                return rule
        return None

    def excludes(self, rel_path: str) -> bool:
        return self.match(rel_path) is not None


def normalize_exclude_pattern(raw: str) -> str:
    value = raw.strip().replace('\\', '/')
    while value.startswith('./'):
        value = value[2:]
    if not value:
        raise ValueError('exclude pattern must not be empty')
    if value.startswith('/'):
        raise ValueError('exclude pattern must be repository-relative')
    parts = [part for part in value.split('/') if part]
    if '..' in parts:
        raise ValueError('exclude pattern must not escape the repository root')
    return value


def _relative_if_inside(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def build_boundary(
    root: Path,
    *,
    config_path: Path,
    output_path: Path | None = None,
    configured_patterns: list[str] | tuple[str, ...] = (),
    cli_patterns: list[str] | tuple[str, ...] = (),
) -> ScanBoundary:
    rules: list[ExcludeRule] = []

    config_rel = _relative_if_inside(root, config_path)
    if config_rel is not None:
        rules.append(ExcludeRule(
            config_rel, 'auto:config', 'active scanner configuration', exact=True
        ))

    output_rel = _relative_if_inside(root, output_path)
    if output_rel is not None:
        rules.append(ExcludeRule(
            output_rel, 'auto:output', 'active scanner report output', exact=True
        ))

    seen: set[tuple[str, str]] = set()
    for raw in configured_patterns:
        pattern = normalize_exclude_pattern(raw)
        key = ('config', pattern)
        if key not in seen:
            seen.add(key)
            rules.append(ExcludeRule(
                pattern, 'config:exclude_paths', 'configured evidence-domain exclusion'
            ))

    for raw in cli_patterns:
        pattern = normalize_exclude_pattern(raw)
        key = ('cli', pattern)
        if key not in seen:
            seen.add(key)
            rules.append(ExcludeRule(
                pattern, 'cli:--exclude', 'command-line evidence-domain exclusion'
            ))

    return ScanBoundary(tuple(rules))
