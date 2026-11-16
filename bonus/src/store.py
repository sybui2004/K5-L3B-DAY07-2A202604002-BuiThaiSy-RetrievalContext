"""Read access to the HELM index (table helm_chunks) mapped to the chunk schema used by src.agent."""
import json
from typing import Any, Callable

import psycopg

from src.config import Config
from src.embed import embed_query
from src.retrievers import HybridRetriever, _vec, normalize_query

SOURCE = "helm_2211.09110v2.pdf"
COLS = "chunk_id, page, kind, label, caption, text, bbox, image_path"


def row_to_chunk(r) -> dict:
    chunk_id, page, kind, label, caption, text, bbox, image_path = r
    return {"id": chunk_id, "text": text, "source_id": "helm", "source": SOURCE, "page": page,
            "metadata": {"kind": kind, "label": label, "caption": caption, "bbox": bbox, "image_path": image_path,
                         "page_end": page}}


def load_chunks(cfg: Config) -> list[dict]:
    with psycopg.connect(cfg.database_url) as conn:
        rows = conn.execute(f"SELECT {COLS} FROM helm_chunks ORDER BY chunk_id").fetchall()
    return [row_to_chunk(r) for r in rows]


class HelmDenseRetriever:
    def __init__(self, cfg: Config, embed: Callable[[str, Config], list[float]] = embed_query) -> None:
        self.cfg, self.embed = cfg, embed

    def search(self, query: str, *, filters: dict[str, Any] | None, top_k: int) -> list[dict]:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        if filters:
            raise ValueError("the HELM index supports no filters")
        vec = _vec(self.embed(normalize_query(query), self.cfg))
        sql = (f"SELECT {COLS}, 1 - (embedding <=> %s::vector) AS score FROM helm_chunks "
               f"ORDER BY embedding <=> %s::vector LIMIT %s")
        with psycopg.connect(self.cfg.database_url) as conn:
            rows = conn.execute(sql, [vec, vec, top_k]).fetchall()
        return [{**row_to_chunk(r[:-1]), "score": float(r[-1])} for r in rows]


def build_retriever(method: str, cfg: Config, chunks: list[dict]):
    dense = HelmDenseRetriever(cfg)
    if method == "dense":
        return dense
    from src.retrievers import Bm25Retriever
    bm25 = Bm25Retriever(chunks)
    return bm25 if method == "bm25" else HybridRetriever(dense, bm25)
