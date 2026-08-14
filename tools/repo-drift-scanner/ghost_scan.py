#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from drift_core import (
    AuthorityRule, ConfigError, Finding, PatternSpec, ScanResult,
    SuppressionRule, TruthRule, classify_authority, haunting_label,
    load_config, scan,
)
from drift_git import GitError, changed_only_paths, changed_since_paths
from drift_report import render_json, render_markdown, render_text


class DriftArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(3, f'{self.prog}: error: {message}\n')


def build_parser() -> argparse.ArgumentParser:
    parser = DriftArgumentParser(description='Find stale statements that conflict with declared current truth.')
    parser.add_argument('root', type=Path, help='Repository or directory to inspect')
    parser.add_argument('--config', type=Path, required=True, help='JSON file containing authority, truth, and suppression rules')
    parser.add_argument('--door', help='Inspect one relative file path instead of the whole tree')
    parser.add_argument('--context', type=int, default=1, help='Context lines before/after each finding (default: 1)')
    parser.add_argument('--report', choices=('text', 'json', 'markdown'), default='text', help='Output format (default: text)')
    parser.add_argument('--json', action='store_true', help='Backward-compatible alias for --report json')
    parser.add_argument('--output', type=Path, help='Write the report to this file instead of stdout')
    parser.add_argument('--show-suppressed', action='store_true', help='Include suppressed findings in text/Markdown reports')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--changed-only', action='store_true', help='Scan tracked working-tree changes plus untracked files')
    group.add_argument('--changed-since', metavar='REF', help='Scan files changed between REF and HEAD')
    return parser


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

    try:
        authorities, truths, suppressions = load_config(args.config)
        included = None
        if args.changed_only:
            included = changed_only_paths(root)
        elif args.changed_since:
            included = changed_since_paths(root, args.changed_since)
        result = scan(
            root, authorities, truths, suppressions,
            door=args.door, included_paths=included, context=args.context,
        )
    except (ConfigError, GitError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 3

    if report == 'json':
        rendered = render_json(result, root)
    elif report == 'markdown':
        rendered = render_markdown(result, show_suppressed=args.show_suppressed)
    else:
        rendered = render_text(result, show_suppressed=args.show_suppressed) + '\n'

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding='utf-8')
    else:
        sys.stdout.write(rendered)
    return 2 if result.drift else 0


if __name__ == '__main__':
    raise SystemExit(main())
