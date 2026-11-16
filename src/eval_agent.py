"""Automatic agent/context metrics from traces (human labels are collected separately)."""
import json
from collections import Counter
from pathlib import Path

from .benchmark import hit, is_answerable


def context_evidence_rate(traces: list[dict], questions: list[dict], chunks_by_id: dict[str, dict]) -> dict:
    """answerable questions whose final context holds a chunk that satisfies a gold entry / answerable questions."""
    by_id = {t["query_id"]: t for t in traces}
    n = N = 0
    for q in questions:
        if not is_answerable(q) or q["id"] not in by_id:
            continue
        N += 1
        ids = by_id[q["id"]].get("context_ids", [])
        n += any(i in chunks_by_id and hit(chunks_by_id[i], q["gold"]) for i in ids)
    return {"n": n, "N": N}


def agent_hit_at_k(traces: list[dict], questions: list[dict], chunks_by_id: dict[str, dict],
                   ks: tuple[int, ...] = (1, 3)) -> dict:
    """Hit@k of the agent's FIRST search (its own query, not the original question) over answerable questions.
    A question with no search event counts as a miss."""
    by_id = {t["query_id"]: t for t in traces}
    out = {f"hit@{k}": {"n": 0, "N": 0} for k in ks}
    for q in questions:
        if not is_answerable(q) or q["id"] not in by_id:
            continue
        first = next((e for e in by_id[q["id"]].get("events", []) if e.get("event") == "search"), None)
        ids = [r["id"] for r in first.get("results", [])] if first else []
        for k in ks:
            out[f"hit@{k}"]["N"] += 1
            out[f"hit@{k}"]["n"] += any(i in chunks_by_id and hit(chunks_by_id[i], q["gold"]) for i in ids[:k])
    return out


def tool_use_stats(traces: list[dict]) -> dict:
    ok = [t for t in traces if t["status"] != "error"]
    return {"n": sum(t["searches"] >= 1 for t in ok), "N": len(ok),
            "errors": len(traces) - len(ok), "distribution": dict(sorted(Counter(t["searches"] for t in ok).items()))}


def to_agent_metrics_inputs(traces: list[dict], questions: list[dict], out_dir,
                            status_overrides: dict[str, str] | None = None) -> None:
    """Write cases.json / traces.json in the shape expected by starter/agent_metrics.py."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cases = [{"id": q["id"], "split": q["split"], "answerable": is_answerable(q)} for q in questions
             if q["id"] in {t["query_id"] for t in traces}]
    ov = status_overrides or {}
    slim = [{"query_id": t["query_id"], "status": ov.get(t["query_id"], t["status"]), "trace_status": t["status"],
             "events": t["events"], "citations": t["citations"]} for t in traces]
    (out / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "traces.json").write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv=None) -> int:
    """Recompute the automatic metrics of a saved run from its traces (no LLM call) and store them in summary.json:
    python -m src.eval_agent --run results/agent/improve-b-dev --split dev"""
    import argparse
    from .benchmark import load_questions
    from .config import load_config
    from .store_day6 import load_day6_chunks
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--split", required=True, choices=["dev", "test"])
    p.add_argument("--questions", default="benchmark/questions.json")
    a = p.parse_args(argv)
    run = Path(a.run)
    traces = json.loads((run / "traces.json").read_text(encoding="utf-8"))
    qs = [q for q in load_questions(a.questions) if q["split"] == a.split]
    chunks = {c["id"]: c for c in load_day6_chunks(load_config())}
    summary_path = run / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["first_search_hits"] = agent_hit_at_k(traces, qs, chunks)
    summary["context_evidence_rate"] = context_evidence_rate(traces, qs, chunks)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"run": str(run), "first_search_hits": summary["first_search_hits"],
                      "context_evidence_rate": summary["context_evidence_rate"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
