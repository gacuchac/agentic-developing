#!/usr/bin/env python3
"""Run one targeted Codex review pass and print Codex's final message."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]  # Developing/: run this script from inside a project
PASSES = ("plan", "answers-ask", "commit", "pr", "alternatives", "principles", "ideas", "judge")
NO_DIFF_PASSES = frozenset({"plan", "ideas", "judge"})
SOL_PASSES = frozenset({"plan", "ideas", "pr"})  # every other pass runs on Luna
REQUIRED = {
    "commit": ("commit", "ask_file", "plan_file"),
    "answers-ask": ("base", "ask_file", "plan_file"),
    "pr": ("base", "ask_file", "plan_file"),
}


def missing_args(pass_name: str, given: dict[str, str | None]) -> list[str]:
    """The options pass_name requires that are missing or empty in given, as --flag names."""
    return [f"--{key.replace('_', '-')}" for key in REQUIRED.get(pass_name, ()) if not given.get(key)]


def git(*args: str) -> str:
    """Run a git command and return stdout."""
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def collect_changes(base: str | None) -> str:
    """Diff of tracked changes against base (default HEAD) plus the content of new untracked files."""
    tracked = git("diff", base or "HEAD")
    untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
    new_files = (f"\n### New file: {p}\n{Path(p).read_text(errors='replace')}" for p in untracked)
    return tracked + "".join(new_files)


def commit_changes(sha: str, base: str | None) -> str:
    """One commit's message and diff, after the one-line log of earlier commits since base (if given)."""
    earlier = git("log", "--oneline", f"{base}..{sha}^") if base else ""
    shown = git("show", "--format=fuller", sha)
    return (f"### Earlier commits on this branch\n{earlier}\n" if earlier else "") + f"### This commit\n{shown}"


def pr_changes(target: str) -> str:
    """The PR's committed changes: diff from where HEAD and target last met to HEAD.

    Target's commits merged into the branch are left out, and so is anything uncommitted or untracked.
    """
    return git("diff", git("merge-base", target, "HEAD").strip(), "HEAD")


def verdict_summary(review: str) -> str:
    """One review as its header, its verdict and each failed criterion, joined into one line."""
    lines = review.splitlines()
    fails = [line.strip() for line in lines[2:] if ": FAIL" in line.split("—")[0]]
    return " ".join(lines[:2] + fails)


def commit_verdicts(folder: Path | None, shas: list[str]) -> str:
    """The latest saved review of each commit in shas, in that order; reviews of other commits are left out."""
    if folder is None:
        return ""
    latest: dict[str, str] = {}
    for path in sorted(folder.glob("review-commit-*.md"), key=lambda p: int(p.stem.rsplit("-", 1)[1])):
        text = path.read_text()
        latest[text.split("base: commit ", 1)[-1].split(" ", 1)[0]] = text
    return "\n".join(verdict_summary(latest[sha]) for sha in shas if sha in latest)


def branch_overview(base: str, folder: Path | None) -> str:
    """What answers-ask sees: every commit's message and file stats since base, and each commit's verdict."""
    log = git("log", "--stat", "--format=fuller", f"{base}..HEAD")
    verdicts = commit_verdicts(folder, git("rev-list", "--reverse", f"{base}..HEAD").split())
    return f"### Commits since {base}\n{log}\n### Per-commit review verdicts\n{verdicts or '(none saved)'}"


def pass_prompt_path(pass_name: str, project: Path) -> Path:
    """The pass prompt: the project's own .claude/review-passes/<pass>.md if it has one, else the workspace's."""
    own = project / ".claude" / "review-passes" / f"{pass_name}.md"
    return own if own.exists() else WORKSPACE / ".claude" / "review-passes" / f"{pass_name}.md"


def project_rules(project: Path) -> str:
    """The workspace CLAUDE.md (coding principles for all projects), then the project's own CLAUDE.md if any."""
    paths = dict.fromkeys([WORKSPACE / "CLAUDE.md", project.resolve() / "CLAUDE.md"])
    return "\n\n".join(text for text in (read_optional(str(p)) for p in paths) if text)


def read_optional(path: str | None) -> str:
    """Return a file's text, or an empty string when no path or no file."""
    return Path(path).read_text() if path and Path(path).exists() else ""


def build_prompt(pass_name: str, ask: str, plan: str, principles: str, changes: str, extra: str) -> str:
    """Assemble the prompt from the pass instructions and whatever context is present."""
    sections = (
        pass_prompt_path(pass_name, Path.cwd()).read_text(),
        f"## Original ask\n{ask}" if ask else "",
        f"## Plan\n{plan}" if plan else "",
        f"## Project principles (CLAUDE.md)\n{principles}" if principles else "",
        f"## Changes under review\n{changes}" if changes else "",
        extra,
    )
    return "\n\n".join(s for s in sections if s)


def context_files(paths: list[str]) -> str:
    """Each extra context file as its own section, headed by its path."""
    return "\n\n".join(f"## {p}\n{read_optional(p)}" for p in paths)


def resolve_model(pass_name: str, override: str | None) -> str:
    """Pick the model: --model, else CODEX_SOL_MODEL for plan, ideas and pr, else CODEX_LUNA_MODEL."""
    env_key = "CODEX_SOL_MODEL" if pass_name in SOL_PASSES else "CODEX_LUNA_MODEL"
    model = override or os.environ.get(env_key, "")
    if not model or model.startswith("["):
        sys.exit(f"Set {env_key} under env in .claude/settings.json to an OpenAI model name.")
    return model


def find_tool(name: str) -> str:
    """Path to a CLI tool on PATH or in the usual Homebrew folders, which VS Code's PATH often lacks; else name."""
    return shutil.which(name, path=f"{os.environ.get('PATH', '')}:/opt/homebrew/bin:/usr/local/bin") or name


def run_codex(prompt: str, model: str) -> tuple[int, str]:
    """Run codex exec read-only with the prompt on stdin; return exit code and final message."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "last_message.md"
        result = subprocess.run(
            [
                find_tool("codex"),
                "exec",
                "--model",
                model,
                "--sandbox",
                "read-only",
                "--output-last-message",
                str(out),
                "-",
            ],
            input=prompt,
            text=True,
            capture_output=True,
        )
        message = out.read_text() if out.exists() else result.stderr
        return result.returncode, message


def output_dir(ask_file: str | None, run_dir: str | None) -> Path | None:
    """Folder that receives the saved output: --run-dir, else the folder holding the ask file, else none."""
    if run_dir:
        return Path(run_dir)
    return Path(ask_file).parent if ask_file else None


def save_output(folder: Path, pass_name: str, model: str, base: str | None, code: int, message: str) -> Path:
    """Write the message to the next free review-<pass>-<n>.md in folder, with a one-line header; return its path."""
    folder.mkdir(parents=True, exist_ok=True)
    n = 1
    while (folder / f"review-{pass_name}-{n}.md").exists():
        n += 1
    path = folder / f"review-{pass_name}-{n}.md"
    header = f"<!-- pass: {pass_name} | model: {model} | base: {base or 'HEAD'} | exit: {code} | {time.strftime('%Y-%m-%d %H:%M:%S')} -->\n"
    path.write_text(header + message)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pass_name", choices=PASSES)
    parser.add_argument("--ask-file")
    parser.add_argument("--plan-file")
    parser.add_argument("--base", help="git ref to diff against (default: HEAD)")
    parser.add_argument("--commit", help="review only this commit (its message and diff) instead of the branch diff")
    parser.add_argument("--run-dir", help="folder for the saved output (default: the ask file's folder)")
    parser.add_argument("--model", help="override the OpenAI model for this run")
    parser.add_argument("--context-file", action="append", default=[], help="extra file to include; repeatable")
    args = parser.parse_args()
    missing = missing_args(args.pass_name, vars(args))
    if missing:
        sys.exit(f"Pass {args.pass_name} needs {', '.join(missing)}.")
    if args.commit:
        args.commit = git("rev-parse", "--verify", f"{args.commit}^{{commit}}").strip()

    if args.pass_name in NO_DIFF_PASSES:
        changes = ""
    elif args.pass_name == "answers-ask":
        changes = branch_overview(args.base, output_dir(args.ask_file, args.run_dir))
    elif args.pass_name == "pr":
        changes = pr_changes(args.base)
    elif args.commit:
        changes = commit_changes(args.commit, args.base)
    else:
        changes = collect_changes(args.base)
    principles = project_rules(Path.cwd()) if args.pass_name == "principles" else ""
    prompt = build_prompt(
        args.pass_name,
        read_optional(args.ask_file),
        read_optional(args.plan_file),
        principles,
        changes,
        context_files(args.context_file),
    )
    model = resolve_model(args.pass_name, args.model)
    code, message = run_codex(prompt, model)
    folder = output_dir(args.ask_file, args.run_dir)
    label = f"commit {args.commit}" if args.commit else args.base
    if folder is not None:
        print(f"saved: {save_output(folder, args.pass_name, model, label, code, message)}", file=sys.stderr)
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
