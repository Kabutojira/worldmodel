#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess


def run(*cmd: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser(description='Commit and push deterministic WorldModel changes.')
    parser.add_argument('--message', required=True)
    parser.add_argument('--allow-empty', action='store_true')
    args = parser.parse_args()

    status = run('git', 'status', '--short')
    print(status.stdout, end='')
    if status.returncode != 0:
        print(status.stderr, end='')
        return status.returncode
    if not status.stdout.strip() and not args.allow_empty:
        print('refusing empty commit')
        return 1
    add = run('git', 'add', 'AGENTS.md', 'PLAN.md', 'index.md', 'data', 'templates', 'entities', 'reports', 'skills', 'bin', 'docs', 'site')
    if add.returncode != 0:
        print(add.stderr, end='')
        return add.returncode
    commit_cmd = ['git', 'commit', '-m', args.message]
    if args.allow_empty:
        commit_cmd.insert(2, '--allow-empty')
    commit = run(*commit_cmd)
    print(commit.stdout, end='')
    if commit.returncode != 0:
        print(commit.stderr, end='')
        return commit.returncode
    push = run('git', 'push')
    print(push.stdout, end='')
    if push.returncode != 0:
        print(push.stderr, end='')
        return push.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
