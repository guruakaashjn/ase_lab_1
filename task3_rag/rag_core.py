"""Task 3 – RAG under the microscope: shared building blocks.

Everything the experiments need lives here (no RAG frameworks, as required by the lab):

  * loading the PaderQueue corpus and questions
  * two chunkers: fixed-size (R2) and recursive (R3/R1/R4/R5)
  * a BM25 tokenizer that keeps identifiers like `PQ-E4663` or `spool.buffer_bytes` intact
  * an on-disk embedding cache (the gateway model has 4096 dimensions, re-embedding is slow)
  * the retrievers R1–R5, all returning one score per chunk, so they can be combined
  * mapping chunk rankings to document rankings (what evaluate.py expects)

Chunk sizes and overlaps are measured in characters (1 token is roughly 4 characters of English text).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT))

from common.llm_client import LLMClient  # noqa: E402

_ENCODING = None


def count_tokens(text: str) -> int:
    """Approximate token count (tiktoken cl100k_base; the gateway models use other tokenizers, so this is an
    estimate). The encoding is loaded once; without it we fall back to len(text) / 4."""
    global _ENCODING
    if _ENCODING is None:
        try:
            import tiktoken

            _ENCODING = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _ENCODING = False
    return len(_ENCODING.encode(text)) if _ENCODING else max(1, len(text) // 4)

DATA = HERE / "data"
RESULTS = HERE / "results"
CACHE = HERE / ".cache"  # embeddings + HyDE generations; do NOT submit (can be > 50 MB)

ABSTENTION = "The documentation does not contain this information."

# Qwen3-Embedding is trained with an instruction in front of the *query* (documents get none).
QUERY_INSTRUCTION = (
    "Instruct: Given a question about the PaderQueue message queue, "
    "retrieve the documentation passages that answer it\nQuery: "
)


# --------------------------------------------------------------------------- data


def load_jsonl(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_corpus() -> list[dict]:
    return load_jsonl(DATA / "corpus.jsonl")


def load_questions(split: str) -> list[dict]:
    return load_jsonl(DATA / f"questions_{split}.jsonl")


# ----------------------------------------------------------------------- chunking


@dataclass
class Chunk:
    chunk_id: str  # e.g. "d0132#2"
    doc_id: str
    text: str  # what gets embedded / indexed / shown to the generator (header + body)


def doc_header(doc: dict) -> str:
    """Metadata line put in front of every chunk.

    Without it, the 3rd chunk of a long page no longer says which option, error code or
    version it is about. This matters most for the `version` questions (2.x vs 4.x pages).
    """
    version = f" | PaderQueue {doc['version']}" if doc.get("version") else ""
    return f"[{doc['type']}] {doc['title']}{version}\n"


def fixed_size_split(text: str, size: int, overlap: int) -> list[str]:
    """R2: cut every `size` characters, ignoring the structure of the text."""
    step = max(1, size - overlap)
    pieces = []
    for start in range(0, len(text), step):
        piece = text[start : start + size]
        if piece.strip():
            pieces.append(piece)
        if start + size >= len(text):
            break
    return pieces


# Coarse to fine: markdown sections, sub-sections, paragraphs, lines, sentences, words, characters.
RECURSIVE_SEPARATORS = ["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""]


def recursive_split(text: str, size: int, overlap: int, separators: list[str] = RECURSIVE_SEPARATORS) -> list[str]:
    """R3: split at the coarsest separator that exists in the text; pieces that are still
    too large are split again with the next, finer separator. Small neighbouring pieces are
    merged back together up to `size`, with about `overlap` characters repeated between chunks.
    """
    if len(text) <= size:
        return [text] if text.strip() else []

    # pick the first (= coarsest) separator that occurs in the text
    sep, finer = "", []
    for i, candidate in enumerate(separators):
        if candidate == "" or candidate in text:
            sep, finer = candidate, separators[i + 1 :]
            break

    if sep == "":
        parts = list(text)  # last resort: characters
    else:
        raw = text.split(sep)
        # keep the separator attached to the start of the following part (so "## Heading" stays a heading)
        parts = [raw[0]] + [sep + p for p in raw[1:]]

    chunks: list[str] = []
    buffer: list[str] = []  # small parts waiting to be merged
    for part in parts:
        if len(part) <= size:
            buffer.append(part)
        else:
            chunks.extend(_merge(buffer, size, overlap))
            buffer = []
            chunks.extend(recursive_split(part, size, overlap, finer))
    chunks.extend(_merge(buffer, size, overlap))
    return [c for c in chunks if c.strip()]


def _merge(parts: list[str], size: int, overlap: int) -> list[str]:
    """Greedily join consecutive parts into chunks of at most `size` characters.
    When a chunk is emitted, its last parts (up to `overlap` characters) start the next chunk."""
    chunks, current, length = [], [], 0
    for part in parts:
        if current and length + len(part) > size:
            chunks.append("".join(current))
            while current and (length > overlap or length + len(part) > size):
                length -= len(current[0])
                current.pop(0)
        current.append(part)
        length += len(part)
    if current:
        chunks.append("".join(current))
    return chunks


def make_chunks(corpus: list[dict], method: str, size: int, overlap: int) -> list[Chunk]:
    splitter = {"fixed": fixed_size_split, "recursive": recursive_split}[method]
    chunks = []
    for doc in corpus:
        header = doc_header(doc)
        for i, body in enumerate(splitter(doc["text"], size, overlap)):
            chunks.append(Chunk(f"{doc['doc_id']}#{i}", doc["doc_id"], header + body.strip()))
    return chunks


# -------------------------------------------------------------------------- BM25

TOKEN_RE = re.compile(r"[a-z0-9]+(?:[._\-/][a-z0-9]+)*")
STOPWORDS = set(
    "a an and are as at be by can do does for from has have how i if in is it its my of on or our "
    "should that the this to was we what when which why will with you your".split()
)


def bm25_tokenize(text: str) -> list[str]:
    """Lower-case word tokens. Identifiers are kept whole AND split into their parts:

        "PQ-E4663"            -> ["pq-e4663", "pq", "e4663"]
        "spool.buffer_bytes"  -> ["spool.buffer_bytes", "spool", "buffer", "bytes"]

    The whole token gives exact-match precision for identifier questions, the parts still
    match when a question only mentions "the spool buffer".
    """
    tokens = []
    for token in TOKEN_RE.findall(text.lower()):
        if token in STOPWORDS:
            continue
        tokens.append(token)
        if any(c in token for c in "._-/"):
            tokens.extend(p for p in re.split(r"[._\-/]", token) if p and p not in STOPWORDS)
    return tokens


class BM25Index:
    def __init__(self, chunks: list[Chunk]):
        from rank_bm25 import BM25Okapi

        self.bm25 = BM25Okapi([bm25_tokenize(c.text) for c in chunks])

    def scores(self, query: str) -> np.ndarray:
        return np.asarray(self.bm25.get_scores(bm25_tokenize(query)), dtype=np.float32)


# -------------------------------------------------------------------- embeddings


def _hash_texts(texts: list[str], model: str) -> str:
    h = hashlib.sha1(model.encode())
    for t in texts:
        h.update(t.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:16]


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)


# The gateway allows ~100 requests per minute per key. llm_client (given code) retries with backoff when we hit
# the limit, but gives up after 5 retries. We pace OUR embedding requests instead of relying on retries.
MIN_SECONDS_BETWEEN_REQUESTS = 0.7  # <= ~85 requests per minute
EMBED_BATCH_SIZE = 64  # v2 tried 16: duplicates still happened, at 4x the number of requests
_last_request = 0.0


def _pace() -> None:
    """Wait until at least MIN_SECONDS_BETWEEN_REQUESTS have passed since our previous embedding request."""
    global _last_request
    wait = _last_request + MIN_SECONDS_BETWEEN_REQUESTS - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_request = time.time()


EMBED_STATS = {"requests": 0, "batches_out_of_order": 0, "invalid_responses": 0, "last_latency_s": 0.0}


def _embed_request(llm: LLMClient, texts: list[str]) -> np.ndarray | None:
    """One embedding request, written by us instead of llm_client.embed() (given code, unchanged).

    The API returns every vector with an `index` field saying WHICH input it belongs to. llm_client.embed()
    takes the vectors in list order. Our runs showed that the gateway's answers to large batches are broken:
    e.g. for 64 inputs the indices were [0, 1, 2, 3, 4, 5, 4, 5, 6, 7, ...] - some texts got two vectors,
    others none. So we (1) put every vector at its `index` and (2) return None if the indices are not exactly
    0..n-1, so the caller can retry with a smaller batch. Every response is logged (indices included)."""
    _pace()
    start = time.time()
    response = llm._with_retries(
        lambda: llm._client.embeddings.create(model=llm.embedding_model, input=texts)
    )
    EMBED_STATS["last_latency_s"] = time.time() - start  # request time only, without the pacing pause
    EMBED_STATS["requests"] += 1
    data = response.data
    order = [getattr(item, "index", i) for i, item in enumerate(data)]
    valid = len(data) == len(texts) and sorted(order) == list(range(len(texts)))
    out_of_order = valid and order != list(range(len(texts)))
    EMBED_STATS["invalid_responses"] += int(not valid)
    EMBED_STATS["batches_out_of_order"] += int(out_of_order)
    llm.log_event({"embedding_request": len(texts), "n_returned": len(data), "valid": valid,
                   "out_of_order": out_of_order, "indices": order if not valid or out_of_order else "0..n-1",
                   "duration_s": round(EMBED_STATS["last_latency_s"], 3)})
    if not valid:
        return None
    vectors = [None] * len(texts)
    for i, item in zip(order, data):
        vectors[i] = item.embedding
    return _normalize(np.asarray(vectors, dtype=np.float32))


def _embed_one(llm: LLMClient, text: str) -> np.ndarray:
    for _ in range(3):
        vector = _embed_request(llm, [text])
        if vector is not None:
            return vector[0]
    raise RuntimeError("gateway returned an invalid response for a single text 3 times")


def _embed_robust(llm: LLMClient, texts: list[str]) -> np.ndarray:
    """Embed one batch; if the gateway's answer is invalid, split THIS batch in two halves and try again.
    The failures are random (~2-10% of requests, at every batch size), so we don't shrink the batch size for the
    rest of the run. Halves are different requests, so the gateway cache can't return the same broken answer."""
    if len(texts) == 1:
        return _embed_one(llm, texts[0])[None, :]
    result = _embed_request(llm, texts)
    if result is not None:
        return result
    mid = len(texts) // 2
    print(f"  invalid gateway response for a batch of {len(texts)} -> sending it again as {mid} + {len(texts) - mid}")
    return np.concatenate([_embed_robust(llm, texts[:mid]), _embed_robust(llm, texts[mid:])])


def _embed_batched(llm: LLMClient, texts: list[str], batch_size: int = EMBED_BATCH_SIZE) -> np.ndarray:
    return np.concatenate([_embed_robust(llm, texts[i : i + batch_size]) for i in range(0, len(texts), batch_size)])


def _wrong_duplicates(texts: list[str], vectors: np.ndarray) -> list[int]:
    """Indices of chunks whose vector is identical to the vector of a chunk with a DIFFERENT text."""
    groups: dict[bytes, list[int]] = {}
    for i, row in enumerate(np.round(vectors, 5)):
        groups.setdefault(row.tobytes(), []).append(i)
    return sorted(i for g in groups.values() if len({texts[j] for j in g}) > 1 for i in g)


def _validate_embeddings(llm: LLMClient, texts: list[str], vectors: np.ndarray, n_check: int = 30) -> dict:
    """Our first run showed that the gateway sometimes returns the SAME vector for different texts inside
    one batch request (so those chunks were indexed with another chunk's meaning). Two checks:
      1. no two different texts may share a vector -> re-embed those chunks one by one
      2. spot check: re-embed n_check random chunks one by one, cosine with the batch vector must be > 0.98
    The caller falls back to smaller batches if the spot check fails, so a broken index is never used silently."""
    report = {"duplicates_repaired": 0, "spot_checked": 0, "spot_check_failures": 0}
    for _ in range(3):
        bad = _wrong_duplicates(texts, vectors)
        if not bad:
            break
        print(f"  {len(bad)} chunks share a vector with a different text -> re-embedding them one by one")
        for i in bad:
            vectors[i] = _embed_one(llm, texts[i])
        report["duplicates_repaired"] += len(bad)
    rng = np.random.default_rng(0)
    for i in rng.choice(len(texts), size=min(n_check, len(texts)), replace=False):
        single = _embed_one(llm, texts[i])
        report["spot_checked"] += 1
        if float(single @ vectors[i]) < 0.98:
            report["spot_check_failures"] += 1
    report["duplicates_left_after_single_requests"] = len(_wrong_duplicates(texts, vectors))  # genuine, if any
    return report


def embed_corpus_cached(llm: LLMClient, texts: list[str], name: str) -> tuple[np.ndarray, float]:
    """Embed chunk texts (batched), validate, cache on disk. Returns (unit vectors, embedding time in s).
    Invalid gateway answers are repaired per batch (_embed_robust). If the spot check still fails, the whole
    index is embedded again with smaller batches (64 -> 16 -> 4);
    if even that fails, the run stops. Indexing time includes embedding + validation of the run that passed.
    Cache files are called emb_v3_*: earlier caches (v1, v2) contained misaligned vectors."""
    key = _hash_texts(texts, llm.embedding_model)
    path = CACHE / f"emb_v3_{name}_{key}.npy"
    meta_path = path.with_suffix(".json")
    if path.exists() and meta_path.exists():
        return np.load(path), json.loads(meta_path.read_text())["seconds"]
    CACHE.mkdir(parents=True, exist_ok=True)
    attempts = []
    for batch_size in (EMBED_BATCH_SIZE, 16, 4):
        before = dict(EMBED_STATS)
        start = time.time()
        vectors = _embed_batched(llm, texts, batch_size)
        report = _validate_embeddings(llm, texts, vectors)
        seconds = time.time() - start
        report.update(start_batch_size=batch_size,
                      requests=EMBED_STATS["requests"] - before["requests"],
                      invalid_responses=EMBED_STATS["invalid_responses"] - before["invalid_responses"],
                      batches_out_of_order=EMBED_STATS["batches_out_of_order"] - before["batches_out_of_order"])
        print(f"  embedding check: {report}")
        attempts.append(report)
        if report["spot_check_failures"] == 0:
            np.save(path, vectors)
            meta_path.write_text(json.dumps({"seconds": seconds, "n": len(texts), "model": llm.embedding_model,
                                             "attempts": attempts}))
            return vectors, seconds
        print(f"  spot check failed with batch size {batch_size} -> embedding again with smaller batches")
    raise RuntimeError(f"embeddings still misaligned with batch size 4: {attempts}")


def embed_queries_cached(llm: LLMClient, texts: list[str], name: str) -> tuple[np.ndarray, list[float]]:
    """Embed queries ONE BY ONE (that is what happens per user request, so the timing is a real
    per-query latency). Cached on disk together with the latency of the first, uncached call."""
    key = _hash_texts(texts, llm.embedding_model)
    path = CACHE / f"qemb_{name}_{key}.npy"  # single-text requests: not affected by the batch problem
    meta_path = path.with_suffix(".json")
    if path.exists() and meta_path.exists():
        return np.load(path), json.loads(meta_path.read_text())["latencies"]
    CACHE.mkdir(parents=True, exist_ok=True)
    vectors, latencies = [], []
    for i, text in enumerate(texts, 1):
        vectors.append(_embed_one(llm, text))
        latencies.append(EMBED_STATS["last_latency_s"])
        if i % 25 == 0:
            print(f"  embedded {i}/{len(texts)} queries")
    vectors = _normalize(np.asarray(vectors, dtype=np.float32))
    np.save(path, vectors)
    meta_path.write_text(json.dumps({"latencies": latencies, "model": llm.embedding_model}))
    return vectors, latencies


# ------------------------------------------------------------------ HyDE (R5)

HYDE_PROMPT = """You write documentation for PaderQueue, a message queue (similar to Kafka or RabbitMQ).
Write a short documentation passage (3-6 sentences) that would answer the question below.
Use the style of a reference page: name the exact configuration options, error codes (PQ-E....), CLI commands
and components that are likely involved. If you don't know the facts, invent plausible ones; the passage is
only used to search the real documentation.

Question: {question}

Passage:"""


def hyde_passages(llm: LLMClient, questions: list[dict], split: str) -> dict[str, dict]:
    """R5 (HyDE): one LLM call per question generates a hypothetical answer passage.
    Cached in .cache/hyde_<split>.jsonl with tokens and latency of the original call."""
    path = CACHE / f"hyde_{split}_{llm.model.replace('/', '_')}.jsonl"
    cached = {row["id"]: row for row in load_jsonl(path)} if path.exists() else {}
    CACHE.mkdir(parents=True, exist_ok=True)
    todo = [q for q in questions if q["id"] not in cached]
    if todo:
        print(f"  HyDE: generating {len(todo)} passages with {llm.model} ...")
    with path.open("a", encoding="utf-8") as f:
        for i, q in enumerate(todo, 1):
            prompt = HYDE_PROMPT.format(question=q["question"])
            before_prompt, before_completion = llm.total_prompt_tokens, llm.total_completion_tokens
            start = time.time()
            passage = llm.chat([{"role": "user", "content": prompt}], max_tokens=2000)
            row = {
                "id": q["id"],
                "passage": passage.strip(),
                "latency_s": time.time() - start,
                "prompt_tokens": llm.total_prompt_tokens - before_prompt,
                "completion_tokens": llm.total_completion_tokens - before_completion,
            }
            cached[q["id"]] = row
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            if i % 25 == 0:
                print(f"  HyDE {i}/{len(todo)}")
    return cached


# ------------------------------------------------------------------- combining


def minmax(scores: np.ndarray) -> np.ndarray:
    """Scale scores to [0, 1]. BM25 scores are unbounded (0 .. ~30), cosine similarities live in
    a narrow band (e.g. 0.3 .. 0.8): without this, one of them would dominate the sum."""
    lo, hi = float(scores.min()), float(scores.max())
    if hi - lo < 1e-12:
        return np.zeros_like(scores)
    return (scores - lo) / (hi - lo)


def hybrid(bm25_scores: np.ndarray, dense_scores: np.ndarray, weight_bm25: float) -> np.ndarray:
    """Weighted score fusion: normalize both score lists, then mix with weight w (BM25 share)."""
    return weight_bm25 * minmax(bm25_scores) + (1 - weight_bm25) * minmax(dense_scores)


RRF_K = 60  # standard constant from Cormack et al. (2009); damps the influence of the very top ranks


def rrf(bm25_scores: np.ndarray, dense_scores: np.ndarray) -> np.ndarray:
    """Reciprocal Rank Fusion: score = 1/(k + rank_bm25) + 1/(k + rank_dense).
    Uses only the RANKS, so the different score scales don't matter and there is no weight to tune.
    A chunk that is near the top in either list ends up high."""
    def ranks(scores: np.ndarray) -> np.ndarray:
        r = np.empty(len(scores))
        r[np.argsort(-scores, kind="stable")] = np.arange(1, len(scores) + 1)
        return r
    return 1.0 / (RRF_K + ranks(bm25_scores)) + 1.0 / (RRF_K + ranks(dense_scores))


def rank(scores: np.ndarray, chunks: list[Chunk], n_docs: int = 10, n_chunks: int = 10) -> tuple[list[str], list[int]]:
    """Chunk scores -> (top document ids, top chunk indices).
    A document is ranked by its best chunk (max pooling); duplicates are removed.
    Ties (e.g. near-duplicate forum threads with exactly the same BM25 score) are broken by chunk position:
    kind="stable" makes the order identical on every machine. With numpy's default sort, a teammate's run on
    Windows picked different tied documents in 60 of 150 questions, so BM25 recall differed by ~0.01."""
    order = np.argsort(-scores, kind="stable")
    doc_ids, seen = [], set()
    for idx in order:
        doc_id = chunks[idx].doc_id
        if doc_id not in seen:
            seen.add(doc_id)
            doc_ids.append(doc_id)
            if len(doc_ids) == n_docs:
                break
    return doc_ids, [int(i) for i in order[:n_chunks]]
