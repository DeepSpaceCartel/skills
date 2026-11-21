#!/usr/bin/env python3
"""Compare two outputs of the same build or test step and classify what differs.

Usage: python3 nondeterminism_diff.py A B [--env]

A and B are text files: two logs, two generated files, or two `env` dumps taken on
different machines or runs. Each differing line is classified as a likely source of
non-hermeticity (timestamp, home path, temp path, absolute path, pid or port, random id).
With --env, A and B are read as KEY=VALUE dumps and compared by key.

Exit status: 0 when the files match, 1 when they differ, 2 on usage error.
Standard library only.
"""

import difflib
import re
import sys

PATTERNS = [
    ("timestamp", re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?|\b\d{2}:\d{2}:\d{2}\b|\b1[6-9]\d{8}\b")),
    ("home path", re.compile(r"/(home|Users)/[^/\s]+")),
    ("temp path", re.compile(r"/(tmp|var/folders|private/var)/[^\s]+")),
    ("absolute path", re.compile(r"(?<![\w.])/(usr|opt|root|srv|workspaces?|builds?)/[^\s]*")),
    ("pid or port", re.compile(r"\b(pid|port)[=: ]\d+", re.IGNORECASE)),
    ("random id", re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")),
]

# Environment variables that commonly leak host state into actions or tests.
LEAKY_ENV = {"HOME", "USER", "LOGNAME", "HOSTNAME", "PATH", "TZ", "LANG", "LC_ALL",
             "TMPDIR", "PWD", "PYTHONPATH", "PYTHONHASHSEED", "SOURCE_DATE_EPOCH"}


def classify(line):
    hits = [name for name, rx in PATTERNS if rx.search(line)]
    return hits or ["other"]


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def diff_text(a, b):
    found = []
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        for line in a[i1:i2]:
            found.append(("-", line, classify(line)))
        for line in b[j1:j2]:
            found.append(("+", line, classify(line)))
    return found


def parse_env(lines):
    env = {}
    for line in lines:
        if "=" in line:
            key, _, value = line.partition("=")
            env[key] = value
    return env


def diff_env(a, b):
    ea, eb = parse_env(a), parse_env(b)
    found = []
    for key in sorted(set(ea) | set(eb)):
        if ea.get(key) != eb.get(key):
            kind = "leaky env var" if key in LEAKY_ENV else "env var"
            found.append((key, ea.get(key, "<unset>"), eb.get(key, "<unset>"), kind))
    return found


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 2:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    a, b = read_lines(args[0]), read_lines(args[1])
    if "--env" in argv:
        rows = diff_env(a, b)
        for key, va, vb, kind in rows:
            print(f"[{kind}] {key}: {va!r} -> {vb!r}")
    else:
        rows = diff_text(a, b)
        for sign, line, kinds in rows:
            print(f"{sign} [{', '.join(kinds)}] {line}")
    print(f"{len(rows)} difference(s)", file=sys.stderr)
    return 1 if rows else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
