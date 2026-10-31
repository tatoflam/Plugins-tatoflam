#!/usr/bin/env python3
"""PostToolUse hook: lint the file Claude just edited and report only what the edit added.

Runs ruff (pyflakes + bugbear + bandit rules), shellcheck and gitleaks on the edited
file. ruff / shellcheck findings are compared with the HEAD version of the same file so
pre-existing debt does not block every edit; gitleaks hits are always reported.

Exit 2 with findings on stderr feeds them back to Claude. Missing tools are skipped.

The same file runs from two places:
  - the dev-standards plugin (local machines), invoked with --plugin
  - a repo copy at .claude/hooks/check-edit.py (Claude Code on the web)
When the repo copy exists, the plugin copy steps aside so findings are not doubled.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_COPY = Path(".claude/hooks/check-edit.py")
MAX_LINES = 20
MAX_BYTES = 2_000_000
RUFF_CONFIG_FILES = ("ruff.toml", ".ruff.toml")


class LinterFailed(Exception):
    pass


def run(cmd: list[str], stdin: str | None = None, cwd: Path | None = None) -> str:
    proc = subprocess.run(  # noqa: S603 — argv list, no shell
        cmd, input=stdin, capture_output=True, text=True, cwd=cwd, timeout=60, check=False
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        # A crashed linter prints nothing on stdout; do not mistake that for a clean file.
        err = proc.stderr.strip().splitlines()
        raise LinterFailed(f"{cmd[0]} exited {proc.returncode}: {err[-1] if err else ''}")
    return proc.stdout


def git_head_text(project: Path, path: Path) -> str | None:
    """The HEAD version of `path`, or None when it is untracked or not in a repo."""
    try:
        rel = path.relative_to(project)
    except ValueError:
        return None
    if not shutil.which("git"):
        return None
    proc = subprocess.run(  # noqa: S603 — argv list, no shell
        ["git", "-C", str(project), "show", f"HEAD:{rel.as_posix()}"],  # noqa: S607
        capture_output=True, text=True, timeout=30, check=False,
    )
    return proc.stdout if proc.returncode == 0 else None


def pre_edit_text(payload: dict, text: str) -> str | None:
    """The file as it was before an Edit, rebuilt by undoing the replacement."""
    if payload.get("tool_name") != "Edit":
        return None
    ti = payload.get("tool_input") or {}
    old, new = ti.get("old_string"), ti.get("new_string")
    if old is None or not new or new not in text:
        return None
    return text.replace(new, old) if ti.get("replace_all") else text.replace(new, old, 1)


def has_ruff_config(project: Path) -> bool:
    if any((project / name).is_file() for name in RUFF_CONFIG_FILES):
        return True
    pyproject = project / "pyproject.toml"
    return pyproject.is_file() and "[tool.ruff" in pyproject.read_text(errors="replace")


def ruff_findings(path: Path, text: str, project: Path) -> list[tuple[int, str, str]]:
    cmd = ["ruff", "check", "--no-cache", "--output-format", "json", "--exit-zero",
           "--stdin-filename", str(path)]
    if not has_ruff_config(project) and (HERE / "ruff.toml").is_file():
        cmd += ["--config", str(HERE / "ruff.toml")]
    out = run([*cmd, "-"], stdin=text, cwd=project)
    return [(f["location"]["row"], f["code"] or "syntax", f["message"])
            for f in json.loads(out or "[]")]


def shell_dialect(path: Path, text: str) -> str | None:
    first = text.split("\n", 1)[0]
    if first.startswith("#!"):
        for sh in ("bash", "zsh", "dash", "ksh", "sh"):
            if sh in first:
                return None if sh == "zsh" else sh  # shellcheck does not speak zsh
        return None
    return "bash" if path.suffix in (".sh", ".bash") else None


def shellcheck_findings(path: Path, text: str) -> list[tuple[int, str, str]]:
    dialect = shell_dialect(path, text)
    if dialect is None:
        return []
    out = run(["shellcheck", "-S", "warning", "-s", dialect, "-f", "json", "-"], stdin=text)
    return [(f["line"], f"SC{f['code']}", f["message"]) for f in json.loads(out or "[]")]


def gitleaks_findings(text: str) -> list[tuple[int, str, str]]:
    out = run(["gitleaks", "stdin", "--no-banner", "--redact", "--report-format", "json",
               "--report-path", "-", "--exit-code", "0"], stdin=text)
    return [(f["StartLine"], f["RuleID"], "possible secret (gitleaks)")
            for f in json.loads(out or "[]")]


def added(new: list[tuple[int, str, str]], new_text: str,
          old: list[tuple[int, str, str]], old_text: str) -> list[tuple[int, str, str]]:
    """Findings in `new` not already present in `old`, matched by (code, line text)."""
    def key(f: tuple[int, str, str], lines: list[str]) -> tuple[str, str]:
        line = lines[f[0] - 1].strip() if 0 < f[0] <= len(lines) else ""
        return f[1], line

    new_lines, old_lines = new_text.splitlines(), old_text.splitlines()
    budget = Counter(key(f, old_lines) for f in old)
    out = []
    for f in new:
        k = key(f, new_lines)
        if budget[k] > 0:
            budget[k] -= 1
        else:
            out.append(f)
    return out


def main() -> int:
    # ensure-tools.sh installs into ~/.local/bin in cloud sessions; hooks may not inherit
    # the PATH it exports.
    os.environ["PATH"] = f"{Path.home() / '.local/bin'}{os.pathsep}{os.environ.get('PATH', '')}"
    payload = json.load(sys.stdin)
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".").resolve()
    if "--plugin" in sys.argv and (project / REPO_COPY).is_file():
        return 0

    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return 0
    path = Path(file_path)
    if not path.is_absolute():
        path = project / path
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        return 0
    try:
        text = path.read_text()
    except (UnicodeDecodeError, OSError):
        return 0
    # Baseline: the pre-edit text for Edit (exact even when another session has uncommitted
    # changes in the same file), HEAD for Write, nothing for new files.
    old_text = pre_edit_text(payload, text)
    if old_text is None:
        old_text = git_head_text(project, path.resolve())

    report: list[str] = []
    linters = []
    if path.suffix in (".py", ".pyi") and shutil.which("ruff"):
        linters.append(lambda t: ruff_findings(path, t, project))
    if shutil.which("shellcheck"):
        linters.append(lambda t: shellcheck_findings(path, t))
    if shutil.which("gitleaks"):
        linters.append(None)
    for lint in linters:
        try:
            if lint is None:  # secrets are reported whether or not they predate the edit
                found = gitleaks_findings(text)
            else:
                found = lint(text)
                if found and old_text is not None:
                    found = added(found, text, lint(old_text), old_text)
        except (LinterFailed, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            report.append(f"{path.name}: linter did not run cleanly — {e}")
            continue
        report += [f"{path.name}:{line}: {code} {msg}" for line, code, msg in found]

    if not report:
        return 0
    shown = report[:MAX_LINES]
    more = len(report) - len(shown)
    print("dev-standards: this edit introduced findings. Fix them, or explain why a finding "
          "is a false positive and suppress it inline with the narrowest code.", file=sys.stderr)
    print("\n".join(shown), file=sys.stderr)
    if more:
        print(f"... and {more} more", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
