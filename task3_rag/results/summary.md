# Task 3 – retrieval results (dev, 120 answerable questions, k=5)

Unanswerable questions have no relevant documents; they only appear in the end-to-end (judge) results.

## Recall@5 per category

| config | identifier | paraphrase | multi-hop | version | overall R@5 | overall P@5 | R@10 |
|---|---|---|---|---|---|---|---|
| r1_recursive_s256_o64 | 0.967 | 0.300 | 0.500 | 0.800 | **0.642** | 0.590 | 0.725 |
| r2_fixed_s256_o64 | 0.600 | 0.867 | 0.050 | 0.833 | **0.588** | 0.484 | 0.637 |
| r3_recursive_s256_o64 | 0.733 | 0.867 | 0.100 | 0.867 | **0.642** | 0.495 | 0.658 |
| r4_recursive_s256_o64_w0.4 | 0.967 | 0.667 | 0.483 | 0.767 | **0.721** | 0.672 | 0.817 |
| r4_recursive_s256_o64_rrf | 0.833 | 0.767 | 0.150 | 0.767 | **0.629** | 0.520 | 0.746 |
| r5_recursive_s256_o64_w0.4 | 0.933 | 0.733 | 0.450 | 0.800 | **0.729** | 0.693 | 0.812 |

## Precision@5 per category

| config | identifier | paraphrase | multi-hop | version |
|---|---|---|---|---|
| r1_recursive_s256_o64 | 0.690 | 0.189 | 0.831 | 0.652 |
| r2_fixed_s256_o64 | 0.567 | 0.739 | 0.025 | 0.606 |
| r3_recursive_s256_o64 | 0.650 | 0.687 | 0.068 | 0.577 |
| r4_recursive_s256_o64_w0.4 | 0.748 | 0.540 | 0.798 | 0.603 |
| r4_recursive_s256_o64_rrf | 0.736 | 0.532 | 0.217 | 0.593 |
| r5_recursive_s256_o64_w0.4 | 0.766 | 0.580 | 0.784 | 0.642 |

## Chunk size comparison (R3, recursive + dense, same overlap)

| setting | #chunks | avg chunk chars | identifier | paraphrase | multi-hop | version | overall R@5 | overall P@5 |
|---|---|---|---|---|---|---|---|---|
| r3_recursive_s256_o64 | 2923 | 220.5 | 0.733 | 0.867 | 0.100 | 0.867 | 0.642 | 0.495 |
| r3_recursive_s512_o64 | 1348 | 419.1 | 0.700 | 0.867 | 0.100 | 0.700 | 0.592 | 0.512 |
| r3_recursive_s1024_o64 | 987 | 553.4 | 0.700 | 0.867 | 0.000 | 0.667 | 0.558 | 0.475 |

Hybrid: best weighted fusion w = 0.4 (BM25 share); chosen fusion for R5: **weighted** (see hybrid_fusion_sweep.csv)

## Cost and latency (retrieval only)

Indexing = chunking + BM25 build + embedding all chunks (first, uncached run).
Latency = per question: query embedding call(s) + HyDE call (R5) + scoring all chunks.
Tokens = tokens sent to models for retrieval (query embedding, HyDE prompt + output).
Generation tokens are added by generate.py (see results/stats_generation_*.json).

| config | #chunks | indexing (s) | latency mean (s) | latency p95 (s) | tokens / query |
|---|---|---|---|---|---|
| r1_recursive_s256_o64 | 2923 | 0.3 | 0.0131 | 0.0249 | 0.0 |
| r2_fixed_s256_o64 | 2821 | 81.94 | 0.2824 | 0.7164 | 42.4 |
| r3_recursive_s256_o64 | 2923 | 169.61 | 0.2824 | 0.7154 | 42.4 |
| r4_recursive_s256_o64_w0.4 | 2923 | 169.88 | 0.2917 | 0.7228 | 42.4 |
| r4_recursive_s256_o64_rrf | 2923 | 169.88 | 0.292 | 0.723 | 42.4 |
| r5_recursive_s256_o64_w0.4 | 2923 | 169.88 | 6.3557 | 11.6518 | 519.5 |
| r3_recursive_s512_o64 | 1348 | 50.32 | 0.2816 | 0.7144 | 42.4 |
| r3_recursive_s1024_o64 | 987 | 59.88 | 0.2813 | 0.7143 | 42.4 |
