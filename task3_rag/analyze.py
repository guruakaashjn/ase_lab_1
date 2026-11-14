"""After judging: compare the two best configurations, prepare the failure analysis and the judge check.

    uv run python task3_rag/analyze.py --tags <best_tag> <second_tag>

Writes into task3_rag/results/
  summary_judge.md                 judge metrics per category for every tag (+ generation cost/latency)
  failure_analysis_<best>.md       every question the best system got wrong or partial, classified as
                                   retrieval failure / generation failure, with the evidence. Pick 5 for the video
                                   and write the "why" in your own words.
  judge_check_<best>.md            10 judge decisions (2 per category) with an empty column for YOUR verdict
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

from generate import N_CONTEXT_DOCS
from rag_core import ABSTENTION, RESULTS, load_corpus, load_jsonl, load_questions
from retrieval import config_from_tag

CATEGORIES = ["identifier", "paraphrase", "multi-hop", "version", "unanswerable"]


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def fmt(v):
    return "-" if v is None else f"{v:.2f}"


def judge_summary(tags: list[str]) -> None:
    lines = ["# End-to-end results (LLM judge, 50 stratified dev questions)", "",
             "correctness: 1 correct / 0.5 partial / 0 wrong (for unanswerable: 1 = correctly abstained).",
             "faithfulness: share of claims supported by the context (abstentions not scored).", ""]
    for tag in tags:
        rows = load_jsonl(RESULTS / f"judge_{tag}.jsonl")
        by_cat = defaultdict(list)
        for r in rows:
            by_cat[r["category"]].append(r)
        lines += [f"## {tag}", "", "| category | n | correctness | faithfulness | answer relevance | abstained |",
                  "|---|---|---|---|---|---|"]
        for cat in CATEGORIES + ["OVERALL"]:
            items = rows if cat == "OVERALL" else by_cat[cat]
            if not items:
                continue
            lines.append(f"| {cat} | {len(items)} | {fmt(mean([r['correctness'] for r in items]))} | "
                         f"{fmt(mean([r['faithfulness'] for r in items]))} | "
                         f"{fmt(mean([r['answer_relevance'] for r in items]))} | "
                         f"{sum(r['abstained'] for r in items)} |")
        stats_path = RESULTS / f"stats_generation_{tag}_dev.json"
        if stats_path.exists():
            st = json.loads(stats_path.read_text(encoding="utf-8"))
            lines += ["", f"Generation: {st['llm_prompt_tokens_per_query']} prompt + "
                          f"{st['llm_completion_tokens_per_query']} completion tokens per question, "
                          f"mean latency {st['generation_latency_mean_s']} s, cost ${st['cost_usd_total']} for {st['n']} questions."]
        lines.append("")
    (RESULTS / "summary_judge.md").write_text("\n".join(lines), encoding="utf-8")


def failure_analysis(tag: str) -> None:
    cfg = config_from_tag(tag)
    questions = {q["id"]: q for q in load_questions("dev")}
    titles = {d["doc_id"]: f"{d['title']} [{d['type']}]" for d in load_corpus()}
    judged = load_jsonl(RESULTS / f"judge_{tag}.jsonl")
    answers = {a["id"]: a for a in load_jsonl(RESULTS / f"answers_{tag}_dev.jsonl")}
    retrieved = {r["id"]: r for r in load_jsonl(RESULTS / f"retrieval_{cfg.tag}_dev.jsonl")}

    failures = []
    for j in judged:
        if j["correctness"] >= 1:
            continue
        q = questions[j["id"]]
        context_docs = retrieved[q["id"]]["retrieved_doc_ids"][:N_CONTEXT_DOCS]
        groups = q["relevant_doc_ids"]
        missing = [g for g in groups if not set(g) & set(context_docs)]
        answer = answers[q["id"]]["answer"]
        if not groups:
            kind = "generation: answered an unanswerable question (should have abstained)"
        elif missing:
            kind = f"retrieval: {len(missing)} of {len(groups)} needed documents not in the context"
        elif answer.strip() == ABSTENTION:
            kind = "generation: abstained although the answer was in the context"
        else:
            kind = "generation: the right documents were in the context, the answer is still wrong"
        failures.append((q, j, answer, context_docs, missing, kind))

    lines = [f"# Failure analysis – {tag}", "",
             f"{len(failures)} of {len(judged)} judged questions are not fully correct.", "",
             "Classification rule: an answerable question is a *retrieval failure* if at least one needed document",
             f"was not among the {N_CONTEXT_DOCS} documents given to the generator; otherwise it is a *generation failure*.",
             "Check every case yourself: the judge can be wrong too.", "",
             "| id | category | correctness | classification |", "|---|---|---|---|"]
    lines += [f"| {q['id']} | {q['category']} | {j['correctness']} | {kind} |" for q, j, _, _, _, kind in failures]
    for q, j, answer, context_docs, missing, kind in failures:
        lines += ["", f"## {q['id']} ({q['category']}) – {kind}", "",
                  f"**Question:** {q['question']}", "", f"**Ground truth:** {q['answer']}", "",
                  f"**Our answer:** {answer}", "", f"**Judge:** {j['correctness']} – {j['correctness_reason']}", "",
                  "**Needed documents:** " + ("none (unanswerable)" if not q["relevant_doc_ids"] else
                                              "; ".join(" or ".join(f"{d} {titles[d]}" for d in g)
                                                        for g in q["relevant_doc_ids"])),
                  "", "**Documents in the context (rank order):** " + "; ".join(f"{d} {titles[d]}" for d in context_docs)]
        if missing:
            lines += ["", "**Missing:** " + "; ".join(" or ".join(g) for g in missing)]
        lines += ["", "**Why (write this yourself):** ..."]
    (RESULTS / f"failure_analysis_{tag}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def judge_check(tag: str) -> None:
    questions = {q["id"]: q for q in load_questions("dev")}
    judged = load_jsonl(RESULTS / f"judge_{tag}.jsonl")
    by_cat = defaultdict(list)
    for j in judged:
        by_cat[j["category"]].append(j)
    picked = []
    for cat in CATEGORIES:  # 2 per category; prefer one wrong/partial and one correct, so both kinds get checked
        items = sorted(by_cat[cat], key=lambda r: r["id"])
        wrong = [r for r in items if r["correctness"] < 1]
        right = [r for r in items if r["correctness"] >= 1]
        picked += (wrong[:1] + right[:1] + wrong[1:] + right[1:])[:2]
    answers = {a["id"]: a for a in load_jsonl(RESULTS / f"answers_{tag}_dev.jsonl")}
    lines = [f"# Hand check of 10 judge decisions – {tag}", "",
             "For each question, read the ground truth and our answer, decide yourself, then compare with the judge.", "",
             "| id | category | judge | my verdict | agree? |", "|---|---|---|---|---|"]
    lines += [f"| {j['id']} | {j['category']} | {j['correctness']} |  |  |" for j in picked]
    for j in picked:
        q = questions[j["id"]]
        unsupported = [c["claim"] for c in j.get("claims", []) if not c.get("supported")]
        lines += ["", f"## {j['id']} ({j['category']})", "", f"**Question:** {q['question']}", "",
                  f"**Ground truth:** {q['answer']}", "", f"**Our answer:** {answers[j['id']]['answer']}", "",
                  f"**Judge correctness:** {j['correctness']} – {j['correctness_reason']}", "",
                  f"**Judge faithfulness:** {fmt(j['faithfulness'])}"
                  + (f" (unsupported claims: {unsupported})" if unsupported else ""), "",
                  "**My verdict / comment:** ..."]
    (RESULTS / f"judge_check_{tag}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tags", nargs="+", required=True, help="judged configurations, best first")
    args = parser.parse_args()
    judge_summary(args.tags)
    failure_analysis(args.tags[0])
    judge_check(args.tags[0])
    print(f"wrote summary_judge.md, failure_analysis_{args.tags[0]}.md, judge_check_{args.tags[0]}.md in {RESULTS}")


if __name__ == "__main__":
    main()
