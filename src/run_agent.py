"""CLI: run the DeepSeek agent for one config on one split; write traces, summary and blank audit sheets."""
import argparse
import json
from collections import Counter
from pathlib import Path

from .agent import AgentConfig, run_batch
from .audit_sheets import write_audit_sheets
from .benchmark import is_answerable, load_questions
from .eval_agent import agent_hit_at_k, context_evidence_rate, to_agent_metrics_inputs, tool_use_stats
from .eval_retrieval import build_retriever, ensure_split_allowed

METHODS = {"dense", "bm25", "bm25-bigram", "hybrid", "dense-rerank", "hybrid-rerank"}


def load_agent_config(path) -> AgentConfig:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("method") not in METHODS:
        raise ValueError(f"unknown method {d.get('method')!r}")
    return AgentConfig(**d)


def summarize_run(traces: list[dict], questions: list[dict], chunks_by_id: dict) -> dict:
    return {"n_questions": len(traces),
            "status_counts": dict(Counter(t["status"] for t in traces)),
            "context_evidence_rate": context_evidence_rate(traces, questions, chunks_by_id),
            "first_search_hits": agent_hit_at_k(traces, questions, chunks_by_id),
            "tool_use": tool_use_stats(traces),
            "tokens_in": sum(t["tokens_in"] for t in traces), "tokens_out": sum(t["tokens_out"] for t in traces),
            "seconds_total": round(sum(t["seconds"] for t in traces), 2)}


def main(argv=None) -> int:
    from .config import load_config
    from .llm import DeepSeekController
    from .prompts import build_system_prompt
    from .store_day6 import load_day6_chunks
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--split", default="dev", choices=["dev", "test"])
    p.add_argument("--final", action="store_true")
    p.add_argument("--questions", default="benchmark/questions.json")
    p.add_argument("--freeze", default="benchmark/freeze.json")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    ensure_split_allowed(a.split, a.final, a.questions, a.freeze)
    acfg, cfg = load_agent_config(a.config), load_config()
    qs = [q for q in load_questions(a.questions) if q["split"] == a.split]
    chunks = load_day6_chunks(cfg)
    controller = DeepSeekController(cfg, system_prompt=build_system_prompt(acfg.rewrite))
    traces = run_batch(qs, acfg, build_retriever(acfg.method, cfg), controller, a.out, all_chunks=chunks,
                       secrets=[cfg.deepseek_api_key, cfg.database_url])
    summary = summarize_run(traces, qs, {c["id"]: c for c in chunks}) | {"config": acfg.name, "split": a.split,
                                                                           "model": cfg.deepseek_model}
    out = Path(a.out)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_audit_sheets(traces, qs, out / "audit")
    to_agent_metrics_inputs(traces, qs, out / "metrics_inputs")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
