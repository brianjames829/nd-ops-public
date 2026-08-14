from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Sequence

from drift_core import Finding, ScanResult, haunting_label


def _by_rule(items: Sequence[Finding]) -> Counter:
    return Counter(f.rule_id for f in items)


def _by_authority(items: Sequence[Finding]) -> Counter:
    return Counter(f.authority for f in items)


def _context_lines(f: Finding) -> list[str]:
    lines = [f'{n:>4} | {text}' for n, text in f.context_before]
    lines.append(f'{f.line:>4} > {f.text}')
    lines.extend(f'{n:>4} | {text}' for n, text in f.context_after)
    return lines


def _counter(title: str, counter: Counter) -> list[str]:
    if not counter:
        return []
    width = max(len(str(key)) for key in counter)
    return ['', title, *(f'{str(k):<{width}}  {v}' for k, v in sorted(counter.items()))]


def render_text(result: ScanResult, *, show_suppressed: bool = False) -> str:
    out = [
        '╔══════════════════════════════════════════╗',
        '║       THE ARCHIVE REMEMBERS TOO MUCH     ║',
        '╚══════════════════════════════════════════╝', '',
        f'Inspecting {result.file_count} text files...', '',
        f'CURRENT DRIFT        {len(result.drift)}',
        f'HARMLESS GHOSTS      {len(result.ghosts)}',
        f'SUPPRESSED           {len(result.suppressed)}',
        f'HAUNTING SCORE       {result.haunting_score}  [{haunting_label(result.haunting_score)}]',
    ]
    out.extend(_counter('BY RULE', _by_rule(result.findings)))
    out.extend(_counter('BY AUTHORITY', _by_authority(result.findings)))

    visible = list(result.findings) + (list(result.suppressed) if show_suppressed else [])
    for f in visible:
        out.extend(['', '──────────────────────────────────────────'])
        out.append('⚠ GHOST FOUND' if f.kind == 'current_drift' else '👻 HISTORICAL ECHO' if f.kind == 'harmless_ghost' else '⊘ SUPPRESSED ECHO')
        out.extend(['', f'{f.path}:{f.line}', *_context_lines(f), '',
                    f'Rule:       {f.description} [{f.rule_id}]',
                    f'Matched:    {f.matched}', f'Authority:  {f.authority}',
                    f'Canonical:  {f.canonical}'])
        if f.kind == 'current_drift':
            out.append('Verdict:    CURRENT DRIFT — review recommended')
        elif f.kind == 'harmless_ghost':
            out.append('Verdict:    HARMLESS GHOST — preserve history')
        else:
            out.extend([f'Suppressed: {f.suppression_source}', f'Reason:     {f.suppression_reason}'])

    out.extend(['', '──────────────────────────────────────────'])
    out.append(
        f'The archive has spoken. {len(result.drift)} correction(s) deserve attention.'
        if result.drift else 'The archive is quiet. Suspiciously quiet.'
    )
    if result.ghosts:
        out.append(f'{len(result.ghosts)} historical ghost(s) may remain undisturbed.')
    if result.suppressed:
        out.append(f'{len(result.suppressed)} finding(s) were intentionally suppressed.')
    return '\n'.join(out)


def _md_context(f: Finding) -> str:
    return '\n'.join(['```text', *_context_lines(f), '```'])


def render_markdown(result: ScanResult, *, show_suppressed: bool = False) -> str:
    lines = [
        '# Repository Drift Report', '',
        f'- **Files scanned:** {result.file_count}',
        f'- **Current drift:** {len(result.drift)}',
        f'- **Historical ghosts:** {len(result.ghosts)}',
        f'- **Suppressed:** {len(result.suppressed)}',
        f'- **Haunting score:** {result.haunting_score} ({haunting_label(result.haunting_score)})',
        '', '## Summary by rule', '', '| Rule | Findings |', '|---|---:|',
    ]
    lines.extend(f'| `{k}` | {v} |' for k, v in sorted(_by_rule(result.findings).items()))
    if not result.findings:
        lines.append('| _none_ | 0 |')
    lines.extend(['', '## Summary by authority', '', '| Authority | Findings |', '|---|---:|'])
    lines.extend(f'| `{k}` | {v} |' for k, v in sorted(_by_authority(result.findings).items()))
    if not result.findings:
        lines.append('| _none_ | 0 |')

    lines.extend(['', '## Current drift', ''])
    if not result.drift:
        lines.append('_No current drift found._')
    for f in result.drift:
        lines.extend([
            f'### `{f.path}:{f.line}`', '', _md_context(f), '',
            f'- **Rule:** {f.description} (`{f.rule_id}`)',
            f'- **Matched:** `{f.matched}`', f'- **Authority:** `{f.authority}`',
            f'- **Canonical:** {f.canonical}', '- **Verdict:** CURRENT DRIFT — review recommended', '',
        ])

    lines.extend(['## Historical ghosts', ''])
    if not result.ghosts:
        lines.append('_No historical ghosts found._')
    for f in result.ghosts:
        lines.extend([
            f'### `{f.path}:{f.line}`', '', _md_context(f), '',
            f'- **Rule:** {f.description} (`{f.rule_id}`)',
            f'- **Matched:** `{f.matched}`', f'- **Authority:** `{f.authority}`',
            f'- **Canonical:** {f.canonical}', '- **Verdict:** HARMLESS GHOST — preserve history', '',
        ])

    if show_suppressed:
        lines.extend(['## Suppressed findings', ''])
        if not result.suppressed:
            lines.append('_No suppressed findings._')
        for f in result.suppressed:
            lines.extend([
                f'### `{f.path}:{f.line}`', '', _md_context(f), '',
                f'- **Rule:** {f.description} (`{f.rule_id}`)', f'- **Matched:** `{f.matched}`',
                f'- **Suppression source:** `{f.suppression_source}`', f'- **Reason:** {f.suppression_reason}', '',
            ])
    return '\n'.join(lines).rstrip() + '\n'


def _finding_dict(f: Finding) -> dict:
    return {
        'path': f.path, 'line': f.line, 'text': f.text,
        'rule_id': f.rule_id, 'description': f.description,
        'canonical': f.canonical, 'matched': f.matched,
        'authority': f.authority, 'kind': f.kind, 'score': f.score,
        'context_before': [{'line': n, 'text': t} for n, t in f.context_before],
        'context_after': [{'line': n, 'text': t} for n, t in f.context_after],
        'suppression_source': f.suppression_source,
        'suppression_reason': f.suppression_reason,
    }


def render_json(result: ScanResult, root: Path) -> str:
    payload = {
        'root': str(root), 'file_count': result.file_count,
        'current_drift_count': len(result.drift),
        'historical_ghost_count': len(result.ghosts),
        'suppressed_count': len(result.suppressed),
        'haunting_score': result.haunting_score,
        'haunting_label': haunting_label(result.haunting_score),
        'by_rule': dict(sorted(_by_rule(result.findings).items())),
        'by_authority': dict(sorted(_by_authority(result.findings).items())),
        'findings': [_finding_dict(f) for f in result.findings],
        'suppressed_findings': [_finding_dict(f) for f in result.suppressed],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + '\n'
