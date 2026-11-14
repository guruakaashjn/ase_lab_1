"""Generate answers from retrieved documents (end-to-end RAG, small-to-big) for the judge or for the test submission.

    # 50 dev questions (the same stratified sample judge.py --sample 50 uses)
    uv run python task3_rag/generate.py --tag <tag> --split dev --sample 50
    uv run python task3_rag/judge.py task3_rag/results/answers_<tag>_dev.jsonl --sample 50 \
        --out task3_rag/results/judge_<tag>.jsonl

    # test predictions with the best configuration
    uv run python task3_rag/generate.py --tag <tag> --split test      # -> task3_rag/predictions_test.jsonl

<tag> is a configuration name from results/configs.json (written by experiments.py), e.g.
r4_recursive_s512_o64_w0.3. If the retrieval file for the split doesn't exist yet, it is computed first.
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from judge import stratified_sample
from rag_core import (ABSTENTION, HERE, RESULTS, LLMClient, count_tokens, doc_header, load_corpus, load_jsonl,
                      load_questions, make_chunks, write_jsonl)
from retrieval import config_from_tag, run

N_CONTEXT_DOCS = 5  # documents given to the generator (multi-hop questions need 2)
MAX_DOC_CHARS = 2500  # pages longer than this (changelogs) are represented by their retrieved chunks only
N_CONTEXT_CHUNKS = 10  # how many top chunks are scanned to find those documents (= chunks stored by retrieval.py)

SYSTEM_PROMPT = f"""You are the documentation assistant for PaderQueue, a message queue.
Answer the QUESTION using ONLY the numbered CONTEXT passages. Do not use outside knowledge.

Rules:
- Official reference pages ([config], [error], [cli], [changelog], [runbook]) are authoritative.
  [forum] answers can be wrong or outdated: only use them if no reference page covers the question.
- Versions matter. If the question names a version (e.g. 2.x), use the passage for that version (also check the
  changelog). Otherwise answer for the current version (4.x).
- Some questions need two steps, e.g. incident -> error code -> fix from the error catalogue. Combine the passages.
- Answer in 1-3 sentences with the exact names, codes and values from the context.
- The information can be spread over a page: e.g. a default value can appear in a property table OR in a
  configuration example. If the context describes the exact option, error, command or incident asked about,
  answer from it.
- Only if the context does not describe the specific thing asked about (for example only a similar but
  different option or error code), reply with exactly this sentence and nothing else:
  {ABSTENTION}"""


def build_contexts(doc_ids: list[str], chunk_ids: list[str], docs: dict[str, dict], chunk_text: dict[str, str]) -> list[str]:
    """Small-to-big: the retriever ranks SMALL chunks (precise matching), but the generator gets the WHOLE
    page each top chunk comes from, so it sees e.g. the property table AND the config example of an option.
    Our first run showed the model abstaining when it only saw fragments of the right page.
    Very long pages (> MAX_DOC_CHARS, e.g. changelogs) are represented by their retrieved chunks instead."""
    contexts = []
    for doc_id in doc_ids[:N_CONTEXT_DOCS]:
        doc = docs[doc_id]
        if len(doc["text"]) <= MAX_DOC_CHARS:
            contexts.append(doc_header(doc) + doc["text"].strip())
        else:
            parts = [chunk_text[cid] for cid in chunk_ids if cid.split("#")[0] == doc_id]
            contexts.append("\n[...]\n".join(parts) if parts else doc_header(doc) + doc["text"][:MAX_DOC_CHARS])
    return contexts


def build_prompt(question: str, contexts: list[str]) -> list[dict]:
    blocks = "\n\n".join(f"[{i}] {text}" for i, text in enumerate(contexts, 1))
    return [{"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"CONTEXT:\n{blocks}\n\nQUESTION: {question}"}]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--split", default="dev", choices=["dev", "test"])
    parser.add_argument("--sample", type=int, help="dev only: stratified sample (same as judge.py --sample)")
    parser.add_argument("--workers", type=int, default=4, help="parallel requests (gateway allows <= 10)")
    args = parser.parse_args()

    cfg = config_from_tag(args.tag)
    questions = load_questions(args.split)
    if args.sample:
        questions = stratified_sample(questions, args.sample)

    retrieval_path = RESULTS / f"retrieval_{cfg.tag}_{args.split}.jsonl"
    if not retrieval_path.exists():
        print(f"no {retrieval_path.name} yet, running retrieval for {args.split} ...")
        run(cfg, args.split)
    retrieved = {r["id"]: r for r in load_jsonl(retrieval_path)}
    corpus = load_corpus()
    docs = {d["doc_id"]: d for d in corpus}
    chunk_text = {c.chunk_id: c.text for c in make_chunks(corpus, cfg.chunking, cfg.size, cfg.overlap)}

    llm = LLMClient(log_path=Path("logs") / f"task3_generate_{cfg.tag}_{args.split}.jsonl")

    def answer(q: dict) -> dict:
        r = retrieved[q["id"]]
        contexts = build_contexts(r["retrieved_doc_ids"], r["chunk_ids"][:N_CONTEXT_CHUNKS], docs, chunk_text)
        messages = build_prompt(q["question"], contexts)
        start = time.time()
        reply = llm.chat(messages, max_tokens=4000).strip()
        return {"id": q["id"], "answer": reply or ABSTENTION, "contexts": contexts,
                "retrieved_doc_ids": retrieved[q["id"]]["retrieved_doc_ids"][:5],
                "_latency_s": time.time() - start,
                "_prompt_tokens": sum(count_tokens(m["content"]) for m in messages)}

    with ThreadPoolExecutor(args.workers) as pool:
        rows = list(pool.map(answer, questions))

    stats = {"tag": cfg.tag, "split": args.split, "n": len(rows),
             "generation_latency_mean_s": round(float(np.mean([r["_latency_s"] for r in rows])), 3),
             "generation_prompt_tokens_per_query_est": round(float(np.mean([r["_prompt_tokens"] for r in rows])), 1),
             "llm_usage": llm.usage_summary(),
             "llm_prompt_tokens_per_query": round(llm.total_prompt_tokens / len(rows), 1),
             "llm_completion_tokens_per_query": round(llm.total_completion_tokens / len(rows), 1),
             "cost_usd_total": round(llm.total_cost_usd, 5),
             "abstentions": sum(r["answer"] == ABSTENTION for r in rows)}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"stats_generation_{cfg.tag}_{args.split}.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    if args.split == "test":
        out = HERE / "predictions_test.jsonl"
        write_jsonl(out, [{"id": r["id"], "answer": r["answer"], "retrieved_doc_ids": r["retrieved_doc_ids"]}
                          for r in rows])
    else:
        out = RESULTS / f"answers_{cfg.tag}_dev.jsonl"
        write_jsonl(out, [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows])
    print(json.dumps(stats, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
