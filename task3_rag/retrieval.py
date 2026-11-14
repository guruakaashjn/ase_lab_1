"""Run ONE retrieval configuration (R1–R5) on dev or test questions.

    uv run python task3_rag/retrieval.py --config r3 --size 512 --overlap 64 --split dev
    uv run python task3_rag/retrieval.py --config r4 --size 512 --overlap 64 --weight 0.3

Writes
    results/retrieval_<tag>_<split>.jsonl   {"id", "retrieved_doc_ids" (top 10 docs), "chunk_ids" (top 10 chunks)}
    results/stats_<tag>_<split>.json        indexing time, latency per query, tokens per query, ...
and registers the configuration in results/configs.json (generate.py rebuilds the chunks from it).

Usually you don't call this directly: experiments.py runs the whole grid.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from rag_core import (
    QUERY_INSTRUCTION,
    RESULTS,
    BM25Index,
    Chunk,
    LLMClient,
    count_tokens,
    embed_corpus_cached,
    embed_queries_cached,
    hybrid,
    hyde_passages,
    load_corpus,
    load_questions,
    make_chunks,
    rank,
    rrf,
    write_jsonl,
)

NEEDS = {  # which components a configuration uses
    "r1": {"bm25"},
    "r2": {"dense"},
    "r3": {"dense"},
    "r4": {"bm25", "dense"},
    "r5": {"bm25", "dense", "hyde"},
}


@dataclass
class Config:
    name: str  # r1 .. r5
    size: int = 512  # chunk size in characters
    overlap: int = 64  # overlap in characters
    weight: float = 0.3  # weight of BM25 in the weighted hybrid (R4/R5)
    fusion: str = "weighted"  # R4/R5: "weighted" (normalized scores, weight w) or "rrf" (reciprocal rank fusion)

    @property
    def chunking(self) -> str:
        return "fixed" if self.name == "r2" else "recursive"

    @property
    def tag(self) -> str:
        tag = f"{self.name}_{self.chunking}_s{self.size}_o{self.overlap}"
        if self.name in ("r4", "r5"):
            tag += "_rrf" if self.fusion == "rrf" else f"_w{self.weight:g}"
        return tag


class Index:
    """Chunks + BM25 + chunk embeddings for one chunking setting (shared by several configs)."""

    _cache: dict[tuple, "Index"] = {}

    def __init__(self, chunks: list[Chunk], chunk_seconds: float):
        self.chunks = chunks
        self.chunk_seconds = chunk_seconds
        self.bm25: BM25Index | None = None
        self.bm25_seconds = 0.0
        self.vectors: np.ndarray | None = None
        self.embed_seconds = 0.0

    @classmethod
    def get(cls, method: str, size: int, overlap: int, needs: set[str], llm: LLMClient | None) -> "Index":
        key = (method, size, overlap)
        if key not in cls._cache:
            start = time.time()
            chunks = make_chunks(load_corpus(), method, size, overlap)
            cls._cache[key] = Index(chunks, time.time() - start)
        index = cls._cache[key]
        if "bm25" in needs and index.bm25 is None:
            start = time.time()
            index.bm25 = BM25Index(index.chunks)
            index.bm25_seconds = time.time() - start
        if "dense" in needs and index.vectors is None:
            name = f"{method}_s{size}_o{overlap}"
            print(f"  embedding {len(index.chunks)} chunks ({name}) ...")
            index.vectors, index.embed_seconds = embed_corpus_cached(llm, [c.text for c in index.chunks], name)
        return index


def component_scores(cfg: Config, questions: list[dict], split: str, llm: LLMClient | None):
    """Per question: raw BM25 and dense chunk scores (whatever the config needs) + timing/token info."""
    needs = NEEDS[cfg.name]
    index = Index.get(cfg.chunking, cfg.size, cfg.overlap, needs, llm)
    n = len(questions)
    per_query_latency = np.zeros(n)
    per_query_tokens = np.zeros(n)
    bm25 = dense = None

    if "bm25" in needs:
        bm25 = []
        for i, q in enumerate(questions):
            start = time.time()
            bm25.append(index.bm25.scores(q["question"]))
            per_query_latency[i] += time.time() - start

    if "dense" in needs:
        query_texts = [QUERY_INSTRUCTION + q["question"] for q in questions]
        qvecs, latencies = embed_queries_cached(llm, query_texts, f"{split}")
        per_query_latency += np.asarray(latencies)
        per_query_tokens += [count_tokens(t) for t in query_texts]
        if "hyde" in needs:
            hyde = hyde_passages(llm, questions, split)
            passages = [hyde[q["id"]]["passage"] for q in questions]
            # the hypothetical passage is a *document*, so it is embedded without the query instruction
            pvecs, p_latencies = embed_queries_cached(llm, passages, f"hyde_{split}")
            qvecs = qvecs + pvecs
            qvecs = qvecs / np.linalg.norm(qvecs, axis=1, keepdims=True)
            per_query_latency += np.asarray(p_latencies)
            per_query_latency += [hyde[q["id"]]["latency_s"] for q in questions]
            per_query_tokens += [hyde[q["id"]]["prompt_tokens"] + hyde[q["id"]]["completion_tokens"]
                                 + count_tokens(hyde[q["id"]]["passage"]) for q in questions]
        dense = []
        for i in range(n):
            start = time.time()
            dense.append(index.vectors @ qvecs[i])
            per_query_latency[i] += time.time() - start

    return index, bm25, dense, per_query_latency, per_query_tokens


def final_scores(cfg: Config, bm25, dense, i: int) -> np.ndarray:
    if cfg.name == "r1":
        return bm25[i]
    if cfg.name in ("r2", "r3"):
        return dense[i]
    if cfg.fusion == "rrf":
        return rrf(bm25[i], dense[i])
    return hybrid(bm25[i], dense[i], cfg.weight)


def run(cfg: Config, split: str = "dev", llm: LLMClient | None = None, questions: list[dict] | None = None) -> dict:
    questions = questions or load_questions(split)
    if llm is None and NEEDS[cfg.name] != {"bm25"}:
        llm = LLMClient(log_path=Path("logs") / "task3_retrieval.jsonl")
    index, bm25, dense, latency, tokens = component_scores(cfg, questions, split, llm)

    rows = []
    for i, q in enumerate(questions):
        start = time.time()
        doc_ids, chunk_idx = rank(final_scores(cfg, bm25, dense, i), index.chunks)
        latency[i] += time.time() - start
        rows.append({"id": q["id"], "retrieved_doc_ids": doc_ids,
                     "chunk_ids": [index.chunks[j].chunk_id for j in chunk_idx]})

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"retrieval_{cfg.tag}_{split}.jsonl"
    write_jsonl(out, rows)

    needs = NEEDS[cfg.name]
    stats = {
        "tag": cfg.tag,
        "config": asdict(cfg),
        "split": split,
        "n_questions": len(questions),
        "n_chunks": len(index.chunks),
        "avg_chunk_chars": round(float(np.mean([len(c.text) for c in index.chunks])), 1),
        "indexing_s": round(index.chunk_seconds + (index.bm25_seconds if "bm25" in needs else 0)
                            + (index.embed_seconds if "dense" in needs else 0), 2),
        "latency_mean_s": round(float(np.mean(latency)), 4),
        "latency_p95_s": round(float(np.percentile(latency, 95)), 4),
        "retrieval_tokens_per_query": round(float(np.mean(tokens)), 1),
    }
    (RESULTS / f"stats_{cfg.tag}_{split}.json").write_text(json.dumps(stats, indent=2))
    register(cfg)
    return {"rows": rows, "stats": stats, "path": out}


def register(cfg: Config) -> None:
    path = RESULTS / "configs.json"
    configs = json.loads(path.read_text()) if path.exists() else {}
    configs[cfg.tag] = asdict(cfg)
    path.write_text(json.dumps(configs, indent=2))


def config_from_tag(tag: str) -> Config:
    configs = json.loads((RESULTS / "configs.json").read_text())
    return Config(**configs[tag])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one retrieval configuration.")
    parser.add_argument("--config", required=True, choices=sorted(NEEDS))
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--overlap", type=int, default=64)
    parser.add_argument("--weight", type=float, default=0.3, help="BM25 weight in the weighted hybrid (R4/R5)")
    parser.add_argument("--fusion", default="weighted", choices=["weighted", "rrf"])
    parser.add_argument("--split", default="dev", choices=["dev", "test"])
    args = parser.parse_args()
    result = run(Config(args.config, args.size, args.overlap, args.weight, args.fusion), args.split)
    print(json.dumps(result["stats"], indent=2))
    print(f"wrote {result['path']}")


if __name__ == "__main__":
    main()
