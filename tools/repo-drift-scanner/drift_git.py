from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def _run_git(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ['git', *args], cwd=root, check=False,
            capture_output=True, text=True,
        )
    except FileNotFoundError as exc:
        raise GitError('git executable was not found') from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or 'unknown git error'
        raise GitError(detail)
    return completed.stdout


def _ensure_repo(root: Path) -> None:
    if _run_git(root, 'rev-parse', '--is-inside-work-tree').strip().lower() != 'true':
        raise GitError(f'not a Git work tree: {root}')


def changed_only_paths(root: Path) -> set[str]:
    _ensure_repo(root)
    tracked = _run_git(root, 'diff', '--name-only', 'HEAD').splitlines()
    untracked = _run_git(root, 'ls-files', '--others', '--exclude-standard').splitlines()
    return {p.replace('\\', '/') for p in [*tracked, *untracked] if p.strip()}


def changed_since_paths(root: Path, ref: str) -> set[str]:
    _ensure_repo(root)
    output = _run_git(root, 'diff', '--name-only', f'{ref}...HEAD')
    return {p.replace('\\', '/') for p in output.splitlines() if p.strip()}
