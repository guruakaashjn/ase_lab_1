"""Run all retrieval experiments of Task 3 on the dev questions and write the result tables.

    uv run python task3_rag/experiments.py                       # everything (R1–R5, chunk sizes, weight sweep)
    uv run python task3_rag/experiments.py --sizes 256 512 1024 --overlap 64

Steps
  1. R3 (recursive chunking + dense) with 3 chunk sizes, same overlap  -> pick the best size on recall@5
  2. R1 (BM25) on exactly the same chunks as the best R3
  3. R2 (fixed-size chunking + dense) with the same size/overlap, for a fair comparison with R3
  4. Fusion sweep: weighted score fusion (w = BM25 weight, 0.0 .. 1.0) and Reciprocal Rank Fusion (RRF).
     To avoid tuning on the numbers we report, the choice is made on the odd-numbered dev questions and
     checked on the even-numbered ones.
  5. R4 with both fusions (weighted with the best w, and RRF);  R5 = R4 (chosen fusion) + HyDE

Writes into task3_rag/results/
  metrics_<tag>.json          evaluate.py output (summary + per-question scores), k=5
  summary_retrieval.csv       one row per config x category (recall@5, precision@5)
  hybrid_fusion_sweep.csv     the fusion sweep (weights + RRF)
  summary.md                  the tables for the video/README (per category, chunk sizes, cost/latency)
"""

from __future__ import annotations

import argparse
import csv
import json

import numpy as np

import evaluate as ev
from rag_core import RESULTS, LLMClient, load_questions, rank
from retrieval import Config, component_scores, run

CATEGORIES = ["identifier", "paraphrase", "multi-hop", "version", "unanswerable"]


def score(tag: str, rows: list[dict], questions: list[dict], k: int = 5) -> dict:
    report = ev.evaluate(rows, questions, k)
    if k == 5:
        (RESULTS / f"metrics_{tag}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report["summary"]


def fusion_sweep(size: int, overlap: int, questions: list[dict], llm: LLMClient) -> tuple[str, float]:
    """Choose how R4 combines BM25 and dense: weighted score fusion (w = 0.1 .. 0.9) or RRF.
    Chosen on the odd-numbered dev questions, checked on the even-numbered ones (held-out),
    so the choice isn't tuned on the numbers we report. Returns (fusion, w)."""
    from rag_core import hybrid, rrf

    cfg = Config("r4", size, overlap)
    index, bm25, dense, _, _ = component_scores(cfg, questions, "dev", llm)
    tune = [i for i, q in enumerate(questions) if int(q["id"][3:]) % 2 == 1]
    check = [i for i, q in enumerate(questions) if int(q["id"][3:]) % 2 == 0]

    def evaluate_scores(label: str, w: float | None, score_fn) -> dict:
        rows = [{"id": q["id"], "retrieved_doc_ids": rank(score_fn(i), index.chunks)[0]} for i, q in enumerate(questions)]
        s_tune = ev.evaluate([rows[i] for i in tune], [questions[i] for i in tune], 5)["summary"]["overall"]
        s_check = ev.evaluate([rows[i] for i in check], [questions[i] for i in check], 5)["summary"]["overall"]
        return {"fusion": label, "w_bm25": w,
                "tune_recall@5": round(s_tune["context_recall"], 4),
                "tune_precision@5": round(s_tune["context_precision"], 4),
                "heldout_recall@5": round(s_check["context_recall"], 4),
                "heldout_precision@5": round(s_check["context_precision"], 4)}

    table = [evaluate_scores("weighted", float(w), lambda i, w=w: hybrid(bm25[i], dense[i], w))
             for w in np.round(np.arange(0, 1.01, 0.1), 2)]
    table.append(evaluate_scores("rrf", None, lambda i: rrf(bm25[i], dense[i])))
    with (RESULTS / "hybrid_fusion_sweep.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)

    # w = 0 (pure dense) and w = 1 (pure BM25) are R3 and R1, so only true mixtures are candidates.
    candidates = [r for r in table if r["fusion"] == "rrf" or 0 < r["w_bm25"] < 1]
    key = lambda r: (r["tune_recall@5"], r["tune_precision@5"])  # noqa: E731
    best = max(candidates, key=key)
    best_weighted = max([r for r in candidates if r["fusion"] == "weighted"], key=key)
    print("\nFusion sweep (w = weight of BM25; chosen on odd ids, held-out = even ids):")
    for r in table:
        name = "RRF     " if r["fusion"] == "rrf" else f"w={r['w_bm25']:.1f}   "
        mark = "  <- chosen" if r is best else ("  <- best weighted" if r is best_weighted else "")
        print(f"  {name} tune R@5={r['tune_recall@5']:.3f}  held-out R@5={r['heldout_recall@5']:.3f}{mark}")
    return best["fusion"], best_weighted["w_bm25"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[256, 512, 1024])
    parser.add_argument("--overlap", type=int, default=64)
    parser.add_argument("--weight", type=float, help="skip the sweep and use this BM25 weight")
    parser.add_argument("--skip-r5", action="store_true")
    args = parser.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    questions = load_questions("dev")
    llm = LLMClient(log_path="logs/task3_retrieval.jsonl")
    summaries, stats = {}, {}

    def do(cfg: Config) -> None:
        print(f"\n=== {cfg.tag} ===")
        result = run(cfg, "dev", llm, questions)
        summaries[cfg.tag] = score(cfg.tag, result["rows"], questions, 5)
        summaries[cfg.tag]["recall@10"] = score(cfg.tag, result["rows"], questions, 10)["overall"]["context_recall"]
        stats[cfg.tag] = result["stats"]
        print(ev.format_table(summaries[cfg.tag], cfg.tag))

    # 1. chunk size sweep for R3
    for size in args.sizes:
        do(Config("r3", size, args.overlap))
    r3_tags = [Config("r3", s, args.overlap).tag for s in args.sizes]
    best_tag = max(r3_tags, key=lambda t: (summaries[t]["overall"]["context_recall"],
                                           summaries[t]["overall"]["context_precision"]))
    best_size = int(best_tag.split("_s")[1].split("_")[0])
    print(f"\nBest R3 chunk size: {best_size} characters")

    # 2./3. R1 and R2 on the same size
    do(Config("r1", best_size, args.overlap))
    do(Config("r2", best_size, args.overlap))

    # 4./5. hybrid: both fusion variants of R4 are reported; R5 uses the chosen one
    if args.weight is not None:
        fusion, weight = "weighted", args.weight
    else:
        fusion, weight = fusion_sweep(best_size, args.overlap, questions, llm)
    do(Config("r4", best_size, args.overlap, weight, "weighted"))
    do(Config("r4", best_size, args.overlap, weight, "rrf"))
    if not args.skip_r5:
        do(Config("r5", best_size, args.overlap, weight, fusion))

    write_summary(summaries, stats, r3_tags, best_size, weight, fusion)
    print(f"\nLLM usage for retrieval: {llm.usage_summary()}")
    print(f"Tables: {RESULTS / 'summary.md'}")


def write_summary(summaries: dict, stats: dict, r3_tags: list[str], best_size: int, weight: float,
                  fusion: str) -> None:
    with (RESULTS / "summary_retrieval.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["config", "category", "n", "recall@5", "precision@5"])
        for tag, s in summaries.items():
            for cat, v in s["per_category"].items():
                writer.writerow([tag, cat, v["n"], f"{v['context_recall']:.3f}", f"{v['context_precision']:.3f}"])
            o = s["overall"]
            writer.writerow([tag, "OVERALL", o["n"], f"{o['context_recall']:.3f}", f"{o['context_precision']:.3f}"])

    cats = [c for c in CATEGORIES if c != "unanswerable"]
    main_tags = [t for t in summaries if t not in r3_tags or f"_s{best_size}_" in t]
    order = sorted(main_tags, key=lambda t: t[:2])

    lines = ["# Task 3 – retrieval results (dev, 120 answerable questions, k=5)", "",
             "Unanswerable questions have no relevant documents; they only appear in the end-to-end (judge) results.",
             "", "## Recall@5 per category", "",
             "| config | " + " | ".join(cats) + " | overall R@5 | overall P@5 | R@10 |",
             "|---|" + "---|" * (len(cats) + 3)]
    for tag in order:
        s = summaries[tag]
        cells = [f"{s['per_category'][c]['context_recall']:.3f}" for c in cats]
        lines.append(f"| {tag} | " + " | ".join(cells)
                     + f" | **{s['overall']['context_recall']:.3f}** | {s['overall']['context_precision']:.3f}"
                     + f" | {s['recall@10']:.3f} |")
    lines += ["", "## Precision@5 per category", "", "| config | " + " | ".join(cats) + " |",
              "|---|" + "---|" * len(cats)]
    for tag in order:
        s = summaries[tag]
        lines.append(f"| {tag} | " + " | ".join(f"{s['per_category'][c]['context_precision']:.3f}" for c in cats) + " |")

    lines += ["", "## Chunk size comparison (R3, recursive + dense, same overlap)", "",
              "| setting | #chunks | avg chunk chars | " + " | ".join(cats) + " | overall R@5 | overall P@5 |",
              "|---|---|---|" + "---|" * (len(cats) + 2)]
    for tag in r3_tags:
        s, st = summaries[tag], stats[tag]
        lines.append(f"| {tag} | {st['n_chunks']} | {st['avg_chunk_chars']} | "
                     + " | ".join(f"{s['per_category'][c]['context_recall']:.3f}" for c in cats)
                     + f" | {s['overall']['context_recall']:.3f} | {s['overall']['context_precision']:.3f} |")

    lines += ["", f"Hybrid: best weighted fusion w = {weight} (BM25 share); chosen fusion for R5: **{fusion}** "
              "(see hybrid_fusion_sweep.csv)", "",
              "## Cost and latency (retrieval only)", "",
              "Indexing = chunking + BM25 build + embedding all chunks (first, uncached run).",
              "Latency = per question: query embedding call(s) + HyDE call (R5) + scoring all chunks.",
              "Tokens = tokens sent to models for retrieval (query embedding, HyDE prompt + output).",
              "Generation tokens are added by generate.py (see results/stats_generation_*.json).", "",
              "| config | #chunks | indexing (s) | latency mean (s) | latency p95 (s) | tokens / query |",
              "|---|---|---|---|---|---|"]
    for tag in order + [t for t in r3_tags if t not in order]:
        st = stats[tag]
        lines.append(f"| {tag} | {st['n_chunks']} | {st['indexing_s']} | {st['latency_mean_s']} | "
                     f"{st['latency_p95_s']} | {st['retrieval_tokens_per_query']} |")
    (RESULTS / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
