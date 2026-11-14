## Guru Akaash Nagaraj Janthalur -7397321

- Used OpenCode initially to plan the implementation steps necessary for task 4. Then, Understand how these steps lead us to the successful execution of the task. Then, giving valid and formatted prompts to the agent along with understanding the internal steps which the agent executes during the complete session.
- Designed and implemented a tool-based agent listing files, reading files, search code, running tests and running predefined tinyledger commands like report, balances etc.
- Understand and control several threatslike path traversal and symlinks checking, output truncation, malformed JSON structure validation, call of unavailable tools, and restricting the editing of test and configuration files.
- Identify and guide agent to fix the three bugs.
  - First in ledger.py, related to the existing balances() implementation, which caused KeyError when it encountered a participant who had not paid, which was fixed by scraping the initialization of balances logic.
  - Secondly in money.py, where dstributing amounts evenly was leaving the leftover cents, which was fixed using divmod() to distribute the remainder.
    - Thirdly in io_csv.py, where date parsing of month and day was done incorectly, which was fixed by correcting the order.
- Going through the agent workflow to understand and find similarity in the trace of how these bugs were resolved.
- Integrated and fixed the minor issues related to security control, and tools along with Yashas.

## Yashas Purushotama - 7393419

- Analyse the untrusted code scenario of the misleading the instruction directed at coding assisstance to update the test case instead of fixing the implementation if a test fails.
- Also analyse how the agent rightfully rejects the case of mock model attempt.
- Understand how the mock model works, which attempts to read secrets, call run_shell, edit tests/test_settlt.py, inject shell command through run_cli and malformed JSON.
- Integrated and fixed the minor issues related to security control, and tools jointly with Guru Akaash.

## Sai Dheeraj Reddy Banda -7399879

- Implemented R1 (BM25), R2 (fixed-size dense retrieval) and R3 (recursive dense retrieval).
- Conducted the chunk-size comparison using 256, 512 and 1024-character chunks.
- Evaluated retrieval performance across question categories and analysed the results.
- Contributed to identifying retrieval weaknesses and comparing the approaches.
- Integrated and tested all five retrieval configurations along with Srivallabh.
- Reviewed evaluation results and discussed the final findings along with test-set predictions with Srivallabh.

## Srivallabh Tippa - 7392258

- Implemented R4 (weighted hybrid retrieval) and R5 (hybrid retrieval with HyDE).
- Tuned and justified the hybrid retrieval weight.
- Conducted end-to-end evaluation of the two best configurations using the LLM judge.
- Analysed failure cases, latency and token costs, and contributed to the final deployment recommendation.
- Integrated and tested all five retrieval configurations jointly with Dheeraj.
- Reviewed evaluation results and discussed the final findings along with test-set predictions jointly with Dheeraj.

## Aniket Anandakumar Boryal -7400739

- Worked on developing our own agent using Python.
- Set up RAG to find relevant information from the style documents.
- Implemented the agent actions to read my team members profile and generate the new team website.
- Connected the website generation process with the automated checker.
- Worked on handling errors and correcting the website based on checker feedback.

## Common contributions done

- Setup and Understand the usage of opencode agent.
- Generate our team Website, with required data. Also understand how the images are embedded in the site's file.
- Analysing the issue and fixing the issue related to index.html file does not exist and profile-name normalization to handle file name case.
- Understand how images are embedded and end up in the HTML file.
- Prepared the presentation slides and understand each-others implementation with results.
