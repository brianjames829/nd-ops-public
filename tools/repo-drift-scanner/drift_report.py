from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Sequence

from drift_contracts import ContractFinding, ContractResult
from drift_core import Finding, ScanResult, haunting_label


def _by_rule(items: Sequence[Finding]) -> Counter:
    return Counter(f.rule_id for f in items)


def _by_authority(items: Sequence[Finding]) -> Counter:
    return Counter(f.authority for f in items)


def _by_contract(items: Sequence[ContractFinding]) -> Counter:
    return Counter(f.contract_type for f in items)


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


def _append_provenance(out: list[str], f: Finding) -> None:
    if f.canonical_source:
        out.append(f'Source:      {f.canonical_source}')
    if f.introduced:
        out.append(f'Introduced:  {f.introduced}')
    if f.rule_reason:
        out.append(f'Why:         {f.rule_reason}')


def _contract_text(f: ContractFinding) -> list[str]:
    out = [
        '',
        '──────────────────────────────────────────',
        '⛔ CONTRACT VIOLATION' if f.level == 'violation' else '◇ REVIEW SIGNAL',
        '',
        f'{f.path}',
        f'Contract:   {f.description} [{f.contract_id}]',
        f'Type:       {f.contract_type}',
        f'Level:      {f.level.upper()}',
        f'Finding:    {f.message}',
    ]
    if f.source:
        out.append(f'Source:     {f.source}')
    if f.reason:
        out.append(f'Why:        {f.reason}')
    if f.details:
        out.append('Details:')
        for key, value in sorted(f.details.items()):
            out.append(f'  {key}: {value}')
    return out


def render_text(
    result: ScanResult,
    *,
    contract_result: ContractResult | None = None,
    show_suppressed: bool = False,
) -> str:
    contract_result = contract_result or ContractResult(())
    out = [
        '╔══════════════════════════════════════════╗',
        '║       THE ARCHIVE REMEMBERS TOO MUCH     ║',
        '╚══════════════════════════════════════════╝', '',
        f'Inspecting {result.file_count} text files...', '',
        f'CURRENT DRIFT        {len(result.drift)}',
        f'REVIEW SIGNALS       {len(result.reviews) + len(contract_result.reviews)}',
        f'CONTRACT VIOLATIONS  {len(contract_result.violations)}',
        f'HARMLESS GHOSTS      {len(result.ghosts)}',
        f'SUPPRESSED           {len(result.suppressed)}',
        f'HAUNTING SCORE       {result.haunting_score}  [{haunting_label(result.haunting_score)}]',
    ]
    out.extend(_counter('BY RULE', _by_rule(result.findings)))
    out.extend(_counter('BY AUTHORITY', _by_authority(result.findings)))
    out.extend(_counter('BY CONTRACT TYPE', _by_contract(contract_result.findings)))

    visible = list(result.findings) + (list(result.suppressed) if show_suppressed else [])
    for f in visible:
        out.extend(['', '──────────────────────────────────────────'])
        if f.kind == 'current_drift':
            out.append('⚠ GHOST FOUND')
        elif f.kind == 'harmless_ghost':
            out.append('👻 HISTORICAL ECHO')
        elif f.kind == 'review':
            out.append('◇ REVIEW SIGNAL')
        else:
            out.append('⊘ SUPPRESSED ECHO')
        out.extend([
            '', f'{f.path}:{f.line}', *_context_lines(f), '',
            f'Rule:       {f.description} [{f.rule_id}]',
            f'Matched:    {f.matched}', f'Authority:  {f.authority}',
            f'Canonical:  {f.canonical}',
        ])
        _append_provenance(out, f)
        if f.kind == 'current_drift':
            out.append('Verdict:    CURRENT DRIFT — correction/review required')
        elif f.kind == 'harmless_ghost':
            out.append('Verdict:    HARMLESS GHOST — preserve history')
        elif f.kind == 'review':
            out.extend([
                'Verdict:    REVIEW — deterministic signal, not a failing violation',
                f'Source:     {f.suppression_source}',
                f'Reason:     {f.suppression_reason}',
            ])
        else:
            out.extend([f'Suppressed: {f.suppression_source}', f'Reason:     {f.suppression_reason}'])

    for f in contract_result.findings:
        out.extend(_contract_text(f))

    out.extend(['', '──────────────────────────────────────────'])
    blocking = len(result.drift) + len(contract_result.violations)
    if blocking:
        out.append(f'The archive has spoken. {blocking} blocking correction(s) deserve attention.')
    else:
        out.append('The archive is quiet. Suspiciously quiet.')
    if result.reviews or contract_result.reviews:
        out.append(
            f'{len(result.reviews) + len(contract_result.reviews)} review signal(s) need judgment but do not fail the scan.'
        )
    if result.ghosts:
        out.append(f'{len(result.ghosts)} historical ghost(s) may remain undisturbed.')
    if result.suppressed:
        out.append(f'{len(result.suppressed)} finding(s) were intentionally suppressed.')
    return '\n'.join(out)


def _md_context(f: Finding) -> str:
    return '\n'.join(['```text', *_context_lines(f), '```'])


def render_markdown(
    result: ScanResult,
    *,
    contract_result: ContractResult | None = None,
    show_suppressed: bool = False,
) -> str:
    contract_result = contract_result or ContractResult(())
    lines = [
        '# Repository Drift Report', '',
        f'- **Files scanned:** {result.file_count}',
        f'- **Current drift:** {len(result.drift)}',
        f'- **Contract violations:** {len(contract_result.violations)}',
        f'- **Review signals:** {len(result.reviews) + len(contract_result.reviews)}',
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
    lines.extend(['', '## Summary by contract type', '', '| Contract type | Findings |', '|---|---:|'])
    lines.extend(f'| `{k}` | {v} |' for k, v in sorted(_by_contract(contract_result.findings).items()))
    if not contract_result.findings:
        lines.append('| _none_ | 0 |')

    lines.extend(['', '## Current drift', ''])
    if not result.drift:
        lines.append('_No current drift found._')
    for f in result.drift:
        lines.extend([
            f'### `{f.path}:{f.line}`', '', _md_context(f), '',
            f'- **Rule:** {f.description} (`{f.rule_id}`)',
            f'- **Matched:** `{f.matched}`', f'- **Authority:** `{f.authority}`',
            f'- **Canonical:** {f.canonical}',
        ])
        if f.canonical_source:
            lines.append(f'- **Canonical source:** `{f.canonical_source}`')
        if f.introduced:
            lines.append(f'- **Introduced:** {f.introduced}')
        if f.rule_reason:
            lines.append(f'- **Reason:** {f.rule_reason}')
        lines.extend(['- **Verdict:** CURRENT DRIFT — correction/review required', ''])

    lines.extend(['## Contract violations', ''])
    if not contract_result.violations:
        lines.append('_No contract violations found._')
    for f in contract_result.violations:
        lines.extend([
            f'### `{f.path}`', '',
            f'- **Contract:** {f.description} (`{f.contract_id}`)',
            f'- **Type:** `{f.contract_type}`',
            f'- **Finding:** {f.message}',
        ])
        if f.source:
            lines.append(f'- **Source:** `{f.source}`')
        if f.reason:
            lines.append(f'- **Reason:** {f.reason}')
        if f.details:
            lines.extend(['', '```json', json.dumps(f.details, indent=2, ensure_ascii=False), '```'])
        lines.append('')

    reviews = list(result.reviews)
    contract_reviews = list(contract_result.reviews)
    lines.extend(['## Review signals', ''])
    if not reviews and not contract_reviews:
        lines.append('_No review signals found._')
    for f in reviews:
        lines.extend([
            f'### `{f.path}:{f.line}`', '', _md_context(f), '',
            f'- **Rule:** {f.description} (`{f.rule_id}`)',
            f'- **Finding:** suppression expired; verify whether the exception is still intentional',
            f'- **Reason:** {f.suppression_reason}', '',
        ])
    for f in contract_reviews:
        lines.extend([
            f'### `{f.path}`', '',
            f'- **Contract:** {f.description} (`{f.contract_id}`)',
            f'- **Type:** `{f.contract_type}`',
            f'- **Finding:** {f.message}', '',
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
        'canonical_source': f.canonical_source,
        'introduced': f.introduced,
        'rule_reason': f.rule_reason,
    }


def _contract_dict(f: ContractFinding) -> dict:
    return {
        'contract_id': f.contract_id,
        'contract_type': f.contract_type,
        'description': f.description,
        'level': f.level,
        'path': f.path,
        'message': f.message,
        'details': f.details,
        'source': f.source,
        'reason': f.reason,
    }


def render_json(
    result: ScanResult,
    root: Path,
    *,
    contract_result: ContractResult | None = None,
) -> str:
    contract_result = contract_result or ContractResult(())
    payload = {
        'root': str(root), 'file_count': result.file_count,
        'current_drift_count': len(result.drift),
        'contract_violation_count': len(contract_result.violations),
        'review_count': len(result.reviews) + len(contract_result.reviews),
        'historical_ghost_count': len(result.ghosts),
        'suppressed_count': len(result.suppressed),
        'haunting_score': result.haunting_score,
        'haunting_label': haunting_label(result.haunting_score),
        'by_rule': dict(sorted(_by_rule(result.findings).items())),
        'by_authority': dict(sorted(_by_authority(result.findings).items())),
        'by_contract_type': dict(sorted(_by_contract(contract_result.findings).items())),
        'findings': [_finding_dict(f) for f in result.findings],
        'suppressed_findings': [_finding_dict(f) for f in result.suppressed],
        'contract_findings': [_contract_dict(f) for f in contract_result.findings],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + '\n'
