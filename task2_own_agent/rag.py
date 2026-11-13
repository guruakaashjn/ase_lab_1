
"""Retrieval-Augmented Generation over the Task 2 style guide."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from common.llm_client import LLMClient, count_tokens


@dataclass
class Chunk:
    """A piece of a style-guide document."""

    text: str
    source: str


class StyleGuideRAG:
    """Loads, embeds, and searches style-guide documents."""

    def __init__(
        self,
        style_guide_dir: str | Path,
        llm: LLMClient,
        chunk_size: int = 500,
        overlap: int = 75,
    ):
        self.style_guide_dir = Path(style_guide_dir)
        self.llm = llm
        self.chunk_size = chunk_size
        self.overlap = overlap

        self.chunks: list[Chunk] = []
        self.embeddings: np.ndarray | None = None

        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be between 0 and chunk_size.")

    def load_documents(self) -> list[Chunk]:
        """Read Markdown files and split them into overlapping chunks."""

        if not self.style_guide_dir.is_dir():
            raise FileNotFoundError(
                f"Style guide directory not found: {self.style_guide_dir}"
            )

        chunks = []
        step = self.chunk_size - self.overlap

        files = sorted(self.style_guide_dir.glob("*.md"))

        if not files:
            raise FileNotFoundError(
                f"No Markdown files found in {self.style_guide_dir}"
            )

        for file_path in files:
            content = file_path.read_text(encoding="utf-8").strip()
            if not content:
                continue

            # Preserve IDs such as SG-08 from the filename.
            source = file_path.name.split("_", 1)[0]

            words = content.split()

            for start in range(0, len(words), step):
                chunk_words = words[start : start + self.chunk_size]

                if not chunk_words:
                    continue

                chunks.append(
                    Chunk(
                        text=" ".join(chunk_words),
                        source=source,
                    )
                )

                if start + self.chunk_size >= len(words):
                    break

        self.chunks = chunks
        return chunks

    def build_index(self) -> None:
        """Generate and store embeddings for all chunks."""

        if not self.chunks:
            self.load_documents()

        texts = [chunk.text for chunk in self.chunks]
        self.embeddings = self.llm.embed(texts)

        # Normalize vectors once so search can use dot products.
        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        self.embeddings = self.embeddings / np.maximum(norms, 1e-12)

    def search(self, query: str, k: int = 5) -> list[Chunk]:
        """Return the most relevant chunks within a 1000-token limit."""

        if not query.strip():
            raise ValueError("Search query cannot be empty.")

        if k <= 0:
            raise ValueError("k must be positive.")

        if self.embeddings is None:
            self.build_index()

        query_embedding = self.llm.embed([query])[0]
        query_norm = np.linalg.norm(query_embedding)

        if query_norm == 0:
            return []

        query_embedding = query_embedding / query_norm

        scores = self.embeddings @ query_embedding
        ranked_indices = np.argsort(scores)[::-1]

        results = []
        total_tokens = 0

        for index in ranked_indices:
            if len(results) >= k:
                break

            chunk = self.chunks[int(index)]
            chunk_tokens = count_tokens(chunk.text)

            # Enforce the observation limit.
            if total_tokens + chunk_tokens > 1000:
                continue

            results.append(chunk)
            total_tokens += chunk_tokens

        return results


if __name__ == "__main__":
    # Simple standalone retrieval test.
    root = Path(__file__).resolve().parent.parent

    llm = LLMClient(
        log_path=root / "task2_own_agent" / "logs" / "rag_test.jsonl"
    )

    rag = StyleGuideRAG(
        style_guide_dir=root / "task2_own_agent" / "style_guide",
        llm=llm,
    )

    print("Loading and embedding style-guide documents...")
    rag.build_index()

    print(f"Documents loaded as chunks: {len(rag.chunks)}")

    query = "What are the rules for member bios and hot-take badges?"
    print(f"\nQuery: {query}\n")

    for result in rag.search(query, k=5):
        print(f"[{result.source}] {result.text}\n")

    print(llm.usage_summary())
