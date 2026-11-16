"""Retrievers sharing the protocol search(query, *, filters, top_k) -> list[chunk dict with score]."""
import unicodedata
from typing import Any, Callable

import psycopg

from .config import Config
from .embed import embed_query
from .store_day6 import _COLS, VERSIONS, row_to_chunk


def normalize_query(query: str) -> str:
    q = unicodedata.normalize("NFC", query or "").strip()
    if not q:
        raise ValueError("query must be a non-empty string")
    return q


def check_filters(filters: dict[str, Any] | None) -> str | None:
    """Return the version filter or None; reject anything we do not support."""
    if not filters:
        return None
    if set(filters) != {"version"} or filters["version"] not in VERSIONS:
        raise ValueError(f"unsupported filter {filters!r}; only version in {sorted(VERSIONS)}")
    return filters["version"]


def _vec(v: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in v) + "]"


def _query_db(cfg: Config, sql: str, params: list) -> list[tuple]:
    """Run one read query; turn connection/query failures into a RuntimeError that never echoes DATABASE_URL."""
    try:
        with psycopg.connect(cfg.database_url, connect_timeout=10) as conn:
            return conn.execute(sql, params).fetchall()
    except psycopg.OperationalError as e:
        raise RuntimeError(f"vector store unavailable (check Postgres on DATABASE_URL): {type(e).__name__}") from e
    except psycopg.Error as e:
        raise RuntimeError(f"vector store query failed: {type(e).__name__}") from e


class DenseRetriever:
    """Cosine search over a Day 6 table (exact search, as in Day 6)."""

    def __init__(self, cfg: Config, table: str = "chunks_b",
                 embed: Callable[[str, Config], list[float]] = embed_query) -> None:
        if table not in {"chunks_a", "chunks_b", "chunks_c"}:
            raise ValueError(f"unexpected table {table!r}")
        self.cfg, self.table, self.embed = cfg, table, embed

    def search(self, query: str, *, filters: dict[str, Any] | None, top_k: int) -> list[dict]:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        version = check_filters(filters)
        q = normalize_query(query)
        vec = _vec(self.embed(q, self.cfg))
        where = "WHERE version = %s" if version else ""
        params = [vec] + ([version] if version else []) + [vec, top_k]
        sql = (f"SELECT {_COLS}, 1 - (embedding <=> %s::vector) AS score FROM {self.table} {where} "
               f"ORDER BY embedding <=> %s::vector LIMIT %s")
        rows = _query_db(self.cfg, sql, params)
        out = []
        for r in rows:
            chunk = row_to_chunk(r[:-1])
            chunk["score"] = float(r[-1])
            out.append(chunk)
        return out


class Bm25Retriever:
    """BM25 over in-memory chunks (Day 6 chunk_b export). Only chunks with score > 0 are returned."""

    def __init__(self, chunks: list[dict], tokenizer: Callable[[str], list[str]] | None = None) -> None:
        from rank_bm25 import BM25Okapi
        from .tokenize_vi import tokenize_whitespace
        self.chunks = chunks
        self.tokenizer = tokenizer or tokenize_whitespace
        self.index = BM25Okapi([self.tokenizer(c["text"]) for c in chunks])

    def search(self, query: str, *, filters: dict[str, Any] | None, top_k: int) -> list[dict]:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        version = check_filters(filters)
        q = normalize_query(query)
        scores = self.index.get_scores(self.tokenizer(q))
        ranked = sorted(range(len(self.chunks)), key=lambda i: scores[i], reverse=True)
        out = []
        for i in ranked:
            c = self.chunks[i]
            if scores[i] <= 0:
                break
            if version and c["metadata"].get("version") != version:
                continue
            out.append({**c, "score": float(scores[i])})
            if len(out) == top_k:
                break
        return out


class HybridRetriever:
    """Reciprocal Rank Fusion of a dense and a lexical retriever (score = sum 1/(k + rank))."""

    def __init__(self, dense, lexical, k: int = 60, pool: int = 20) -> None:
        self.dense, self.lexical, self.k, self.pool = dense, lexical, k, pool

    def search(self, query: str, *, filters: dict[str, Any] | None, top_k: int) -> list[dict]:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        fused: dict[str, dict] = {}
        for retriever in (self.dense, self.lexical):
            for rank, chunk in enumerate(retriever.search(query, filters=filters, top_k=self.pool), start=1):
                entry = fused.setdefault(chunk["id"], {**chunk, "score": 0.0})
                entry["score"] += 1.0 / (self.k + rank)
        return sorted(fused.values(), key=lambda c: c["score"], reverse=True)[:top_k]


RERANK_MODEL = "BAAI/bge-reranker-v2-m3"


def cross_encoder_scorer(model_name: str = RERANK_MODEL) -> Callable[[str, list[str]], list[float]]:
    """Local cross-encoder: scores each (query, passage) pair jointly. The model is loaded on first use."""
    state: dict = {}

    def score(query: str, texts: list[str]) -> list[float]:
        if "model" not in state:
            from sentence_transformers import CrossEncoder
            state["model"] = CrossEncoder(model_name, max_length=512)
        return [float(s) for s in state["model"].predict([(query, t) for t in texts], batch_size=8)]

    return score


class RerankRetriever:
    """Fetch a larger candidate pool from `base`, re-score every candidate with a cross-encoder, keep top_k."""

    def __init__(self, base, scorer: Callable[[str, list[str]], list[float]] | None = None, pool: int = 20) -> None:
        self.base, self.scorer, self.pool = base, scorer or cross_encoder_scorer(), pool

    def search(self, query: str, *, filters: dict[str, Any] | None, top_k: int) -> list[dict]:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        q = normalize_query(query)
        cands = self.base.search(q, filters=filters, top_k=max(self.pool, top_k))
        if not cands:
            return []
        scores = self.scorer(q, [c["text"] for c in cands])
        ranked = sorted(zip(cands, scores), key=lambda p: p[1], reverse=True)[:top_k]
        return [{**c, "score": s} for c, s in ranked]
