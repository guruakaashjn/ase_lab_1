# Agent notes

- This folder is Task 1's OpenCode website workspace inside the larger Lab 1 repo. The root `README.md` in this folder covers OpenCode setup; `../README.md` covers shared Python setup and credential handling.
- The website deliverable is intended to be a single self-contained HTML file. No site framework or build step is configured here.
- Team profile source is `content/<name>.md`; use `content/_template.md` for its required sections. Matching photos live under `content/images/`.
- Reference images in HTML as `{{image:filename}}`, then embed them instead of writing base64 manually: `python embed_images.py site/index.html --images content/images` (overwrites the HTML; use `--out` to write elsewhere).
- Validate the result with `python check_site.py site/index.html --content content`; this task wrapper defaults to basic checks. `--full` adds the Task 2 style-guide rules, and `--json` emits machine-readable output. A failure exits nonzero.
- The checker expects embedded image data URIs, no external resources, a mobile viewport and responsive CSS, and a working day/night toggle. With `--content`, it also checks that all profile names appear and there are at least as many images as profiles.
- Never copy API keys into prompts, generated files, or commits. The README documents `UPB_AI_GATEWAY_KEY` for OpenCode credentials; use the environment variable rather than a literal key in `opencode.json`.
