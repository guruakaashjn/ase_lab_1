
"""Task 2: Manual tool-using agent for website generation."""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from common.llm_client import LLMClient, count_tokens
from common.site_checker import check_site, member_names_from_content
from common.embed_images import embed_images

from task2_own_agent.rag import StyleGuideRAG


# Maximum number of model-action cycles.
MAX_STEPS = 25


def extract_json(text: str) -> dict:
    """Extract one JSON object from the model response."""

    text = text.strip()

    # Remove an optional Markdown code fence.
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # Find the JSON object.
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response.")

    result = json.loads(text[start : end + 1])

    if not isinstance(result, dict):
        raise ValueError("Model response must be a JSON object.")

    return result



def build_system_prompt() -> str:
    """Describe the agent protocol without copying style-guide rules."""

    return """
You are an autonomous website-building agent.

Your task is to create a complete, polished, single-file HTML website
for a university software engineering team.

You MUST retrieve design and content requirements from the style guide
using the search_style_guide action. Do not invent or assume style-guide rules.

First, read all member profiles using read_profiles.

Available actions and their exact arguments:

1. search_style_guide
   Arguments: {"query": "your specific question about the style guide"}

2. read_profiles
   Arguments: {}

3. write_site
   Arguments: {"html": "the complete HTML document as a JSON string"}
   Include the entire HTML document inside args.html.

4. finish
   Arguments: {"summary": "a short summary of the completed website"}

At every step, respond with exactly one JSON object:

{
  "thought": "A short explanation of your next step",
  "action": "action_name",
  "args": {}
}

Do not use Markdown fences or text outside the JSON object.
Escape quotation marks and newlines correctly in JSON strings.

Use observations returned by actions to decide your next step.
If an action fails, inspect the error and try to correct it.

The website must be a complete HTML document.
Do not use external scripts, stylesheets, fonts, images, or network requests.
Use image placeholders such as {{image:aniket.jpg}}.
Never generate Base64 image data yourself.

After writing the website, inspect the complete checker report.
Fix every failing check and write the website again.
Only call finish when the full checker reports success.
"""



def resolve_profile_directory(content_dir: str | Path) -> Path:
    """Find the folder containing the actual member Markdown files."""

    content_dir = Path(content_dir)

    # Support profiles directly inside the supplied folder.
    direct_profiles = [
        p for p in content_dir.glob("*.md")
        if not p.name.startswith("_")
    ]

    if direct_profiles:
        return content_dir

    # Support the nested Task 1 folder structure.
    nested_dir = content_dir / "content"

    nested_profiles = [
        p for p in nested_dir.glob("*.md")
        if not p.name.startswith("_")
    ]

    if nested_profiles:
        return nested_dir

    raise FileNotFoundError(
        f"No member profiles found in {content_dir}"
    )


def read_profiles_action(content_dir: str | Path) -> str:
    """Read member profiles and list their available photos."""

    profile_dir = resolve_profile_directory(content_dir)
    image_dir = profile_dir / "images"

    profiles = []

    for profile_file in sorted(profile_dir.glob("*.md")):
        if profile_file.name.startswith("_"):
            continue

        profile_text = profile_file.read_text(encoding="utf-8")

        profiles.append({
            "filename": profile_file.name,
            "content": profile_text,
        })

    images = []

    if image_dir.is_dir():
        supported_extensions = {
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"
        }

        images = [
            image_file.name
            for image_file in sorted(image_dir.iterdir())
            if image_file.is_file()
            and image_file.suffix.lower() in supported_extensions
        ]

    observation = {
        "profile_directory": str(profile_dir),
        "image_directory": str(image_dir),
        "profiles": profiles,
        "available_images": images,
    }

    return json.dumps(observation, ensure_ascii=False, indent=2)


def search_style_guide_action(
    rag: StyleGuideRAG,
    query: str,
) -> str:
    """Search the style guide and return relevant chunks with source IDs."""

    if not isinstance(query, str) or not query.strip():
        raise ValueError("The search query must be a non-empty string.")

    results = rag.search(query, k=5)

    observation = {
        "query": query,
        "results": [
            {
                "source": chunk.source,
                "text": chunk.text,
            }
            for chunk in results
        ],
        "total_tokens": sum(
            count_tokens(chunk.text) for chunk in results
        ),
    }

    return json.dumps(observation, ensure_ascii=False, indent=2)



def write_site_action(
    html: str,
    content_dir: str | Path,
    output_file: str | Path,
) -> str:
    """Embed photos, save the HTML, and run the full checker."""

    if not isinstance(html, str) or not html.strip():
        raise ValueError("The HTML content cannot be empty.")

    profile_dir = resolve_profile_directory(content_dir)
    image_dir = profile_dir / "images"

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Replace image placeholders with actual embedded photos.
    html = embed_images(html, image_dir)

    # Save the generated website.
    output_file.write_text(html, encoding="utf-8")

    # Validate using the actual member names.
    member_names = member_names_from_content(profile_dir)

    report = check_site(
        html,
        mode="full",
        member_names=member_names,
        file_size=output_file.stat().st_size,
    )

    return json.dumps(
        {
            "output_file": str(output_file),
            "passed": report.passed,
            "report": report.summary(),
            "failures": [
                {
                    "name": failure.name,
                    "message": failure.message,
                }
                for failure in report.failures()
            ],
        },
        ensure_ascii=False,
        indent=2,
    )

def finish_action(
    summary: str,
    last_report: dict | None,
) -> str:
    """Allow the agent to finish only after successful validation."""

    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("The finish summary cannot be empty.")

    if last_report is None:
        return json.dumps({
            "accepted": False,
            "message": "You must write and validate the website before finishing.",
        })

    if not last_report.get("passed", False):
        return json.dumps({
            "accepted": False,
            "message": "The website checker has not passed. Fix the failures first.",
            "failures": last_report.get("failures", []),
        }, ensure_ascii=False, indent=2)

    return json.dumps({
        "accepted": True,
        "summary": summary,
        "message": "The website passed the full checker.",
    }, ensure_ascii=False, indent=2)



class WebsiteAgent:
    """Runs the manual JSON-based agent loop."""

    def __init__(self, llm, rag, content_dir, output_file):
        self.llm = llm
        self.rag = rag
        self.content_dir = content_dir
        self.output_file = output_file

        self.messages = [
            {"role": "system", "content": build_system_prompt()}
        ]

        self.last_report = None
        self.step = 0

    def log(self, event):
        """Write an event to the run log."""
        self.llm.log_event({
            "step": self.step,
            "timestamp": datetime.now().isoformat(),
            **event,
        })

    def execute_action(self, action, args):
        """Execute one requested action."""

        if not isinstance(args, dict):
            raise ValueError("Action arguments must be a JSON object.")

        if action == "search_style_guide":
            return search_style_guide_action(
                self.rag,
                args.get("query"),
            )

        if action == "read_profiles":
            if args:
                raise ValueError("read_profiles takes no arguments.")
            return read_profiles_action(self.content_dir)

        if action == "write_site":
            html = args.get("html")

            if not isinstance(html, str):
                raise ValueError("write_site requires args['html'].")

            result = write_site_action(
                html,
                self.content_dir,
                self.output_file,
            )

            self.last_report = json.loads(result)
            return result

        if action == "finish":
            return finish_action(
                args.get("summary"),
                self.last_report,
            )

        raise ValueError(f"Unknown action: {action}")

    
    def run(self):
        """Run the agent until it finishes or reaches the step limit."""

        for step in range(1, MAX_STEPS + 1):
            self.step = step
            print(f"\n--- Agent step {step}/{MAX_STEPS} ---")

            self.log({
                "type": "messages_sent",
                "messages": self.messages,
            })

            response = self.llm.chat(
                self.messages,
                max_tokens=8000,
            )

            self.log({
                "type": "model_response",
                "content": response,
            })

            print("AI response received.")

            action = None

            try:
                decision = extract_json(response)

                thought = decision.get("thought", "")
                action = decision.get("action")
                args = decision.get("args", {})

                if not isinstance(action, str):
                    raise ValueError("The action must be a string.")

                print(f"Thought: {thought}")
                print(f"Action: {action}")

                observation = self.execute_action(action, args)

            except Exception as exc:
                observation = json.dumps({
                    "error": str(exc),
                    "message": "Correct your response and try again.",
                })

            self.log({
                "type": "observation",
                "content": observation,
            })

            self.messages.append({
                "role": "assistant",
                "content": response,
            })

            self.messages.append({
                "role": "user",
                "content": f"Observation:\n{observation}",
            })

            if action == "finish":
                result = json.loads(observation)

                if result.get("accepted"):
                    print("\nAgent finished successfully.")
                    print(result.get("summary", ""))

                    feedback = input(
                        "\nEnter feedback to improve the website, "
                        "or press Enter to stop: "
                    ).strip()

                    if not feedback:
                        return

                    self.messages.append({
                        "role": "user",
                        "content": f"Human feedback: {feedback}",
                    })

        print("\nMaximum number of steps reached.")


def main():
    """Configure and start the website-building agent."""

    parser = argparse.ArgumentParser(
        description="Task 2 autonomous website-building agent"
    )

    parser.add_argument(
        "--content",
        type=Path,
        required=True,
        help="Folder containing member profiles",
    )

    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output HTML file path",
    )

    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent

    log_dir = root / "task2_own_agent" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"run_{run_id}.jsonl"

    llm = LLMClient(log_path=log_path)

    rag = StyleGuideRAG(
        style_guide_dir=root / "task2_own_agent" / "style_guide",
        llm=llm,
    )

    print("Loading and embedding style-guide documents...")
    rag.build_index()
    print(f"Loaded {len(rag.chunks)} chunks.")

    agent = WebsiteAgent(
        llm=llm,
        rag=rag,
        content_dir=args.content,
        output_file=args.out,
    )

    agent.run()

    print("\nUsage summary:")
    print(llm.usage_summary())
    print(f"Run log saved to: {log_path}")


if __name__ == "__main__":
    main()
