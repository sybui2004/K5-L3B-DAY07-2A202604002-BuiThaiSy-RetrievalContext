"""Chạy agent thật và so sánh retrieval cho tab Live (không import streamlit)."""
import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Callable

from src.agent import AgentConfig, _scrub, run_question
from .traces import Dataset, DATASETS

METHODS = {"basic": ("dense", "bm25", "bm25-bigram", "hybrid", "dense-rerank", "hybrid-rerank"), "bonus": ("dense", "bm25", "hybrid")}
_CACHE: dict[tuple, Any] = {}


def list_configs(ds: Dataset, root: Path = Path(".")) -> dict[str, AgentConfig]:
    allowed = {f.name for f in fields(AgentConfig)}
    out = {}
    for p in sorted((Path(root) / ds.configs_dir).glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            out[data.get("name", p.stem)] = AgentConfig(**{k: v for k, v in data.items() if k in allowed})
        except (OSError, ValueError, TypeError):
            continue
    return out


def dev_questions(ds: Dataset, root: Path = Path(".")) -> list[dict]:
    qs = json.loads((Path(root) / ds.questions_path).read_text(encoding="utf-8"))
    return [q for q in qs if q.get("split") == "dev"]


def _env_secrets() -> list[str]:
    return [os.environ.get(v, "") for v in ("DEEPSEEK_API_KEY", "DATABASE_URL")]


def _load_chunks(ds_key: str, cfg) -> list[dict]:
    key = ("chunks", ds_key)
    if key not in _CACHE:
        if ds_key == "bonus":
            from bonus.src.store import load_chunks
        else:
            from src.store_day6 import load_day6_chunks as load_chunks
        _CACHE[key] = load_chunks(cfg)
    return _CACHE[key]


def _build_retriever(ds_key: str, method: str, cfg):
    key = ("retriever", ds_key, method)
    if key not in _CACHE:
        if ds_key == "bonus":
            from bonus.src.store import build_retriever
            _CACHE[key] = build_retriever(method, cfg, _load_chunks(ds_key, cfg))
        else:
            from src.eval_retrieval import build_retriever
            _CACHE[key] = build_retriever(method, cfg)
    return _CACHE[key]


def _make_controller(ds_key: str, cfg, acfg: AgentConfig):
    from src.llm import DeepSeekController
    if ds_key == "bonus":
        from bonus.src.prompts import MULTI_PART_HINT, SYSTEM_PROMPT
        return DeepSeekController(cfg, system_prompt=SYSTEM_PROMPT + (MULTI_PART_HINT if acfg.rewrite else ""),
                                  max_tokens=1800)
    from src.prompts import build_system_prompt
    return DeepSeekController(cfg, system_prompt=build_system_prompt(acfg.rewrite))


def _load_config():
    from src.config import load_config
    return load_config()


@dataclass
class LiveDeps:
    load_config: Callable[[], Any] = _load_config
    build_retriever: Callable[[str, str, Any], Any] = _build_retriever
    load_chunks: Callable[[str, Any], list[dict]] = _load_chunks
    make_controller: Callable[[str, Any, AgentConfig], Any] = _make_controller
    secrets: Callable[[], list[str]] = field(default=_env_secrets)


def _error_trace(question: str, cfg_name: str, exc: Exception, secrets: list[str]) -> dict:
    return {"query_id": "live", "split": "live", "config": cfg_name, "status": "error", "answer": None,
            "citations": [], "events": [], "searches": 0, "context": "", "context_ids": [],
            "error": _scrub(f"{type(exc).__name__}: {exc}", secrets)[:300], "seconds": 0.0, "tokens_in": 0,
            "tokens_out": 0, "llm_calls": 0}


def run_live(ds_key: str, question: str, cfg: AgentConfig, *, filters: dict | None = None,
             deps: "LiveDeps | None" = None) -> dict:
    deps = deps or LiveDeps()
    secrets = [s for s in deps.secrets() if s]
    try:
        env = deps.load_config()
        secrets += [env.deepseek_api_key, env.database_url]
        retriever = deps.build_retriever(ds_key, cfg.method, env)
        chunks = deps.load_chunks(ds_key, env) if (ds_key == "bonus" or cfg.neighbors) else []
        controller = deps.make_controller(ds_key, env, cfg)
    except Exception as e:  # noqa: BLE001 - shown in the UI as an error trace, never a traceback
        return _error_trace(question, cfg.name, e, secrets)
    q = {"id": "live", "split": "live", "question": question, "filter": (filters or None)}
    trace = run_question(q, cfg, retriever, controller, all_chunks=chunks, secrets=secrets)
    if ds_key == "bonus":
        by_id = {c["id"]: c for c in chunks}
        trace["citation_regions"] = [
            {"id": c, "page": by_id[c]["page"], "kind": by_id[c]["metadata"].get("kind"),
             "bbox": by_id[c]["metadata"].get("bbox"), "image": by_id[c]["metadata"].get("image_path")}
            for c in trace["citations"] if c in by_id]
    return trace


def compare_methods(ds_key: str, question: str, *, top_k: int = 3, filters: dict | None = None,
                    deps: "LiveDeps | None" = None) -> dict[str, list[dict] | str]:
    deps = deps or LiveDeps()
    secrets = [s for s in deps.secrets() if s]
    out: dict[str, list[dict] | str] = {}
    try:
        env = deps.load_config()
        secrets += [env.deepseek_api_key, env.database_url]
    except Exception as e:  # noqa: BLE001
        msg = _scrub(f"{type(e).__name__}: {e}", secrets)[:300]
        return {m: msg for m in METHODS[ds_key]}
    for m in METHODS[ds_key]:
        try:
            res = deps.build_retriever(ds_key, m, env).search(question, filters=(filters or None), top_k=top_k)
            out[m] = [{"rank": i, "id": r["id"], "score": r.get("score"), "page": r["page"]}
                      for i, r in enumerate(res, start=1)]
        except Exception as e:  # noqa: BLE001
            out[m] = _scrub(f"{type(e).__name__}: {e}", secrets)[:300]
    return out


def rrf_breakdown(ds_key: str, question: str, *, top_k: int = 8, filters: dict | None = None,
                  deps: "LiveDeps | None" = None) -> list[dict] | str:
    """Phân rã điểm RRF của hybrid: hạng và điểm 1/(k+hạng) của dense và của từ khóa, rồi tổng."""
    deps = deps or LiveDeps()
    secrets = [s for s in deps.secrets() if s]
    try:
        env = deps.load_config()
        secrets += [env.deepseek_api_key, env.database_url]
        hybrid = deps.build_retriever(ds_key, "hybrid", env)
        k, pool = hybrid.k, hybrid.pool
        fused: dict[str, dict] = {}
        for side, retriever in (("dense", hybrid.dense), ("lexical", hybrid.lexical)):
            for rank, c in enumerate(retriever.search(question, filters=(filters or None), top_k=pool), start=1):
                row = fused.setdefault(c["id"], {"id": c["id"], "page": c["page"], "dense_rank": None,
                                                 "lexical_rank": None, "rrf_dense": 0.0, "rrf_lexical": 0.0})
                row[f"{side}_rank"] = rank
                row[f"rrf_{side}"] = 1.0 / (k + rank)
        for row in fused.values():
            row["score"] = row["rrf_dense"] + row["rrf_lexical"]
        return sorted(fused.values(), key=lambda r: r["score"], reverse=True)[:top_k]
    except Exception as e:  # noqa: BLE001
        return _scrub(f"{type(e).__name__}: {e}", secrets)[:300]


def rerank_breakdown(ds_key: str, question: str, *, top_k: int = 3, filters: dict | None = None,
                     method: str = "hybrid-rerank", deps: "LiveDeps | None" = None) -> list[dict] | str:
    """Hạng của từng chunk trước rerank (retriever gốc, top-pool) và sau rerank, kèm điểm cross-encoder."""
    deps = deps or LiveDeps()
    secrets = [s for s in deps.secrets() if s]
    try:
        env = deps.load_config()
        secrets += [env.deepseek_api_key, env.database_url]
        rr = deps.build_retriever(ds_key, method, env)
        cands = rr.base.search(question, filters=(filters or None), top_k=max(rr.pool, top_k))
        scores = rr.scorer(question, [c["text"] for c in cands])
        after = sorted(range(len(cands)), key=lambda i: scores[i], reverse=True)
        return [{"id": cands[i]["id"], "page": cands[i]["page"], "rank_before": i + 1, "rank_after": r,
                 "score": float(scores[i])} for r, i in enumerate(after[:top_k], start=1)]
    except Exception as e:  # noqa: BLE001
        return _scrub(f"{type(e).__name__}: {e}", secrets)[:300]
