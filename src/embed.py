"""Query embedding with the same model as the Day 6 index (bge-m3, 1024 dims, via Ollama)."""
import requests

from .config import Config

DIMENSIONS = 1024


def embed_query(text: str, cfg: Config) -> list[float]:
    try:
        resp = requests.post(f"{cfg.ollama_url}/api/embed",
                             json={"model": cfg.embedding_model, "input": text}, timeout=60)
    except requests.RequestException as e:  # connection refused, timeout, DNS ...
        raise RuntimeError(f"Ollama embed unreachable at {cfg.ollama_url}: {type(e).__name__}") from e
    if resp.status_code != 200:
        raise RuntimeError(f"Ollama embed failed: HTTP {resp.status_code}")
    try:
        vec = resp.json()["embeddings"][0]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Ollama embed returned an unexpected body: {type(e).__name__}") from e
    if len(vec) != DIMENSIONS:
        raise RuntimeError(f"embedding has {len(vec)} dims, index expects {DIMENSIONS}")
    return vec
