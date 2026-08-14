#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from drift_contracts import (
    ContractEvaluationError, ContractFinding, ContractResult,
    evaluate_contracts, load_contracts,
)
from drift_core import (
    AuthorityRule, ConfigError, Finding, PatternSpec, ScanResult,
    SuppressionRule, TruthRule, classify_authority, haunting_label,
    iter_text_files, load_config, load_exclude_paths, scan,
)
from drift_coverage import analyze_coverage, decorate_report
from drift_git import GitError, changed_only_paths, changed_since_paths
from drift_report import render_json, render_markdown, render_text
from drift_scope import build_boundary

VERSION = '0.3.2'


class DriftArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(3, f'{self.prog}: error: {message}\n')


def build_parser() -> argparse.ArgumentParser:
    parser = DriftArgumentParser(
        description='Find stale statements and validate deterministic repository contracts.'
    )
    parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
    parser.add_argument('root', type=Path, help='Repository or directory to inspect')
    parser.add_argument(
        '--config', type=Path, required=True,
        help='JSON file containing authority, truth, suppression, exclusion, and optional contract rules',
    )
    parser.add_argument('--door', help='Inspect one relative file path instead of the whole tree')
    parser.add_argument(
        '--exclude', action='append', default=[], metavar='GLOB',
        help='Exclude a repository-relative path/glob from this scan; may be repeated',
    )
    parser.add_argument(
        '--context', type=int, default=1,
        help='Context lines before/after each text finding (default: 1)',
    )
    parser.add_argument(
        '--report', choices=('text', 'json', 'markdown'), default='text',
        help='Output format (default: text)',
    )
    parser.add_argument('--json', action='store_true', help='Backward-compatible alias for --report json')
    parser.add_argument('--output', type=Path, help='Write the report to this file instead of stdout')
    parser.add_argument(
        '--show-suppressed', action='store_true',
        help='Include suppressed findings in text/Markdown reports',
    )
    parser.add_argument(
        '--contract-baseline', metavar='REF',
        help='Git ref used by append-only contracts. If omitted, --changed-since REF is reused; otherwise append-only contracts emit REVIEW.',
    )
    parser.add_argument(
        '--no-contracts', action='store_true',
        help='Run only text drift checks plus coverage accounting; skip configured contract evaluation',
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--changed-only', action='store_true',
        help='Scan tracked working-tree changes plus untracked files',
    )
    group.add_argument(
        '--changed-since', metavar='REF',
        help='Scan files changed between REF and HEAD',
    )
    return parser


def _coverage_findings(coverage) -> tuple[ContractFinding, ...]:
    undecodable = set(coverage.undecodable_supported)
    findings = []
    for path in coverage.high_value_ignored:
        if path in undecodable:
            message = 'high-value repository surface is supported by filename/type but could not be decoded as UTF-8'
        else:
            message = 'high-value repository surface is not scanned by the current text-format allowlist'
        findings.append(
            ContractFinding(
                'source-coverage', 'coverage', 'High-value source coverage', 'review',
                path, message,
                {'scope': coverage.scope, 'ignored_by_type': dict(coverage.ignored_by_type)},
                None,
                'A clean scan should not silently imply that an important README/state/roadmap-like surface was inspected when it was not.',
            )
        )
    return tuple(findings)


def _filtered_scan_paths(root: Path, scope_paths: set[str] | None, boundary) -> set[str]:
    supported = {path.relative_to(root).as_posix() for path in iter_text_files(root)}
    if scope_paths is not None:
        normalized = {p.replace('\\', '/') for p in scope_paths}
        supported.intersection_update(normalized)
    return {rel for rel in supported if not boundary.excludes(rel)}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.context < 0:
        parser.error('--context must be zero or greater')
    if args.json and args.report != 'text':
        parser.error('--json cannot be combined with --report')
    report = 'json' if args.json else args.report

    root = args.root.resolve()
    if not root.is_dir():
        print(f'ERROR: root is not a directory: {root}', file=sys.stderr)
        return 3

    config_path = args.config.resolve()
    output_path = args.output.resolve() if args.output else None

    try:
        configured_excludes = load_exclude_paths(config_path)
        boundary = build_boundary(
            root,
            config_path=config_path,
            output_path=output_path,
            configured_patterns=configured_excludes,
            cli_patterns=args.exclude,
        )

        authorities, truths, suppressions = load_config(config_path)
        scope_paths = None
        if args.changed_only:
            scope_paths = changed_only_paths(root)
        elif args.changed_since:
            scope_paths = changed_since_paths(root, args.changed_since)

        included = _filtered_scan_paths(root, scope_paths, boundary)
        result = scan(
            root, authorities, truths, suppressions,
            door=args.door, included_paths=included, context=args.context,
        )

        contract_result = ContractResult(())
        if not args.no_contracts:
            contracts = load_contracts(config_path)
            baseline = args.contract_baseline or args.changed_since
            contract_result = evaluate_contracts(
                root, authorities, contracts, baseline=baseline, boundary=boundary,
            )

        coverage = analyze_coverage(
            root,
            door=args.door,
            included_paths=scope_paths,
            boundary=boundary,
        )
        contract_result = ContractResult(
            contract_result.findings + _coverage_findings(coverage)
        )
    except (ConfigError, GitError, ContractEvaluationError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 3

    if report == 'json':
        rendered = render_json(result, root, contract_result=contract_result)
    elif report == 'markdown':
        rendered = render_markdown(result, contract_result=contract_result, show_suppressed=args.show_suppressed)
    else:
        rendered = render_text(result, contract_result=contract_result, show_suppressed=args.show_suppressed) + '\n'

    rendered = decorate_report(rendered, report, coverage)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding='utf-8')
    else:
        sys.stdout.write(rendered)

    blocking = bool(result.drift or contract_result.violations)
    return 2 if blocking else 0


if __name__ == '__main__':
    raise SystemExit(main())
