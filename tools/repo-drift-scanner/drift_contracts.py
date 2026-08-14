from __future__ import annotations

import fnmatch
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from drift_core import (
    ConfigError,
    DEFAULT_EXCLUDES,
    PatternSpec,
    SLUG,
    classify_authority,
    search_pattern,
)

CONTRACT_TYPES = {
    'authority',
    'structured_assertion',
    'lifecycle',
    'current_surface',
    'output_ownership',
    'append_only',
}
LEVELS = {'violation', 'review'}
OPS = {'equals', 'not_equals', 'in', 'not_in', 'exists'}


@dataclass(frozen=True)
class Contract:
    contract_id: str
    contract_type: str
    description: str
    level: str
    source: str | None
    reason: str | None
    spec: dict[str, Any]


@dataclass(frozen=True)
class ContractFinding:
    contract_id: str
    contract_type: str
    description: str
    level: str
    path: str
    message: str
    details: dict[str, Any]
    source: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ContractResult:
    findings: tuple[ContractFinding, ...]

    @property
    def violations(self) -> tuple[ContractFinding, ...]:
        return tuple(f for f in self.findings if f.level == 'violation')

    @property
    def reviews(self) -> tuple[ContractFinding, ...]:
        return tuple(f for f in self.findings if f.level == 'review')


class ContractEvaluationError(RuntimeError):
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


def _load_root(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise ConfigError(f'config file not found: {path}') from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f'config JSON is invalid at line {exc.lineno}, column {exc.colno}: {exc.msg}'
        ) from exc
    if not isinstance(data, dict):
        raise ConfigError('config must be an object')
    return data


def _validate_predicate(raw: object, where: str) -> dict:
    item = _expect_dict(raw, where)
    _reject_unknown(item, {'field', 'op', 'value'}, where)
    field = _expect_string(item.get('field'), f'{where}.field')
    op = item.get('op')
    if not isinstance(op, str) or op not in OPS:
        raise ConfigError(f"{where}.op must be one of: {', '.join(sorted(OPS))}")
    if op != 'exists' and 'value' not in item:
        raise ConfigError(f'{where}.value is required for op {op}')
    return {'field': field, 'op': op, **({'value': item.get('value')} if 'value' in item else {})}


def load_contracts(path: Path) -> list[Contract]:
    root = _load_root(path)
    raw_contracts = root.get('contracts', [])
    if not isinstance(raw_contracts, list):
        raise ConfigError('contracts must be an array')

    contracts: list[Contract] = []
    seen: set[str] = set()

    for index, raw in enumerate(raw_contracts):
        where = f'contracts[{index}]'
        item = _expect_dict(raw, where)
        common = {'id', 'type', 'description', 'level', 'source', 'reason'}
        contract_id = _expect_string(item.get('id'), f'{where}.id')
        if not SLUG.fullmatch(contract_id):
            raise ConfigError(f'{where}.id must contain only letters, numbers, ., _, or -')
        if contract_id in seen:
            raise ConfigError(f'duplicate contract id: {contract_id}')
        seen.add(contract_id)

        contract_type = _expect_string(item.get('type'), f'{where}.type')
        if contract_type not in CONTRACT_TYPES:
            raise ConfigError(
                f"{where}.type must be one of: {', '.join(sorted(CONTRACT_TYPES))}"
            )
        description = _expect_string(item.get('description', contract_id), f'{where}.description')
        level = item.get('level', 'violation')
        if not isinstance(level, str) or level not in LEVELS:
            raise ConfigError(f"{where}.level must be one of: {', '.join(sorted(LEVELS))}")
        source = item.get('source')
        if source is not None:
            source = _expect_string(source, f'{where}.source')
        reason = item.get('reason')
        if reason is not None:
            reason = _expect_string(reason, f'{where}.reason')

        if contract_type == 'authority':
            allowed = common | {'paths', 'must_be', 'require_match'}
            _reject_unknown(item, allowed, where)
            paths = _expect_list(item.get('paths'), f'{where}.paths')
            if not paths:
                raise ConfigError(f'{where}.paths must contain at least one glob')
            paths = [_expect_string(p, f'{where}.paths') for p in paths]
            must_be = _expect_string(item.get('must_be'), f'{where}.must_be')
            spec = {
                'paths': paths,
                'must_be': must_be,
                'require_match': bool(item.get('require_match', True)),
            }

        elif contract_type == 'structured_assertion':
            allowed = common | {'path', 'pointer', 'op', 'value'}
            _reject_unknown(item, allowed, where)
            p = _expect_string(item.get('path'), f'{where}.path')
            pointer = _expect_string(item.get('pointer'), f'{where}.pointer')
            op = _expect_string(item.get('op'), f'{where}.op')
            if op not in OPS:
                raise ConfigError(f"{where}.op must be one of: {', '.join(sorted(OPS))}")
            if op != 'exists' and 'value' not in item:
                raise ConfigError(f'{where}.value is required for op {op}')
            spec = {'path': p, 'pointer': pointer, 'op': op}
            if 'value' in item:
                spec['value'] = item.get('value')

        elif contract_type == 'lifecycle':
            allowed = common | {'path', 'invariants', 'record_id_field'}
            _reject_unknown(item, allowed, where)
            p = _expect_string(item.get('path'), f'{where}.path')
            invariants_raw = _expect_list(item.get('invariants'), f'{where}.invariants')
            if not invariants_raw:
                raise ConfigError(f'{where}.invariants must contain at least one invariant')
            invariants = []
            for i, inv_raw in enumerate(invariants_raw):
                iw = f'{where}.invariants[{i}]'
                inv = _expect_dict(inv_raw, iw)
                _reject_unknown(inv, {'when', 'require', 'message'}, iw)
                when = _validate_predicate(inv.get('when'), f'{iw}.when')
                require = _validate_predicate(inv.get('require'), f'{iw}.require')
                message = inv.get('message')
                if message is not None:
                    message = _expect_string(message, f'{iw}.message')
                invariants.append({'when': when, 'require': require, 'message': message})
            record_id_field = item.get('record_id_field', 'id')
            record_id_field = _expect_string(record_id_field, f'{where}.record_id_field')
            spec = {'path': p, 'invariants': invariants, 'record_id_field': record_id_field}

        elif contract_type == 'current_surface':
            allowed = common | {
                'path', 'must_be_authority', 'required_patterns', 'forbidden_patterns',
                'review_patterns',
            }
            _reject_unknown(item, allowed, where)
            p = _expect_string(item.get('path'), f'{where}.path')
            spec = {'path': p}
            mba = item.get('must_be_authority')
            if mba is not None:
                spec['must_be_authority'] = _expect_string(mba, f'{where}.must_be_authority')
            for key in ('required_patterns', 'forbidden_patterns', 'review_patterns'):
                values = item.get(key, [])
                values = _expect_list(values, f'{where}.{key}')
                spec[key] = [_parse_pattern(v, f'{where}.{key}') for v in values]

        elif contract_type == 'output_ownership':
            allowed = common | {
                'output', 'inspect', 'owners', 'reference', 'require_owner_reference'
            }
            _reject_unknown(item, allowed, where)
            output = _expect_string(item.get('output'), f'{where}.output')
            inspect = _expect_list(item.get('inspect'), f'{where}.inspect')
            owners = _expect_list(item.get('owners'), f'{where}.owners')
            if not inspect:
                raise ConfigError(f'{where}.inspect must contain at least one glob')
            if not owners:
                raise ConfigError(f'{where}.owners must contain at least one glob')
            inspect = [_expect_string(v, f'{where}.inspect') for v in inspect]
            owners = [_expect_string(v, f'{where}.owners') for v in owners]
            reference = item.get('reference', output)
            reference = _expect_string(reference, f'{where}.reference')
            spec = {
                'output': output,
                'inspect': inspect,
                'owners': owners,
                'reference': reference,
                'require_owner_reference': bool(item.get('require_owner_reference', True)),
            }

        else:
            allowed = common | {'path'}
            _reject_unknown(item, allowed, where)
            spec = {'path': _expect_string(item.get('path'), f'{where}.path')}

        contracts.append(
            Contract(contract_id, contract_type, description, level, source, reason, spec)
        )

    return contracts


def _parse_pattern(raw: object, where: str) -> PatternSpec:
    if isinstance(raw, str):
        if not raw.strip():
            raise ConfigError(f'{where} must be a non-empty string')
        return PatternSpec(raw.strip(), 'substring')
    item = _expect_dict(raw, where)
    _reject_unknown(item, {'value', 'match'}, where)
    value = _expect_string(item.get('value'), f'{where}.value')
    mode = item.get('match', 'substring')
    if mode not in {'substring', 'phrase', 'regex'}:
        raise ConfigError(f'{where}.match must be substring, phrase, or regex')
    if mode == 'regex':
        try:
            re.compile(value, re.IGNORECASE)
        except re.error as exc:
            raise ConfigError(f'{where} has invalid regex: {exc}') from exc
    return PatternSpec(value, mode)


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in DEFAULT_EXCLUDES for part in rel_parts):
            continue
        yield path


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _finding(
    contract: Contract,
    path: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    level: str | None = None,
) -> ContractFinding:
    return ContractFinding(
        contract.contract_id,
        contract.contract_type,
        contract.description,
        level or contract.level,
        path,
        message,
        details or {},
        contract.source,
        contract.reason,
    )


_MISSING = object()


def _json_pointer(document: Any, pointer: str) -> Any:
    if pointer == '/':
        return document
    if not pointer.startswith('/'):
        raise ValueError('JSON pointer must start with /')
    current = document
    for raw_part in pointer[1:].split('/'):
        part = raw_part.replace('~1', '/').replace('~0', '~')
        if isinstance(current, dict):
            if part not in current:
                return _MISSING
            current = current[part]
        elif isinstance(current, list):
            try:
                index = int(part)
            except ValueError:
                return _MISSING
            if index < 0 or index >= len(current):
                return _MISSING
            current = current[index]
        else:
            return _MISSING
    return current


def _predicate(record: dict[str, Any], pred: dict[str, Any]) -> bool:
    value = record.get(pred['field'], _MISSING)
    op = pred['op']
    expected = pred.get('value')
    if op == 'exists':
        return (value is not _MISSING) == bool(expected if 'value' in pred else True)
    if value is _MISSING:
        return False
    if op == 'equals':
        return value == expected
    if op == 'not_equals':
        return value != expected
    if op == 'in':
        return value in expected
    if op == 'not_in':
        return value not in expected
    raise AssertionError(op)


def _evaluate_authority(root: Path, contract: Contract, authority_rules) -> list[ContractFinding]:
    findings = []
    matched = []
    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        if _matches_any(rel, contract.spec['paths']):
            matched.append(rel)
            actual = classify_authority(rel, authority_rules)
            expected = contract.spec['must_be']
            if actual != expected:
                findings.append(_finding(
                    contract, rel,
                    f'authority is {actual!r}; expected {expected!r}',
                    details={'actual': actual, 'expected': expected},
                ))
    if contract.spec['require_match'] and not matched:
        findings.append(_finding(
            contract, ','.join(contract.spec['paths']),
            'authority contract matched no files',
            details={'patterns': contract.spec['paths']},
        ))
    return findings


def _evaluate_structured(root: Path, contract: Contract) -> list[ContractFinding]:
    rel = contract.spec['path']
    path = root / rel
    if not path.is_file():
        return [_finding(contract, rel, 'structured assertion target is missing')]
    try:
        document = json.loads(path.read_text(encoding='utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [_finding(contract, rel, f'cannot parse JSON: {exc}')]
    try:
        actual = _json_pointer(document, contract.spec['pointer'])
    except ValueError as exc:
        raise ConfigError(f'contract {contract.contract_id}: {exc}') from exc
    pred = {
        'field': '__value__',
        'op': contract.spec['op'],
        **({'value': contract.spec.get('value')} if 'value' in contract.spec else {}),
    }
    record = {} if actual is _MISSING else {'__value__': actual}
    ok = _predicate(record, pred)
    if ok:
        return []
    shown = '<missing>' if actual is _MISSING else actual
    return [_finding(
        contract, rel,
        f'JSON assertion failed at {contract.spec["pointer"]}',
        details={
            'pointer': contract.spec['pointer'],
            'op': contract.spec['op'],
            'expected': contract.spec.get('value'),
            'actual': shown,
        },
    )]


def _evaluate_lifecycle(root: Path, contract: Contract) -> list[ContractFinding]:
    rel = contract.spec['path']
    path = root / rel
    if not path.is_file():
        return [_finding(contract, rel, 'lifecycle target is missing')]
    findings = []
    for line_no, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        clean = line.strip()
        if not clean:
            continue
        try:
            record = json.loads(clean)
        except json.JSONDecodeError as exc:
            findings.append(_finding(
                contract, rel,
                f'JSONL parse failure at line {line_no}: {exc.msg}',
                details={'line': line_no},
            ))
            continue
        if not isinstance(record, dict):
            findings.append(_finding(
                contract, rel,
                f'JSONL record at line {line_no} is not an object',
                details={'line': line_no},
            ))
            continue
        record_id = record.get(contract.spec['record_id_field'], f'line:{line_no}')
        for inv in contract.spec['invariants']:
            if _predicate(record, inv['when']) and not _predicate(record, inv['require']):
                message = inv['message'] or 'lifecycle invariant failed'
                findings.append(_finding(
                    contract, rel, message,
                    details={
                        'line': line_no,
                        'record_id': record_id,
                        'when': inv['when'],
                        'require': inv['require'],
                    },
                ))
    return findings


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeDecodeError as exc:
        raise ContractEvaluationError(f'cannot decode UTF-8 text: {path}') from exc


def _evaluate_current_surface(root: Path, contract: Contract, authority_rules) -> list[ContractFinding]:
    rel = contract.spec['path']
    path = root / rel
    if not path.is_file():
        return [_finding(contract, rel, 'current surface is missing')]
    findings = []
    text = _read_text(path)

    expected_authority = contract.spec.get('must_be_authority')
    if expected_authority is not None:
        actual = classify_authority(rel, authority_rules)
        if actual != expected_authority:
            findings.append(_finding(
                contract, rel,
                f'current surface authority is {actual!r}; expected {expected_authority!r}',
                details={'actual': actual, 'expected': expected_authority},
            ))

    for pattern in contract.spec.get('required_patterns', []):
        if not any(search_pattern(pattern, line) for line in text.splitlines()):
            findings.append(_finding(
                contract, rel,
                f'required current-surface pattern not found: {pattern.value!r}',
                details={'pattern': pattern.value, 'match': pattern.match},
            ))

    for pattern in contract.spec.get('forbidden_patterns', []):
        for line_no, line in enumerate(text.splitlines(), 1):
            matched = search_pattern(pattern, line)
            if matched:
                findings.append(_finding(
                    contract, rel,
                    f'forbidden current-surface pattern found at line {line_no}',
                    details={
                        'line': line_no, 'matched': matched,
                        'pattern': pattern.value, 'match': pattern.match,
                    },
                ))

    for pattern in contract.spec.get('review_patterns', []):
        for line_no, line in enumerate(text.splitlines(), 1):
            matched = search_pattern(pattern, line)
            if matched:
                findings.append(_finding(
                    contract, rel,
                    f'current surface deserves review at line {line_no}',
                    details={
                        'line': line_no, 'matched': matched,
                        'pattern': pattern.value, 'match': pattern.match,
                    },
                    level='review',
                ))
    return findings


def _evaluate_output_ownership(root: Path, contract: Contract) -> list[ContractFinding]:
    findings = []
    owners_seen = []
    ref = contract.spec['reference']
    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        if not _matches_any(rel, contract.spec['inspect']):
            continue
        try:
            text = _read_text(path)
        except ContractEvaluationError:
            continue
        if ref not in text:
            continue
        if _matches_any(rel, contract.spec['owners']):
            owners_seen.append(rel)
        else:
            findings.append(_finding(
                contract, rel,
                f'reference to protected output {contract.spec["output"]!r} appears outside declared owner',
                details={
                    'output': contract.spec['output'],
                    'reference': ref,
                    'owners': contract.spec['owners'],
                },
            ))
    if contract.spec['require_owner_reference'] and not owners_seen:
        findings.append(_finding(
            contract, contract.spec['output'],
            'no declared owner references the protected output',
            details={'owners': contract.spec['owners'], 'reference': ref},
        ))
    return findings


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ['git', *args], cwd=root, check=False, capture_output=True, text=True
        )
    except FileNotFoundError as exc:
        raise ContractEvaluationError('git executable was not found') from exc


def _baseline_text(root: Path, baseline: str, rel: str) -> tuple[bool, str]:
    exists = _run_git(root, 'cat-file', '-e', f'{baseline}:{rel}')
    if exists.returncode != 0:
        ref_check = _run_git(root, 'rev-parse', '--verify', baseline)
        if ref_check.returncode != 0:
            detail = ref_check.stderr.strip() or f'cannot resolve baseline {baseline}'
            raise ContractEvaluationError(detail)
        return False, ''
    shown = _run_git(root, 'show', f'{baseline}:{rel}')
    if shown.returncode != 0:
        detail = shown.stderr.strip() or f'cannot read {rel} from {baseline}'
        raise ContractEvaluationError(detail)
    return True, shown.stdout


def _evaluate_append_only(
    root: Path,
    contract: Contract,
    baseline: str | None,
) -> list[ContractFinding]:
    rel = contract.spec['path']
    if baseline is None:
        return [_finding(
            contract, rel,
            'append-only contract was not evaluated because no Git baseline was provided',
            details={},
            level='review',
        )]
    current_path = root / rel
    if not current_path.is_file():
        return [_finding(contract, rel, 'append-only target is missing')]
    existed, previous = _baseline_text(root, baseline, rel)
    if not existed:
        return []
    current = _read_text(current_path)
    if current.startswith(previous):
        return []
    common = 0
    for a, b in zip(previous, current):
        if a != b:
            break
        common += 1
    return [_finding(
        contract, rel,
        'existing historical content changed; append-only files may only grow at the end',
        details={
            'baseline': baseline,
            'first_difference_char': common,
            'baseline_length': len(previous),
            'current_length': len(current),
        },
    )]


def evaluate_contracts(
    root: Path,
    authority_rules,
    contracts: list[Contract],
    *,
    baseline: str | None = None,
) -> ContractResult:
    findings: list[ContractFinding] = []
    for contract in contracts:
        if contract.contract_type == 'authority':
            findings.extend(_evaluate_authority(root, contract, authority_rules))
        elif contract.contract_type == 'structured_assertion':
            findings.extend(_evaluate_structured(root, contract))
        elif contract.contract_type == 'lifecycle':
            findings.extend(_evaluate_lifecycle(root, contract))
        elif contract.contract_type == 'current_surface':
            findings.extend(_evaluate_current_surface(root, contract, authority_rules))
        elif contract.contract_type == 'output_ownership':
            findings.extend(_evaluate_output_ownership(root, contract))
        elif contract.contract_type == 'append_only':
            findings.extend(_evaluate_append_only(root, contract, baseline))
        else:
            raise AssertionError(contract.contract_type)
    return ContractResult(tuple(findings))
