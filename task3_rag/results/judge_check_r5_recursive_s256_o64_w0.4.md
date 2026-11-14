# Hand check of 10 judge decisions – r5_recursive_s256_o64_w0.4

For each question, read the ground truth and our answer, decide yourself, then compare with the judge.

Verdicts prepared with AI assistance (Claude) and verified against the source documents in `data/corpus.jsonl`
(default values, flag descriptions, and whether an option exists at all).

| id | category | judge | my verdict | agree? |
|---|---|---|---|---|
| dev008 | identifier | 1.0 | 1.0 | yes |
| dev061 | identifier | 1.0 | 1.0 | yes |
| dev004 | paraphrase | 0.0 | 0.0 | yes |
| dev011 | paraphrase | 1.0 | 1.0 | yes |
| dev025 | multi-hop | 0.0 | 0.0 | yes |
| dev030 | multi-hop | 0.0 | 0.0 | yes |
| dev009 | version | 1.0 | 1.0 | yes |
| dev033 | version | 1.0 | 1.0 | yes |
| dev013 | unanswerable | 1.0 | 1.0 | yes |
| dev054 | unanswerable | 1.0 | 1.0 | yes |

## dev008 (identifier)

**Question:** In PaderQueue 4.x, what does `metrics.interval_s` default to?

**Ground truth:** `10`

**Our answer:** In PaderQueue 4.x, `metrics.interval_s` defaults to `10` seconds.

**Judge correctness:** 1.0 – It gives the default value as 10 seconds.

**Judge faithfulness:** 1.00

**My verdict / comment:** Correct. The 4.x config page (d0171) has Default `10`; the option is in seconds (`interval_s`), so adding "seconds" is supported and not a contradiction.

## dev061 (identifier)

**Question:** What does the `--tenant` flag of `pq topic restore` do?

**Ground truth:** Name of the tenant the command applies to.

**Our answer:** `--tenant` specifies the name of the tenant the `pq topic restore` command applies to.

**Judge correctness:** 1.0 – It correctly states that `--tenant` names the tenant the command applies to.

**Judge faithfulness:** 1.00

**My verdict / comment:** Correct. The CLI page of `pq topic restore` describes `--tenant` exactly as "Name of the tenant the command applies to."

## dev004 (paraphrase)

**Question:** Which setting controls how many times the mechanism that parks messages nobody could process tries again before it gives up?

**Ground truth:** The setting `dlq.max_retries`.

**Our answer:** `quota.max_retries` controls the maximum number of retry attempts before the quota gives up.

**Judge correctness:** 0.0 – The correct setting is `dlq.max_retries`, not `quota.max_retries`.

**Judge faithfulness:** 1.00

**My verdict / comment:** Wrong, as the judge says: the answer names `quota.max_retries`, the ground truth is `dlq.max_retries`. The judge's faithfulness of 1.0 is also right: the retrieved error page PQ-E2995 really says "increase `quota.max_retries`". A retrieval failure (the dlq page was not retrieved) that produced a wrong but faithful answer.

## dev011 (paraphrase)

**Question:** Which setting controls how long the central process that receives and forwards all messages waits for an answer before it counts the attempt as failed?

**Ground truth:** The setting `broker.timeout_ms`.

**Our answer:** `broker.timeout_ms` controls how long the broker waits for a response before the operation fails.

**Judge correctness:** 1.0 – It identifies `broker.timeout_ms` as the setting that controls how long the broker waits for a response before failure.

**Judge faithfulness:** 1.00

**My verdict / comment:** Correct. `broker.timeout_ms` is "time in milliseconds that the broker process ... waits for a response before the operation fails" (config page), which is what the question paraphrases.

## dev025 (multi-hop)

**Question:** Which permanent fix does the documentation recommend for the error that caused incident INC-2024-171?

**Ground truth:** The incident was caused by PQ-E1915. Fix: Throttling protects the node. Add capacity or reduce load. As a last resort, raise `metrics.threshold_percent`.

**Our answer:** The documentation does not contain this information.

**Judge correctness:** 0.0 – The documentation recommends adding capacity or reducing load, with raising `metrics.threshold_percent` as a last resort.

**Judge faithfulness:** -

**My verdict / comment:** Wrong compared to the ground truth (the fix for PQ-E1915 exists in the error catalogue). The abstention was the right behaviour for the context the model got: postmortem INC-2024-171 mentions PQ-E1915 but contains no fix, and the error page was not retrieved. So the judge is right, and the cause is retrieval (missing second hop).

## dev030 (multi-hop)

**Question:** Which permanent fix does the documentation recommend for the error that caused incident INC-2025-175?

**Ground truth:** The incident was caused by PQ-E2617. Fix: Check the logs for the underlying failure first. If the failures are transient, increase `dlq.max_retries`.

**Our answer:** The documentation does not contain this information.

**Judge correctness:** 0.0 – The documentation specifies checking logs for the underlying failure and increasing `dlq.max_retries` for transient failures.

**Judge faithfulness:** -

**My verdict / comment:** Wrong compared to the ground truth, same pattern as dev025: postmortem INC-2025-175 names PQ-E2617 but the error page with the fix (`dlq.max_retries`) was not retrieved. Judge is right.

## dev009 (version)

**Question:** What was the default value of `compactor.compression` in PaderQueue 2.x?

**Ground truth:** `none`

**Our answer:** The default value of `compactor.compression` in PaderQueue 2.x was `none`.

**Judge correctness:** 1.0 – It correctly states that the default value was `none`.

**Judge faithfulness:** 1.00

**My verdict / comment:** Correct. The 2.x config page of `compactor.compression` (d0903) has Default `none`; the model used the 2.x page, not the 4.x one.

## dev033 (version)

**Question:** What was the default value of `spool.interval_s` in PaderQueue 3.x?

**Ground truth:** `60`

**Our answer:** The default value of `spool.interval_s` in PaderQueue 3.x was `60` seconds.

**Judge correctness:** 1.0 – It gives the default value as `60`, matching the ground truth.

**Judge faithfulness:** 1.00

**My verdict / comment:** Correct. The 3.x config page of `spool.interval_s` (d0611) has Default `60` (seconds).

## dev013 (unanswerable)

**Question:** What is the default value of `spool.queue_capacity`?

**Ground truth:** The documentation does not contain this information.

**Our answer:** The documentation does not contain this information.

**Judge correctness:** 1.0 – It clearly states that the documentation does not contain the information.

**Judge faithfulness:** -

**My verdict / comment:** Correct abstention. `spool.queue_capacity` does not appear in any of the 932 documents; the retrieved pages were other `*.queue_capacity` options, and the model did not borrow their values.

## dev054 (unanswerable)

**Question:** What is the default value of `acktracker.worker_threads`?

**Ground truth:** The documentation does not contain this information.

**Our answer:** The documentation does not contain this information.

**Judge correctness:** 1.0 – It clearly states that the documentation does not contain the information.

**Judge faithfulness:** -

**My verdict / comment:** Correct abstention. `acktracker.worker_threads` does not appear in any document; the retrieved pages were `worker_threads` of other components (broker, dlq, quota, retention), and the model did not borrow their values.

## Result

**We agree with the judge in 10 of 10 decisions** (correctness), and also with its faithfulness scores.

How much does this tell us? The sample was chosen to contain both kinds of decisions (one judged wrong and one judged
correct per category, where available), but these are mostly easy cases: exact values, exact flag descriptions,
clear abstentions. The judge handled two subtle points correctly: it accepted an added unit ("10 seconds" for `10`)
instead of punishing different wording, and for dev004 it separated faithfulness (1.0, supported by the retrieved page)
from correctness (0, wrong component). What 10 checks cannot show is how the judge behaves on partial answers (none in
our sample) or on long multi-step answers, so we trust it for this dataset of short factual answers, not in general.
