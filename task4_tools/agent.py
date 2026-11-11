"""Agent loop for Task 4: drives the ToolRegistry with native function calling.

Usage (from the repository root):
    uv run python task4_tools/reset_workspace.py
    uv run python task4_tools/agent.py --mock        # scripted fake model, no gateway
    uv run python task4_tools/agent.py               # real model from .env
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
for _path in (REPO_ROOT, HERE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from common.llm_client import LLMClient, message_to_dict
from tools import ToolRegistry

DEFAULT_WORKSPACE = HERE / "workspace"
LOG_DIR = HERE / "logs"
TRACE_PATH = LOG_DIR / "trace.jsonl"
TASK = "Make all tests pass and fix the problem described in ISSUE.md. Do not modify tests."

SYSTEM_PROMPT = f"""You are an autonomous coding agent working in the tinyledger repository.

Your task: {TASK}

Workspace layout and rules:
- All tool paths are relative to the workspace root.
- ISSUE.md describes the reported bug. Start by reading it and running the test suite.
- src/tinyledger/ contains the library, tests/ contains the tests, data/ contains sample CSV data.
- Use list_files, read_file and search_code to explore the code.
- Use run_tests for a structured pass/fail summary (numbers, failing test names, short tracebacks).
- Use run_cli to reproduce issues: python -m tinyledger <args>, e.g. ["report", "data/sample.csv", "--month", "2026-03"].
- edit_file only changes existing files below src/ and replaces exactly one unique old_str; include enough context.
- Tests, data and configuration files are read-only. Fix the source code, never the tests.
- Verify your changes with run_tests and stop once all tests pass.
"""


def append_trace(trace_path: Path, record: dict) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_agent(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).resolve()
    if not workspace.is_dir():
        print(f"[agent] workspace not found: {workspace}")
        print("[agent] run: uv run python task4_tools/reset_workspace.py")
        return 2

    registry = ToolRegistry(workspace=workspace)
    try:
        if args.mock:
            from mock_model import MockOpenAIClient

            llm = LLMClient(
                model="mock",
                log_path=LOG_DIR / "mock_run.jsonl",
                openai_client=MockOpenAIClient(),
            )
        else:
            llm = LLMClient(model=args.model, log_path=LOG_DIR / "agent_run.jsonl")
    except RuntimeError as exc:
        print(f"[agent] cannot create the LLM client: {exc}", file=sys.stderr)
        return 1

    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRACE_PATH.write_text("", encoding="utf-8")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": TASK},
    ]

    for step in range(1, args.max_steps + 1):
        message = llm.chat_with_tools(messages, tools=registry.schemas())
        messages.append(message_to_dict(message))
        if not message.tool_calls:
            answer = (message.content or "").strip()
            print(f"\n[agent] final answer ({step} model steps):\n{answer}")
            break
        for call in message.tool_calls:
            started = time.perf_counter()
            result = registry.execute(call.function.name, call.function.arguments)
            duration_s = time.perf_counter() - started
            append_trace(
                TRACE_PATH,
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                    "step": step,
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                    "ok": result.ok,
                    "error": result.error,
                    "truncated": result.truncated,
                    "duration_s": round(duration_s, 6),
                },
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result.to_content(),
                }
            )
            status = "ok" if result.ok else f"error: {(result.error or '')[:160]}"
            print(f"[agent] step {step:02d} {call.function.name:10} {status} ({duration_s:.2f}s)")
    else:
        print(f"\n[agent] stopped: step budget of {args.max_steps} exhausted without a final answer")

    print(f"[agent] usage: {llm.usage_summary()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Task 4 agent: fix tinyledger through tools.")
    parser.add_argument("--mock", action="store_true", help="use the scripted MockOpenAIClient instead of the gateway")
    parser.add_argument("--max-steps", type=int, default=30, help="maximum number of model steps (default: 30)")
    parser.add_argument("--model", default=None, help="chat model id for real runs (default: $LAB_CHAT_MODEL)")
    parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE), help="workspace directory (default: task4_tools/workspace)")
    args = parser.parse_args(argv)
    return run_agent(args)


if __name__ == "__main__":
    sys.exit(main())
