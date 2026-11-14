"""Run the whole Task 3 pipeline in one go (university VPN must be on):

    python task3_rag/run_all.py

1. experiments.py                      all retrieval configs on dev -> results/summary.md
2. picks the 2 best configs (R1-R5 at the chosen chunk size) by recall@5 (tie: precision@5)
3. generate.py + judge.py              50 stratified dev questions for both
4. analyze.py                          judge summary, failure analysis, judge hand-check sheet
5. generate.py --split test            with the config that has the better judge correctness -> predictions_test.jsonl

Each step is a separate script, so you can also rerun single steps by hand (see TASK3_GUIDE.md).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def step(*args: str) -> None:
    cmd = [sys.executable, *args]
    print(f"\n$ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True, cwd=HERE.parent)


def main() -> None:
    step("task3_rag/experiments.py", *sys.argv[1:])

    summary = (RESULTS / "summary.md").read_text(encoding="utf-8")
    configs = json.loads((RESULTS / "configs.json").read_text(encoding="utf-8"))
    # the final configs at the chosen chunk size are the rows of the first table in summary.md
    final_tags = [t for t in configs if f"| {t} |" in summary.split("## Precision@5")[0]]
    metrics = {t: json.loads((RESULTS / f"metrics_{t}.json").read_text(encoding="utf-8"))["summary"]["overall"] for t in final_tags}
    best_two = sorted(final_tags, key=lambda t: (metrics[t]["context_recall"], metrics[t]["context_precision"]),
                      reverse=True)[:2]
    print(f"\nTwo best configs by recall@5: {best_two}")

    correctness = {}
    for tag in best_two:
        step("task3_rag/generate.py", "--tag", tag, "--split", "dev", "--sample", "50")
        step("task3_rag/judge.py", f"task3_rag/results/answers_{tag}_dev.jsonl", "--sample", "50",
             "--out", f"task3_rag/results/judge_{tag}.jsonl")
        rows = [json.loads(line) for line in (RESULTS / f"judge_{tag}.jsonl").read_text(encoding="utf-8").splitlines() if line]
        correctness[tag] = sum(r["correctness"] for r in rows) / len(rows)

    best = max(best_two, key=lambda t: correctness[t])
    ordered = [best] + [t for t in best_two if t != best]
    step("task3_rag/analyze.py", "--tags", *ordered)
    step("task3_rag/generate.py", "--tag", best, "--split", "test")

    print("\n=== done ===")
    for tag in best_two:
        print(f"  {tag}: recall@5 {metrics[tag]['context_recall']:.3f}, judge correctness {correctness[tag]:.3f}")
    print(f"  test predictions from: {best}")
    print("  tables: task3_rag/results/summary.md, summary_judge.md")
    print(f"  to fill in by hand: results/judge_check_{best}.md, results/failure_analysis_{best}.md")


if __name__ == "__main__":
    main()
