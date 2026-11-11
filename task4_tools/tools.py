"""The agent's tool layer for Task 4.

Implements the interface from tool_contract.py: sandboxed tools (list_files,
read_file, search_code, run_tests, run_cli, edit_file) with strict argument
validation, workspace containment, bounded output and isolated subprocesses.
"""

from __future__ import annotations

import copy
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from tool_contract import (
    DEFAULT_TIMEOUT_S,
    MAX_LIST_ENTRIES,
    MAX_OUTPUT_CHARS,
    MAX_READ_LINES,
    MAX_SEARCH_RESULTS,
    ToolRegistryBase,
    ToolResult,
)

_SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git", ".venv", "node_modules"}
_TEST_TARGET_RE = re.compile(r"^tests/[\w\-./]+\.py(?:::[\w.\-\[\]]+)*$")
_MAX_MATCH_LINE = 300
_MAX_FAILING_LISTED = 20
_MAX_TRACEBACKS = 10
_MAX_TRACEBACK_CHARS = 600
_JSON_OVERHEAD = 200


class _ToolError(Exception):
    """Raised by handlers; execute() turns it into ToolResult(ok=False, error=...)."""


def _object_schema(properties: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List files below a directory in the workspace, as workspace-relative paths. "
                "'path' defaults to the workspace root."
            ),
            "parameters": _object_schema(
                {
                    "path": {"type": "string", "description": "Directory to list, relative to the workspace root. Defaults to '.'."},
                    "pattern": {"type": "string", "description": "Optional glob pattern that relative paths must match, e.g. '**/*.py'."},
                },
                [],
            ),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a text file from the workspace with 1-based line numbers. "
                "At most 200 lines per call; use start_line/end_line to page through longer files."
            ),
            "parameters": _object_schema(
                {
                    "path": {"type": "string", "description": "File to read, relative to the workspace root."},
                    "start_line": {"type": "integer", "minimum": 1, "description": "First line to return (1-based)."},
                    "end_line": {"type": "integer", "minimum": 1, "description": "Last line to return (inclusive)."},
                },
                ["path"],
            ),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": (
                "Search the workspace with a regular expression and return 'path:line: text' matches. "
                "Searches at most 200 results; refine the pattern to narrow the search."
            ),
            "parameters": _object_schema(
                {
                    "pattern": {"type": "string", "description": "Python regular expression to search for."},
                    "glob": {"type": "string", "description": "Optional glob restricting which files are searched, e.g. '**/*.py'."},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 200, "description": "Maximum number of matches to return."},
                },
                ["pattern"],
            ),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": (
                "Run the project's pytest suite inside the workspace. Returns a structured summary: "
                "numbers of passed/failed tests, the names of failing tests and short tracebacks."
            ),
            "parameters": _object_schema(
                {
                    "target": {
                        "type": "string",
                        "description": "Optional test target: 'tests/test_x.py' or 'tests/test_x.py::test_name'. Defaults to the whole suite.",
                    },
                },
                [],
            ),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_cli",
            "description": (
                "Run the fixed command 'python -m tinyledger <args>' in the workspace "
                "(e.g. args ['report', 'data/sample.csv', '--month', '2026-03']). "
                "Returns the exit code, stdout and stderr."
            ),
            "parameters": _object_schema(
                {
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Command line arguments for the tinyledger CLI; the first one is the subcommand.",
                    },
                },
                ["args"],
            ),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Replace old_str with new_str in an existing file below src/. "
                "old_str must occur exactly once in the file. Returns the unified diff of the change."
            ),
            "parameters": _object_schema(
                {
                    "path": {"type": "string", "description": "File to edit, relative to the workspace root. Must be below src/."},
                    "old_str": {"type": "string", "description": "Existing text to replace. Must occur exactly once in the file."},
                    "new_str": {"type": "string", "description": "Replacement text."},
                },
                ["path", "old_str", "new_str"],
            ),
        },
    },
]


class ToolRegistry(ToolRegistryBase):
    def __init__(self, workspace: Path, timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        super().__init__(workspace, timeout_s)
        self._handlers: dict[str, Callable[[str], ToolResult]] = {
            "list_files": self._tool_list_files,
            "read_file": self._tool_read_file,
            "search_code": self._tool_search_code,
            "run_tests": self._tool_run_tests,
            "run_cli": self._tool_run_cli,
            "edit_file": self._tool_edit_file,
        }
        self._validators = {
            schema["function"]["name"]: Draft202012Validator(schema["function"]["parameters"])
            for schema in _SCHEMAS
        }

    def schemas(self) -> list[dict]:
        return copy.deepcopy(_SCHEMAS)

    def execute(self, name: str, arguments: str) -> ToolResult:
        try:
            handler = self._handlers.get(name)
            if handler is None:
                known = ", ".join(sorted(self._handlers))
                return ToolResult(ok=False, error=f"unknown tool {name!r}. Available tools: {known}")
            return handler(arguments)
        except _ToolError as exc:
            return ToolResult(ok=False, error=str(exc))
        except Exception as exc:
            return ToolResult(ok=False, error=f"{type(exc).__name__}: {exc}")

    def _validate(self, name: str, arguments: str) -> dict:
        if not isinstance(arguments, str):
            raise _ToolError("arguments must be a JSON string")
        try:
            value = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise _ToolError(f"arguments are not valid JSON ({exc.msg}); resend them as valid JSON") from exc
        if not isinstance(value, dict):
            raise _ToolError(f"arguments must be a JSON object of parameters, got {type(value).__name__}")
        validator = self._validators.get(name)
        if validator is None:
            raise _ToolError(f"unknown tool {name!r}")
        problems = [error.message for error in validator.iter_errors(value)]
        if problems:
            raise _ToolError(f"invalid arguments for {name}: " + "; ".join(problems)[:500])
        return value

    def _safe_path(self, rel: str) -> Path:
        if not isinstance(rel, str) or not rel.strip():
            raise _ToolError("path must be a non-empty string")
        if Path(rel).is_absolute():
            raise _ToolError(f"absolute paths are not allowed: {rel!r}")
        root = self.workspace.resolve()
        target = (self.workspace / rel).resolve()
        if not target.is_relative_to(root):
            raise _ToolError(f"path resolves outside the workspace: {rel!r}")
        return target

    def _iter_files(self, start: Path | None = None):
        workspace_root = self.workspace.resolve()
        walk_root = workspace_root if start is None else start.resolve()
        for dirpath, dirnames, filenames in os.walk(walk_root):
            dirnames[:] = sorted(name for name in dirnames if name not in _SKIP_DIRS)
            for filename in sorted(filenames):
                path = Path(dirpath) / filename
                try:
                    resolved = path.resolve()
                except OSError:
                    continue
                if resolved.is_relative_to(workspace_root) and resolved.is_file():
                    yield resolved

    def _tool_list_files(self, arguments: str) -> ToolResult:
        args = self._validate("list_files", arguments)
        rel_root = args.get("path", ".")
        pattern = args.get("pattern")
        root = self._safe_path(rel_root)
        if not root.is_dir():
            raise _ToolError(f"not a directory: {rel_root!r}")
        workspace_root = self.workspace.resolve()
        entries: list[str] = []
        for path in self._iter_files(root):
            rel = path.relative_to(workspace_root).as_posix()
            if pattern is not None and not fnmatch(rel, pattern):
                continue
            entries.append(rel)
        truncated = len(entries) > MAX_LIST_ENTRIES
        entries = sorted(entries)[:MAX_LIST_ENTRIES]
        return self._bounded(entries, truncated=truncated)

    def _tool_read_file(self, arguments: str) -> ToolResult:
        args = self._validate("read_file", arguments)
        rel = args["path"]
        target = self._safe_path(rel)
        if not target.is_file():
            raise _ToolError(f"not a file: {rel!r}")
        start = args.get("start_line")
        end = args.get("end_line")
        if start is not None:
            start = int(start)
        if end is not None:
            end = int(end)
        if start is not None and end is not None and end < start:
            raise _ToolError(f"end_line ({end}) is before start_line ({start})")
        try:
            with target.open("r", encoding="utf-8", errors="replace", newline="") as handle:
                lines = handle.read().splitlines()
        except OSError as exc:
            raise _ToolError(f"cannot read {rel!r}: {exc}") from exc
        total = len(lines)
        if start is None:
            start = 1
        if start > total:
            raise _ToolError(f"start_line {start} is beyond the end of the file ({total} lines)")
        if end is None or end - start + 1 > MAX_READ_LINES:
            end = start + MAX_READ_LINES - 1
        window = lines[start - 1 : end]
        truncated = end < total
        output = "\n".join(f"{number}: {line}" for number, line in enumerate(window, start=start))
        if truncated:
            output += f"\n(truncated: showing lines {start}-{end} of {total})"
        return self._bounded(output, truncated=truncated)

    def _tool_search_code(self, arguments: str) -> ToolResult:
        args = self._validate("search_code", arguments)
        pattern = args["pattern"]
        glob = args.get("glob")
        max_results = args.get("max_results")
        limit = MAX_SEARCH_RESULTS if max_results is None else min(int(max_results), MAX_SEARCH_RESULTS)
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise _ToolError(f"invalid regular expression: {exc}") from exc
        workspace_root = self.workspace.resolve()
        matches: list[str] = []
        truncated = False
        for path in self._iter_files():
            rel = path.relative_to(workspace_root).as_posix()
            if glob is not None and not fnmatch(rel, glob):
                continue
            try:
                with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
                    text = handle.read()
            except OSError:
                continue
            if "\x00" in text:
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if not regex.search(line):
                    continue
                snippet = line.strip()
                if len(snippet) > _MAX_MATCH_LINE:
                    snippet = snippet[:_MAX_MATCH_LINE] + "..."
                matches.append(f"{rel}:{line_number}: {snippet}")
                if len(matches) > limit:
                    truncated = True
                    break
            if truncated:
                break
        if truncated:
            matches = matches[:limit]
        return self._bounded(matches, truncated=truncated)

    def _tool_run_tests(self, arguments: str) -> ToolResult:
        args = self._validate("run_tests", arguments)
        target = args.get("target")
        pytest_args: list[str] = []
        if target is not None:
            pytest_args.append(self._valid_test_target(target))
        with tempfile.TemporaryDirectory(prefix="tinyledger-junit-") as tmp:
            xml_path = Path(tmp) / "junit.xml"
            command = [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                "--junitxml",
                str(xml_path),
                "-q",
                *pytest_args,
            ]
            try:
                process = subprocess.run(
                    command,
                    cwd=self.workspace,
                    env=self._minimal_env(),
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout_s,
                    shell=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise _ToolError(f"timeout: test run exceeded {self.timeout_s:.0f}s") from exc
            except OSError as exc:
                raise _ToolError(f"could not start pytest: {exc}") from exc
            if not xml_path.is_file():
                tail = (process.stderr or process.stdout or "").strip()[-400:]
                message = f"pytest produced no report (exit code {process.returncode})"
                raise _ToolError(f"{message}: {tail}" if tail else message)
            summary = self._parse_junit(xml_path)
            if summary["total"] == 0 and process.returncode != 0:
                tail = (process.stderr or process.stdout or "").strip()[-400:]
                message = f"pytest ran no tests (exit code {process.returncode})"
                raise _ToolError(f"{message}: {tail}" if tail else message)
        return self._bounded(summary)

    def _tool_run_cli(self, arguments: str) -> ToolResult:
        args = self._validate("run_cli", arguments)
        cli_args = self._valid_cli_args(args["args"])
        command = [sys.executable, "-m", "tinyledger", *cli_args]
        try:
            process = subprocess.run(
                command,
                cwd=self.workspace,
                env=self._minimal_env(),
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_s,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise _ToolError(f"timeout: run_cli exceeded {self.timeout_s:.0f}s") from exc
        except OSError as exc:
            raise _ToolError(f"could not start the tinyledger CLI: {exc}") from exc
        stdout = process.stdout or ""
        stderr = process.stderr or ""
        per_stream = (MAX_OUTPUT_CHARS - _JSON_OVERHEAD) // 2
        truncated = len(stdout) > per_stream or len(stderr) > per_stream
        if len(stdout) > per_stream:
            stdout = stdout[:per_stream] + "\n...(truncated)"
        if len(stderr) > per_stream:
            stderr = stderr[:per_stream] + "\n...(truncated)"
        summary = {"exit_code": process.returncode, "stdout": stdout, "stderr": stderr}
        return self._bounded(summary, truncated=truncated)

    def _valid_cli_args(self, cli_args: list[str]) -> list[str]:
        if not cli_args:
            raise _ToolError("args must contain at least the subcommand (report, balances or settle)")
        if cli_args[0] not in {"report", "balances", "settle"}:
            raise _ToolError(
                f"first argument must be one of 'report', 'balances', 'settle', got {cli_args[0]!r}"
            )
        for arg in cli_args[1:]:
            if Path(arg).is_absolute():
                raise _ToolError(f"absolute paths are not allowed in args: {arg!r}")
            if ".." in Path(arg).parts:
                raise _ToolError(f"path arguments must not contain '..': {arg!r}")
            if "/" in arg or "\\" in arg:
                self._safe_path(arg)
        return cli_args

    def _tool_edit_file(self, arguments: str) -> ToolResult:
        args = self._validate("edit_file", arguments)
        rel = args["path"]
        old_str = args["old_str"]
        new_str = args["new_str"]
        if not old_str:
            raise _ToolError("old_str must be a non-empty string")
        if old_str == new_str:
            raise _ToolError("old_str and new_str are identical")
        target = self._safe_path(rel)
        src_root = (self.workspace / "src").resolve()
        if not target.is_relative_to(src_root):
            raise _ToolError("edit_file may only modify existing files below src/")
        if not target.is_file():
            raise _ToolError(f"not a file: {rel!r}")
        try:
            with target.open("r", encoding="utf-8", newline="") as handle:
                text = handle.read()
        except (UnicodeDecodeError, OSError) as exc:
            raise _ToolError(f"cannot read {rel!r}: {exc}") from exc
        eol = "\r\n" if "\r\n" in text else "\n"
        old_match = old_str.replace("\r\n", "\n").replace("\n", eol)
        new_match = new_str.replace("\r\n", "\n").replace("\n", eol)
        count = text.count(old_match)
        if count == 0:
            raise _ToolError(f"old_str not found in {rel!r}")
        if count > 1:
            raise _ToolError(f"old_str occurs {count} times in {rel!r}; include more surrounding lines to make it unique")
        new_text = text.replace(old_match, new_match, 1)
        try:
            with target.open("w", encoding="utf-8", newline="") as handle:
                handle.write(new_text)
        except OSError as exc:
            raise _ToolError(f"cannot write {rel!r}: {exc}") from exc
        diff = "".join(
            difflib.unified_diff(
                text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=rel,
                tofile=rel,
            )
        )
        return self._bounded(diff or "(no changes)")

    def _valid_test_target(self, target: str) -> str:
        if not isinstance(target, str) or not target.strip():
            raise _ToolError("target must be a non-empty string")
        if not _TEST_TARGET_RE.match(target):
            raise _ToolError("target must look like 'tests/test_x.py' or 'tests/test_x.py::test_name'")
        file_part = target.split("::", 1)[0]
        if not self._safe_path(file_part).is_file():
            raise _ToolError(f"test file not found: {file_part!r}")
        return target

    def _parse_junit(self, xml_path: Path) -> dict:
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError as exc:
            raise _ToolError(f"cannot parse the pytest report: {exc}") from exc
        suites = root.findall(".//testsuite") or [root]
        total = failures = errors = skipped = 0
        failing: list[ET.Element] = []
        for suite in suites:
            total += int(suite.get("tests") or 0)
            failures += int(suite.get("failures") or 0)
            errors += int(suite.get("errors") or 0)
            skipped += int(suite.get("skipped") or 0)
            for case in suite.findall("testcase"):
                if case.find("failure") is not None or case.find("error") is not None:
                    failing.append(case)
        names = [f"{case.get('classname') or ''}::{case.get('name') or '?'}" for case in failing]
        summary: dict[str, Any] = {
            "total": total,
            "passed": max(total - failures - errors - skipped, 0),
            "failed": failures + errors,
            "skipped": skipped,
            "failing_tests": names[:_MAX_FAILING_LISTED],
        }
        if len(names) > _MAX_FAILING_LISTED:
            summary["failing_tests"].append(f"... and {len(names) - _MAX_FAILING_LISTED} more failing tests")
        tracebacks: dict[str, str] = {}
        for case in failing[:_MAX_TRACEBACKS]:
            element = case.find("failure") if case.find("failure") is not None else case.find("error")
            name = f"{case.get('classname') or ''}::{case.get('name') or '?'}"
            text = (element.text or element.get("message") or "").strip()
            tracebacks[name] = "\n".join(text.splitlines()[-12:])[:_MAX_TRACEBACK_CHARS]
        if tracebacks:
            summary["tracebacks"] = tracebacks
        return summary

    def _minimal_env(self) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": "src",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        for key in ("SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP"):
            value = os.environ.get(key)
            if value:
                env[key] = value
        return env

    def _bounded(self, output: Any, truncated: bool = False) -> ToolResult:
        limit = MAX_OUTPUT_CHARS - _JSON_OVERHEAD

        def size(value: Any) -> int:
            try:
                return len(json.dumps(value, ensure_ascii=False, default=str))
            except (TypeError, ValueError):
                return len(str(value))

        if size(output) <= limit:
            return ToolResult(ok=True, output=output, truncated=truncated)
        if isinstance(output, list):
            items = list(output)
            while len(items) > 1 and size(items) > limit:
                items = items[: max(1, len(items) * 9 // 10)]
            if size(items) <= limit:
                return ToolResult(ok=True, output=items, truncated=True)
            text = json.dumps(items, ensure_ascii=False, default=str)
            while text and size(text) > limit:
                text = text[: max(1, len(text) * 9 // 10)]
            return ToolResult(ok=True, output=text, truncated=True)
        if isinstance(output, str):
            text = output
            while text and size(text) > limit:
                text = text[: max(1, len(text) * 9 // 10)]
            return ToolResult(ok=True, output=text, truncated=True)
        try:
            text = json.dumps(output, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(output)
        while text and size(text) > limit:
            text = text[: max(1, len(text) * 9 // 10)]
        return ToolResult(ok=True, output=text, truncated=True)
