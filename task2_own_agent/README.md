# Task 2 – Build Your Own Coding Agent

## 1. Overview

This project implements an autonomous website-building agent using a manual JSON-based action protocol and Retrieval-Augmented Generation (RAG).

The agent reads team member profiles, retrieves relevant requirements from a style guide, generates a single-file HTML website, embeds member images, and validates the result using the provided website checker.

## 2. Project Structure

```text
task2_own_agent/
├── agent.py
├── rag.py
├── check_site.py
├── embed_images.py
├── style_guide/
├── site/
│   └── index.html
└── logs/
    └── run_YYYYMMDD_HHMMSS.jsonl
```

## 3. How to Run

Run the following command from the repository root:

```powershell
python -m task2_own_agent.agent --content task1_opencode/content --out task2_own_agent/site/index.html
```

The agent will:

1. Load and embed the style-guide documents.
2. Read the available team member profiles and images.
3. Retrieve relevant style-guide requirements.
4. Generate the website using the language model.
5. Replace image placeholders with embedded images.
6. Run the full website checker.
7. Correct validation failures and retry.
8. Ask for human feedback after successful completion.

Press Enter without typing feedback to finish the run.

## 4. RAG Design Decisions

### Document loading and chunking

- All Markdown documents in `style_guide/` are loaded.
- Chunk size: 500 words.
- Chunk overlap: 75 words.
- Overlapping chunks help preserve context between adjacent sections.
- Source document IDs, such as `SG-08`, are preserved with each chunk.

### Embedding model

The UPB AI Gateway embedding model is:

`kiconnect.qwen3-embedding-8b`

Embeddings are generated through `LLMClient.embed()` and stored in a NumPy matrix.

### Similarity search

- Cosine similarity is used to rank retrieved chunks.
- The query is embedded using the same embedding model.
- The five most relevant chunks are retrieved (`k = 5`).
- Each search observation is limited to a maximum of 1,000 tokens of style-guide text using `count_tokens()`.

## 5. Agent Design

The agent uses a manual JSON-based protocol rather than native model function calling.

Each model response follows this structure:

```json
{
  "thought": "Short reasoning",
  "action": "action_name",
  "args": {}
}
```

### Implemented actions

| Action | Purpose |
|---|---|
| `search_style_guide` | Retrieves relevant style-guide chunks through RAG. |
| `read_profiles` | Reads member Markdown profiles and lists available images. |
| `write_site` | Embeds images, saves the HTML, and runs the full checker. |
| `finish` | Allows the agent to finish only after successful validation. |

The system prompt describes the agent's task and action protocol without copying style-guide rules into the prompt.

The complete HTML document is supplied through `args.html` for the `write_site` action.

### Step limit and output handling

- Maximum agent steps: 25.
- Maximum model output tokens per request: 8,000.
- Invalid JSON, incorrect action arguments, and action errors are returned as error observations so the agent can attempt recovery.
- Unknown actions are rejected.
- The agent checks the validation report before accepting `finish`.

### Human feedback

After a successful finish action, the user can enter feedback in the terminal. Non-empty feedback is added to the conversation, allowing the agent to improve the website. Empty feedback ends the run.

## 6. Image Handling

The model uses image placeholders such as:

```html
<img src="{{image:aniket.jpg}}" alt="Photo of Aniket">
```

The agent does not generate Base64 image data.

The provided `embed_images()` helper replaces placeholders with embedded image data URIs, allowing the final website to work as a standalone HTML file without external image resources.

## 7. Logging

Each run creates a timestamped JSONL file under:

`task2_own_agent/logs/`

The log records:

- Messages sent to the model.
- Model responses.
- Action observations.
- Chat and embedding events.
- Step numbers and timestamps for agent events.

A successful run is included in the logs:

`run_20261111_124652.jsonl`

## 8. Validation Results

The generated website is saved at:

`task2_own_agent/site/index.html`

The full website checker passed all 25 checks during the successful run.

The generated website includes five member cards, embedded photographs, a day/night theme toggle, responsive styling, and a Future of Software Engineering section.

## 9. Known Limitations

- Website generation depends on the availability of the UPB AI Gateway.
- The agent's output quality depends on the accuracy of retrieved style-guide context and the model's responses.
- The model must return valid JSON, including correctly escaped HTML in `args.html`.
- The agent has a fixed maximum of 25 steps per run.
- The agent currently generates a single HTML file rather than a multi-page website.
- Human review is still important even when all automated checker requirements pass.
