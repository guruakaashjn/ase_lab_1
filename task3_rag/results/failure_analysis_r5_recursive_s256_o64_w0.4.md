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

**Why (write this yourself):** ...

## dev025 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** Which permanent fix does the documentation recommend for the error that caused incident INC-2024-171?

**Ground truth:** The incident was caused by PQ-E1915. Fix: Throttling protects the node. Add capacity or reduce load. As a last resort, raise `metrics.threshold_percent`.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The documentation recommends adding capacity or reducing load, with raising `metrics.threshold_percent` as a last resort.

**Needed documents:** d0253 Postmortem INC-2024-171 [incident]; d0183 PQ-E1915 METRICS_THROTTLED [error]

**Documents in the context (rank order):** d0253 Postmortem INC-2024-171 [incident]; d0628 Postmortem INC-2024-123 [incident]; d0289 Postmortem INC-2024-160 [incident]; d0077 Postmortem INC-2024-120 [incident]; d0456 Postmortem INC-2024-151 [incident]

**Missing:** d0183

**Why (write this yourself):** ...

## dev030 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** Which permanent fix does the documentation recommend for the error that caused incident INC-2025-175?

**Ground truth:** The incident was caused by PQ-E2617. Fix: Check the logs for the underlying failure first. If the failures are transient, increase `dlq.max_retries`.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The documentation specifies checking logs for the underlying failure and increasing `dlq.max_retries` for transient failures.

**Needed documents:** d0442 Postmortem INC-2025-175 [incident]; d0174 PQ-E2617 DLQ_RETRIES_EXHAUSTED [error]

**Documents in the context (rank order):** d0442 Postmortem INC-2025-175 [incident]; d0324 Postmortem INC-2025-169 [incident]; d0169 Postmortem INC-2025-187 [incident]; d0535 Postmortem INC-2025-220 [incident]; d0919 Postmortem INC-2025-101 [incident]

**Missing:** d0174

**Why (write this yourself):** ...

## dev032 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** Which permanent fix does the documentation recommend for the error that caused incident INC-2024-213?

**Ground truth:** The incident was caused by PQ-E3891. Fix: Add worker threads or increase `compactor.queue_capacity`. A queue that stays full usually means the component is too slow.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The documentation provides a permanent fix: add worker threads or increase `compactor.queue_capacity`; a persistently full queue usually indicates the component is too slow.

**Needed documents:** d0377 Postmortem INC-2024-213 [incident]; d0350 PQ-E3891 COMPACTOR_WORK_QUEUE_FULL [error]

**Documents in the context (rank order):** d0377 Postmortem INC-2024-213 [incident]; d0628 Postmortem INC-2024-123 [incident]; d0077 Postmortem INC-2024-120 [incident]; d0384 Postmortem INC-2024-128 [incident]; d0898 Postmortem INC-2024-212 [incident]

**Missing:** d0350

**Why (write this yourself):** ...

## dev042 (multi-hop) – retrieval: 2 of 2 needed documents not in the context

**Question:** What is the current default value of the setting that the error catalogue recommends changing for PQ-E2051?

**Ground truth:** `compactor.compression` defaults to `lz4` in 4.x.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – It says the information is unavailable, but the current default is `lz4` for `compactor.compression` in 4.x.

**Needed documents:** d0738 PQ-E2051 COMPACTOR_CODEC_MISMATCH [error]; d0564 compactor.compression [config]

**Documents in the context (rank order):** d0785 PQ-E2051 after upgrade? [forum]; d0879 Help: compactor: codec mismatch in production [forum]; d0736 Help: compactor: codec mismatch in production [forum]; d0841 Help: compactor: codec mismatch in production [forum]; d0765 PQ-E2771 after upgrade? [forum]

**Missing:** d0738; d0564

**Why (write this yourself):** ...

## dev047 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** What is the current default value of the setting that the error catalogue recommends changing for PQ-E2425?

**Ground truth:** `acktracker.max_retries` defaults to `20` in 4.x.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The answer says the information is unavailable, but the current default is 20 in 4.x.

**Needed documents:** d0522 PQ-E2425 ACKTRACKER_RETRIES_EXHAUSTED [error]; d0749 acktracker.max_retries [config]

**Documents in the context (rank order):** d0517 PQ-E2425 after upgrade? [forum]; d0576 PQ-E2425 after upgrade? [forum]; d0522 PQ-E2425 ACKTRACKER_RETRIES_EXHAUSTED [error]; d0805 PaderQueue 2.1 release notes [changelog]; d0116 Getting 'acktracker: retries exhausted' all the time [forum]

**Missing:** d0749

**Why (write this yourself):** ...

## dev065 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** Which permanent fix does the documentation recommend for the error that caused incident INC-2025-101?

**Ground truth:** The incident was caused by PQ-E3177. Fix: Check for connection leaks in clients (connections that are never closed). If the load is legitimate, increase `scheduler.max_connections`.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The documentation gives a permanent fix for PQ-E3177: check for clients that leak connections, and if the load is legitimate, increase `scheduler.max_connections`.

**Needed documents:** d0919 Postmortem INC-2025-101 [incident]; d0227 PQ-E3177 SCHEDULER_CONNECTION_LIMIT_REACHED [error]

**Documents in the context (rank order):** d0919 Postmortem INC-2025-101 [incident]; d0324 Postmortem INC-2025-169 [incident]; d0265 Postmortem INC-2025-108 [incident]; d0726 Postmortem INC-2025-202 [incident]; d0110 Postmortem INC-2025-129 [incident]

**Missing:** d0227

**Why (write this yourself):** ...

## dev069 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** What is the current default value of the setting that the error catalogue recommends changing for PQ-E4020?

**Ground truth:** `spool.compression` defaults to `lz4` in 4.x.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The ground truth states that `spool.compression` defaults to `lz4` in 4.x, but the answer says the documentation does not contain this information.

**Needed documents:** d0506 PQ-E4020 SPOOL_CODEC_MISMATCH [error]; d0679 spool.compression [config]

**Documents in the context (rank order):** d0237 PQ-E4020 after upgrade? [forum]; d0510 PQ-E4020 after upgrade? [forum]; d0769 Help: spool: codec mismatch in production [forum]; d0672 Help: spool: codec mismatch in production [forum]; d0506 PQ-E4020 SPOOL_CODEC_MISMATCH [error]

**Missing:** d0679

**Why (write this yourself):** ...

## dev083 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** Which permanent fix does the documentation recommend for the error that caused incident INC-2024-147?

**Ground truth:** The incident was caused by PQ-E2051. Fix: Set `compactor.compression` to the same value on all nodes, then restart them one after another.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The documentation specifies setting `compactor.compression` to the same value on all nodes and restarting them one after another.

**Needed documents:** d0786 Postmortem INC-2024-147 [incident]; d0738 PQ-E2051 COMPACTOR_CODEC_MISMATCH [error]

**Documents in the context (rank order):** d0786 Postmortem INC-2024-147 [incident]; d0628 Postmortem INC-2024-123 [incident]; d0898 Postmortem INC-2024-212 [incident]; d0077 Postmortem INC-2024-120 [incident]; d0043 Postmortem INC-2024-104 [incident]

**Missing:** d0738

**Why (write this yourself):** ...

## dev089 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** Which permanent fix does the documentation recommend for the error that caused incident INC-2024-166?

**Ground truth:** The incident was caused by PQ-E4013. Fix: Throttling protects the node. Add capacity or reduce load. As a last resort, raise `auth.threshold_percent`.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – The documentation recommends adding capacity or reducing load, with raising `auth.threshold_percent` as a last resort.

**Needed documents:** d0602 Postmortem INC-2024-166 [incident]; d0229 PQ-E4013 AUTH_THROTTLED [error]

**Documents in the context (rank order):** d0602 Postmortem INC-2024-166 [incident]; d0628 Postmortem INC-2024-123 [incident]; d0077 Postmortem INC-2024-120 [incident]; d0135 Postmortem INC-2024-186 [incident]; d0289 Postmortem INC-2024-160 [incident]

**Missing:** d0229

**Why (write this yourself):** ...

## dev119 (multi-hop) – retrieval: 1 of 2 needed documents not in the context

**Question:** What is the current default value of the setting that the error catalogue recommends changing for PQ-E1799?

**Ground truth:** `retention.threshold_percent` defaults to `95` in 4.x.

**Our answer:** The documentation does not contain this information.

**Judge:** 0.0 – It says the information is unavailable, but the default is 95 in 4.x.

**Needed documents:** d0649 PQ-E1799 RETENTION_THROTTLED [error]; d0365 retention.threshold_percent [config]

**Documents in the context (rank order):** d0712 PQ-E1799 after upgrade? [forum]; d0649 PQ-E1799 RETENTION_THROTTLED [error]; d0019 Getting 'retention: throttled' all the time [forum]; d0589 Getting 'retention: throttled' all the time [forum]; d0336 Getting 'retention: throttled' all the time [forum]

**Missing:** d0365

**Why (write this yourself):** ...
