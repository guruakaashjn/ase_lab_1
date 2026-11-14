# End-to-end results (LLM judge, 50 stratified dev questions)

correctness: 1 correct / 0.5 partial / 0 wrong (for unanswerable: 1 = correctly abstained).
faithfulness: share of claims supported by the context (abstentions not scored).

## r5_recursive_s256_o64_w0.4

| category | n | correctness | faithfulness | answer relevance | abstained |
|---|---|---|---|---|---|
| identifier | 10 | 1.00 | 1.00 | 0.77 | 0 |
| paraphrase | 10 | 0.90 | 1.00 | 0.71 | 0 |
| multi-hop | 10 | 0.00 | - | 0.37 | 10 |
| version | 10 | 1.00 | 1.00 | 0.78 | 0 |
| unanswerable | 10 | 1.00 | - | 0.46 | 10 |
| OVERALL | 50 | 0.78 | 1.00 | 0.62 | 20 |

Generation: 1077.9 prompt + 42.2 completion tokens per question, mean latency 2.049 s, cost $0.0066 for 50 questions.

## r4_recursive_s256_o64_w0.4

| category | n | correctness | faithfulness | answer relevance | abstained |
|---|---|---|---|---|---|
| identifier | 10 | 1.00 | 1.00 | 0.75 | 0 |
| paraphrase | 10 | 0.80 | 1.00 | 0.62 | 2 |
| multi-hop | 10 | 0.00 | - | 0.39 | 10 |
| version | 10 | 1.00 | 1.00 | 0.81 | 0 |
| unanswerable | 10 | 1.00 | - | 0.41 | 10 |
| OVERALL | 50 | 0.76 | 1.00 | 0.59 | 22 |

Generation: 1080.9 prompt + 44.3 completion tokens per question, mean latency 1.89 s, cost $0.00486 for 50 questions.
