# Failure analysis – r5_recursive_s256_o64_w0.4

11 of 50 judged questions are not fully correct.

Classification rule: an answerable question is a *retrieval failure* if at least one needed document
was not among the 5 documents given to the generator; otherwise it is a *generation failure*.
Check every case yourself: the judge can be wrong too.

| id | category | correctness | classification |
|---|---|---|---|
| dev004 | paraphrase | 0.0 | retrieval: 1 of 1 needed documents not in the context |
| dev025 | multi-hop | 0.0 | retrieval: 1 of 2 needed documents not in the context |
| dev030 | multi-hop | 0.0 | retrieval: 1 of 2 needed documents not in the context |
| dev032 | multi-hop | 0.0 | retrieval: 1 of 2 needed documents not in the context |
| dev042 | multi-hop | 0.0 | retrieval: 2 of 2 needed documents not in the context |
| dev047 | multi-hop | 0.0 | retrieval: 1 of 2 needed documents not in the context |
| dev065 | multi-hop | 0.0 | retrieval: 1 of 2 needed documents not in the context |
| dev069 | multi-hop | 0.0 | retrieval: 1 of 2 needed documents not in the context |
| dev083 | multi-hop | 0.0 | retrieval: 1 of 2 needed documents not in the context |
| dev089 | multi-hop | 0.0 | retrieval: 1 of 2 needed documents not in the context |
| dev119 | multi-hop | 0.0 | retrieval: 1 of 2 needed documents not in the context |

## dev004 (paraphrase) – retrieval: 1 of 1 needed documents not in the context

**Question:** Which setting controls how many times the mechanism that parks messages nobody could process tries again before it gives up?

**Ground truth:** The setting `dlq.max_retries`.

**Our answer:** `quota.max_retries` controls the maximum number of retry attempts before the quota gives up.

**Judge:** 0.0 – The correct setting is `dlq.max_retries`, not `quota.max_retries`.

**Needed documents:** d0032 dlq.max_retries [config] or d0303 dlq.max_retries (PaderQueue 3.x) [config]

**Documents in the context (rank order):** d0806 PQ-E2995 QUOTA_RETRIES_EXHAUSTED [error]; d0655 spool.max_retries [config]; d0667 PaderQueue 2.2 release notes [changelog]; d0398 spool.max_retries (PaderQueue 3.x) [config]; d0530 broker.timeout_ms [config]

**Missing:** d0032 or d0303

**Why:** Retrieval failure that turned into a *wrong* answer, the only one among our failures. "The mechanism that parks messages nobody could process" describes the dead-letter queue: the needed config page (d0032 `dlq.max_retries`) says "dead-letter handler that moves undeliverable messages to the dead-letter queue". The question never says "dead letter" or "dlq", so neither BM25 nor the dense side (with HyDE) finds that page. Instead the top 5 contains pages for other components with the same kind of setting, retries: the error page PQ-E2995 QUOTA_RETRIES_EXHAUSTED (rank 1), whose fix says "increase `quota.max_retries`", and two `spool.max_retries` pages. The model answered `quota.max_retries`. The judge rated it **faithfulness 1.0, correctness 0**: every claim is supported by the context, but it is about the wrong component. This shows that faithfulness only checks the answer against the retrieved context, not against the truth; when retrieval returns a plausible look-alike, the generator cannot notice.

## dev025 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** Which permanent fix does the documentation recommend for the error that caused incident INC-2024-171?

**Ground truth:** The incident was caused by PQ-E1915. Fix: Throttling protects the node. Add capacity or reduce load. As a last resort, raise `metrics.threshold_percent`.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The documentation recommends adding capacity or reducing load, with raising `metrics.threshold_percent` as a last resort.

**Needed documents:** d0253 Postmortem INC-2024-171 [incident]; d0183 PQ-E1915 METRICS_THROTTLED [error]

**Documents in the context (rank order):** d0253 Postmortem INC-2024-171 [incident]; d0628 Postmortem INC-2024-123 [incident]; d0289 Postmortem INC-2024-160 [incident]; d0077 Postmortem INC-2024-120 [incident]; d0456 Postmortem INC-2024-151 [incident]

**Missing:** d0183

**Why:** Retrieval failure, typical of all six "incident → permanent fix" questions (also dev030, dev032, dev065, dev083, dev089). Hop 1 works: the right postmortem INC-2024-171 (d0253) is ranked #1. But the answer is on a second page, the error-catalogue entry for PQ-E1915 (d0183), and that page shares no words with the question: the error code only appears *inside* the incident text. A single search cannot know that code yet, so the other 4 slots are filled by other postmortems that look almost identical (same template: Summary, Timeline, Root cause, Follow-up). The postmortem itself says "Apply the fix recommended in the error catalogue for PQ-E1915", so the model correctly says the fix isn't in its context. Fix: iterative retrieval, i.e. take the error code from the top result and search again (a second hop).

## dev030 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** Which permanent fix does the documentation recommend for the error that caused incident INC-2025-175?

**Ground truth:** The incident was caused by PQ-E2617. Fix: Check the logs for the underlying failure first. If the failures are transient, increase `dlq.max_retries`.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The documentation specifies checking logs for the underlying failure and increasing `dlq.max_retries` for transient failures.

**Needed documents:** d0442 Postmortem INC-2025-175 [incident]; d0174 PQ-E2617 DLQ_RETRIES_EXHAUSTED [error]

**Documents in the context (rank order):** d0442 Postmortem INC-2025-175 [incident]; d0324 Postmortem INC-2025-169 [incident]; d0169 Postmortem INC-2025-187 [incident]; d0535 Postmortem INC-2025-220 [incident]; d0919 Postmortem INC-2025-101 [incident]

**Missing:** d0174

**Why:** same pattern as dev025, see there.

## dev032 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** Which permanent fix does the documentation recommend for the error that caused incident INC-2024-213?

**Ground truth:** The incident was caused by PQ-E3891. Fix: Add worker threads or increase `compactor.queue_capacity`. A queue that stays full usually means the component is too slow.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The documentation provides a permanent fix: add worker threads or increase `compactor.queue_capacity`; a persistently full queue usually indicates the component is too slow.

**Needed documents:** d0377 Postmortem INC-2024-213 [incident]; d0350 PQ-E3891 COMPACTOR_WORK_QUEUE_FULL [error]

**Documents in the context (rank order):** d0377 Postmortem INC-2024-213 [incident]; d0628 Postmortem INC-2024-123 [incident]; d0077 Postmortem INC-2024-120 [incident]; d0384 Postmortem INC-2024-128 [incident]; d0898 Postmortem INC-2024-212 [incident]

**Missing:** d0350

**Why:** same pattern as dev025, see there.

## dev042 (multi-hop) – retrieval: 2 of 2 needed documents not in the context

**Question:** What is the current default value of the setting that the error catalogue recommends changing for PQ-E2051?

**Ground truth:** `compactor.compression` defaults to `lz4` in 4.x.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – It says the information is unavailable, but the current default is `lz4` for `compactor.compression` in 4.x.

**Needed documents:** d0738 PQ-E2051 COMPACTOR_CODEC_MISMATCH [error]; d0564 compactor.compression [config]

**Documents in the context (rank order):** d0785 PQ-E2051 after upgrade? [forum]; d0879 Help: compactor: codec mismatch in production [forum]; d0736 Help: compactor: codec mismatch in production [forum]; d0841 Help: compactor: codec mismatch in production [forum]; d0765 PQ-E2771 after upgrade? [forum]

**Missing:** d0738; d0564

**Why:** Retrieval failure where forum threads crowd out the official pages: 2 of 2 needed documents missing. The question names PQ-E2051, but all 5 slots go to forum threads: four near-duplicate threads about this error ("PQ-E2051 after upgrade?", three times "Help: compactor: codec mismatch in production") and one about a different code (PQ-E2771). Each thread mentions the code or its log message in the title and body, so together they push both the error-catalogue page d0738 (hop 1) and the config page `compactor.compression` d0564 (hop 2) out of the top 5. The model abstained, which is correct for this context. Our hybrid has no notion of source authority, although the task README warns that forum answers can be wrong or outdated. Fix: use the `type` metadata, e.g. down-weight `forum` or reserve slots for reference pages (config/error/cli).

## dev047 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** What is the current default value of the setting that the error catalogue recommends changing for PQ-E2425?

**Ground truth:** `acktracker.max_retries` defaults to `20` in 4.x.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The answer says the information is unavailable, but the current default is 20 in 4.x.

**Needed documents:** d0522 PQ-E2425 ACKTRACKER_RETRIES_EXHAUSTED [error]; d0749 acktracker.max_retries [config]

**Documents in the context (rank order):** d0517 PQ-E2425 after upgrade? [forum]; d0576 PQ-E2425 after upgrade? [forum]; d0522 PQ-E2425 ACKTRACKER_RETRIES_EXHAUSTED [error]; d0805 PaderQueue 2.1 release notes [changelog]; d0116 Getting 'acktracker: retries exhausted' all the time [forum]

**Missing:** d0749

**Why:** Retrieval failure on the second hop. Hop 1 succeeded: the error-catalogue page for PQ-E2425 (d0522, rank 3, behind two forum threads) is in the context, and it names the setting to change, `acktracker.max_retries`. But the question asks for that setting's *current default*, which is only on the config page d0749, and that page isn't retrieved because the question never mentions `acktracker.max_retries`. The model correctly refused to invent a default. dev119 (PQ-E1799 → `retention.threshold_percent`) is the same pattern.

## dev065 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** Which permanent fix does the documentation recommend for the error that caused incident INC-2025-101?

**Ground truth:** The incident was caused by PQ-E3177. Fix: Check for connection leaks in clients (connections that are never closed). If the load is legitimate, increase `scheduler.max_connections`.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The documentation gives a permanent fix for PQ-E3177: check for clients that leak connections, and if the load is legitimate, increase `scheduler.max_connections`.

**Needed documents:** d0919 Postmortem INC-2025-101 [incident]; d0227 PQ-E3177 SCHEDULER_CONNECTION_LIMIT_REACHED [error]

**Documents in the context (rank order):** d0919 Postmortem INC-2025-101 [incident]; d0324 Postmortem INC-2025-169 [incident]; d0265 Postmortem INC-2025-108 [incident]; d0726 Postmortem INC-2025-202 [incident]; d0110 Postmortem INC-2025-129 [incident]

**Missing:** d0227

**Why:** same pattern as dev025, see there.

## dev069 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** What is the current default value of the setting that the error catalogue recommends changing for PQ-E4020?

**Ground truth:** `spool.compression` defaults to `lz4` in 4.x.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The ground truth states that `spool.compression` defaults to `lz4` in 4.x, but the answer says the documentation does not contain this information.

**Needed documents:** d0506 PQ-E4020 SPOOL_CODEC_MISMATCH [error]; d0679 spool.compression [config]

**Documents in the context (rank order):** d0237 PQ-E4020 after upgrade? [forum]; d0510 PQ-E4020 after upgrade? [forum]; d0769 Help: spool: codec mismatch in production [forum]; d0672 Help: spool: codec mismatch in production [forum]; d0506 PQ-E4020 SPOOL_CODEC_MISMATCH [error]

**Missing:** d0679

**Why:** Same two problems at once. Four of the five slots are forum threads about PQ-E4020 (near-duplicates such as "PQ-E4020 after upgrade?", "Help: spool: codec mismatch in production"); the official error page d0506 only makes it to rank 5. That page says "Set `spool.compression` to the same value on all nodes", but not the default value, which is only on the config page d0679, and that page is not retrieved (missing second hop). The model abstained, which is correct for this context.

## dev083 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** Which permanent fix does the documentation recommend for the error that caused incident INC-2024-147?

**Ground truth:** The incident was caused by PQ-E2051. Fix: Set `compactor.compression` to the same value on all nodes, then restart them one after another.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The documentation specifies setting `compactor.compression` to the same value on all nodes and restarting them one after another.

**Needed documents:** d0786 Postmortem INC-2024-147 [incident]; d0738 PQ-E2051 COMPACTOR_CODEC_MISMATCH [error]

**Documents in the context (rank order):** d0786 Postmortem INC-2024-147 [incident]; d0628 Postmortem INC-2024-123 [incident]; d0898 Postmortem INC-2024-212 [incident]; d0077 Postmortem INC-2024-120 [incident]; d0043 Postmortem INC-2024-104 [incident]

**Missing:** d0738

**Why:** same pattern as dev025, see there.

## dev089 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** Which permanent fix does the documentation recommend for the error that caused incident INC-2024-166?

**Ground truth:** The incident was caused by PQ-E4013. Fix: Throttling protects the node. Add capacity or reduce load. As a last resort, raise `auth.threshold_percent`.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The documentation recommends adding capacity or reducing load, with raising `auth.threshold_percent` as a last resort.

**Needed documents:** d0602 Postmortem INC-2024-166 [incident]; d0229 PQ-E4013 AUTH_THROTTLED [error]

**Documents in the context (rank order):** d0602 Postmortem INC-2024-166 [incident]; d0628 Postmortem INC-2024-123 [incident]; d0077 Postmortem INC-2024-120 [incident]; d0135 Postmortem INC-2024-186 [incident]; d0289 Postmortem INC-2024-160 [incident]

**Missing:** d0229

**Why:** same pattern as dev025, see there.

## dev119 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** What is the current default value of the setting that the error catalogue recommends changing for PQ-E1799?

**Ground truth:** `retention.threshold_percent` defaults to `95` in 4.x.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – It says the information is unavailable, but the default is 95 in 4.x.

**Needed documents:** d0649 PQ-E1799 RETENTION_THROTTLED [error]; d0365 retention.threshold_percent [config]

**Documents in the context (rank order):** d0712 PQ-E1799 after upgrade? [forum]; d0649 PQ-E1799 RETENTION_THROTTLED [error]; d0019 Getting 'retention: throttled' all the time [forum]; d0589 Getting 'retention: throttled' all the time [forum]; d0336 Getting 'retention: throttled' all the time [forum]

**Missing:** d0365

**Why:** same pattern as dev047, see there.

## Summary: what goes wrong and why

All 11 failures of our best system (R5) are **retrieval** failures: in every case at least one needed document was
not among the 5 documents given to the generator. There is no case where the right documents were in the context and
the answer was still wrong. In 10 of the 11 the model answered "The documentation does not contain this information."
instead of guessing. The exception is dev004: retrieval returned a look-alike page (a different component's retry
setting) and the model answered from it, wrong but faithful to the context.

| Pattern | Questions | Root cause | What would fix it |
|---|---|---|---|
| Incident → error fix (multi-hop) | dev025, 030, 032, 065, 083, 089 | 2nd page only reachable via the error code inside the 1st page; look-alike postmortems fill the slots | iterative retrieval (search again with the code found in hop 1) |
| Error → setting default (multi-hop) | dev042, 047, 069, 119 | hop 2 (config page) never retrieved; near-duplicate forum threads crowd out the official pages | iterative retrieval + down-weight `forum` documents via metadata |
| Vocabulary gap (paraphrase) | dev004 | question describes the dead-letter queue without naming it; a look-alike page from another component wins | cross-encoder re-ranking; query rewriting |

**Selected for the video:** dev025 (multi-hop, incident), dev042 (forum noise), dev004 (wrong but faithful), dev047 (second hop missing), dev069 (both problems).

## Recommendation

We would **deploy R4: hybrid search (recursive chunks of 256 characters, weighted fusion with BM25 weight 0.4)**,
with small-to-big generation (the whole page of each of the top 5 documents goes to the generator).

| | R4 (deploy) | R5 (R4 + HyDE) |
|---|---|---|
| recall@5 (dev) | 0.721 | 0.729 |
| precision@5 (dev) | 0.672 | 0.693 |
| judge correctness (50 dev) | 0.76 | 0.78 |
| retrieval latency per query | 0.29 s | 6.36 s |
| retrieval tokens per query | 42 | 520 |

Reasons:
1. **Quality**: R4 is the best method without an extra LLM call. It keeps BM25's strength on identifiers (0.967) and
   gets most of dense retrieval's strength on paraphrases (0.667, vs 0.300 for BM25 alone). The weight was chosen on
   the odd-numbered dev questions; on the held-out even-numbered ones every weight from 0.2 to 0.4 reaches recall@5
   0.70–0.73, while pure dense (0.67) and pure BM25 (0.60) are worse, so the result does not depend on a lucky weight.
   Reciprocal Rank Fusion was worse (0.629), mostly on multi-hop (0.150 vs 0.483), because it ignores how confident
   BM25 is about an exact match like `INC-2024-171`.
2. **Cost/latency**: R5 is only +0.008 recall and +0.02 correctness (1 of 50 questions) better, but about 22x slower
   and uses about 12x the tokens per query, because HyDE needs an LLM call before the search can start. For an
   interactive docs assistant that is not worth it. (For the test submission we used R5, because there only quality
   counts.)
3. **Safety**: the system usually abstains instead of guessing. dev004 shows the remaining risk: a wrong answer that
   looks well supported, because the retrieved page is about a similar but different component.

What we would add next, based on this analysis: (1) a second retrieval hop for multi-hop questions, using the error
code or setting found in the first results; (2) using the `type` metadata to down-weight forum threads, which crowd out
the official pages and can be wrong.
