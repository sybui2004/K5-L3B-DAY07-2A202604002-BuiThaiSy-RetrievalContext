"""Describe a figure crop with a local vision model served by Ollama (no data leaves the machine)."""
import base64
from pathlib import Path

import requests

PROMPT = (
    "You are transcribing a figure from a research paper for a search index. Be literal and do not guess. "
    "1) Say what kind of figure it is (bar chart, line chart, scatter plot, heatmap, table image, diagram, photo, other). "
    "2) Give the title or caption if visible. 3) For charts: name the x-axis and y-axis labels with units, list the "
    "legend entries, and state the clearly visible values or ranking (only numbers you can actually read). "
    "4) For diagrams: list the boxes/nodes and the arrows or relations between them. "
    "5) Finish with one sentence on the main takeaway. Answer in English, at most 220 words."
)


def describe(image_path: str | Path, model: str, url: str = "http://localhost:11434", timeout: int = 600) -> str:
    img = base64.b64encode(Path(image_path).read_bytes()).decode()
    r = requests.post(f"{url}/api/chat", timeout=timeout, json={
        "model": model, "stream": False, "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 400},
        "messages": [{"role": "user", "content": PROMPT, "images": [img]}]})
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


QA_PROMPT = (
    "Look carefully at this figure from a research paper and answer the question using only what is visible. "
    "For bar charts, say which bar is longest/shortest and give the order of labels from top to bottom. For diagrams, "
    "read the labels inside the boxes and at the ends of arrows. If several panels exist, use the panel the question "
    "refers to and name it. If the figure does not show the answer or you cannot see it clearly, say so. "
    "Answer briefly.\n\nQuestion: {q}")


def ask_figure(image_path: str | Path, question: str, model: str, url: str = "http://localhost:11434",
               timeout: int = 600) -> str:
    img = base64.b64encode(Path(image_path).read_bytes()).decode()
    r = requests.post(f"{url}/api/chat", timeout=timeout, json={
        "model": model, "stream": False, "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 250},
        "messages": [{"role": "user", "content": QA_PROMPT.format(q=question), "images": [img]}]})
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


class FigureReader:
    """Agent `enrich` hook: for the top figure chunks of a search round, ask the vision model the user's question
    about the figure crop and append its reading to a copy of the chunk. Cached per (question, chunk)."""

    def __init__(self, ask, *, max_per_round: int = 2, max_per_question: int = 3, model: str = "") -> None:
        self.ask, self.max_per_round, self.max_per_question, self.model = ask, max_per_round, max_per_question, model
        self.cache: dict[tuple[str, str], str] = {}
        self.calls, self.failures = 0, 0

    def __call__(self, question: str, results: list[dict]) -> list[dict]:
        out, used = [], 0
        for c in results:
            img = c["metadata"].get("image_path")
            key = (question, c["id"])
            if c["metadata"].get("kind") == "figure" and img and used < self.max_per_round:
                used += 1
                if key not in self.cache and sum(k[0] == question for k in self.cache) < self.max_per_question:
                    try:
                        self.cache[key] = self.ask(img, question)
                        self.calls += 1
                    except Exception as e:  # noqa: BLE001 - the chunk is still usable without the reading
                        self.cache[key] = ""
                        self.failures += 1
                        print(f"  figure reading failed for {c['id']}: {type(e).__name__}", flush=True)
                if self.cache.get(key):
                    c = dict(c, text=c["text"] + f"\nQuestion-specific reading of the figure image by {self.model} "
                                                 f"(may contain errors; exact values measured above take precedence): "
                                                 f"{self.cache[key]}")
            out.append(c)
        return out
