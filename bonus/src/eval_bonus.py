"""Automatic context metrics + manual pass/fail sheets and the final scoring for the HELM bonus.

    python -m bonus.src.eval_bonus sheets --run bonus/results/<run>      # writes blank audit/pass_fail.csv
    python -m bonus.src.eval_bonus score  --run bonus/results/<run>      # reads the filled sheet, prints n/N
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from src.benchmark import hit, is_answerable, load_questions

COLS = ["query_id", "group", "question", "expected_answer", "status", "answer", "citations", "cited_regions",
        "context_has_all_evidence", "pass_fail", "reason"]


def context_has_all(trace: dict, q: dict, chunks_by_id: dict) -> bool:
    ids = [i for i in trace.get("context_ids", []) if i in chunks_by_id]
    return all(any(hit(chunks_by_id[i], [g]) for i in ids) for g in q["gold"])


def context_evidence_rate(traces, questions, chunks_by_id) -> dict:
    by_id = {t["query_id"]: t for t in traces}
    out = defaultdict(lambda: [0, 0])
    for q in questions:
        if not is_answerable(q) or q["id"] not in by_id:
            continue
        ok = context_has_all(by_id[q["id"]], q, chunks_by_id)
        for key in ("all", q["group"]):
            out[key][0] += ok
            out[key][1] += 1
    return {k: {"n": v[0], "N": v[1]} for k, v in out.items()}


def write_sheet(run_dir, questions, chunks_by_id) -> Path:
    run = Path(run_dir)
    traces = json.loads((run / "traces.json").read_text(encoding="utf-8"))
    qs = {q["id"]: q for q in questions}
    rows = []
    for t in traces:
        q = qs[t["query_id"]]
        expected = q.get("expected_answer") or f"(NOT ANSWERABLE: {q.get('absence_reason', '')})"
        regions = "; ".join(f"{r['id']} p{r['page']} {r['kind']}" + (f" bbox={r['bbox']}" if r["bbox"] else "")
                            for r in t.get("citation_regions", []))
        rows.append({"query_id": t["query_id"], "group": q["group"], "question": q["question"],
                     "expected_answer": expected, "status": t["status"], "answer": t["answer"] or t.get("error") or "",
                     "citations": ";".join(t["citations"]), "cited_regions": regions,
                     "context_has_all_evidence": context_has_all(t, q, chunks_by_id) if is_answerable(q) else "n/a"})
    out = run / "audit" / "pass_fail.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows({c: r.get(c, "") for c in COLS} for r in rows)
    return out


def score(run_dir, questions) -> dict:
    run = Path(run_dir)
    traces = {t["query_id"]: t for t in json.loads((run / "traces.json").read_text(encoding="utf-8"))}
    labels = {}
    with open(run / "audit" / "pass_fail.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            v = r["pass_fail"].strip().lower()
            if v not in {"pass", "fail"}:
                raise ValueError(f"{r['query_id']}: pass_fail must be 'pass' or 'fail', got {r['pass_fail']!r}")
            labels[r["query_id"]] = v
    split_q = [q for q in questions if q["id"] in traces]
    missing = [q["id"] for q in split_q if q["id"] not in labels]
    if missing:
        raise ValueError(f"unlabelled questions: {missing}")
    groups = defaultdict(lambda: [0, 0])
    for q in split_q:
        # system errors, timeouts and empty results count as fail and stay in the denominator
        ok = labels[q["id"]] == "pass" and traces[q["id"]]["status"] != "error"
        for key in ("all", q["group"]):
            groups[key][0] += ok
            groups[key][1] += 1
    n, N = groups["all"]
    return {"pass": f"{n}/{N}", "rate_percent": round(100 * n / N, 2), "meets_90_percent": n * 10 >= N * 9,
            "by_group": {k: f"{v[0]}/{v[1]}" for k, v in sorted(groups.items()) if k != "all"},
            "errors": sum(t["status"] == "error" for t in traces.values()),
            "tokens_in": sum(t["tokens_in"] for t in traces.values()),
            "tokens_out": sum(t["tokens_out"] for t in traces.values()),
            "seconds_total": round(sum(t["seconds"] for t in traces.values()), 1)}


def main(argv=None) -> int:
    from src.config import load_config
    from .store import load_chunks
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["sheets", "score"])
    p.add_argument("--run", required=True)
    p.add_argument("--questions", default="bonus/benchmark/questions.json")
    a = p.parse_args(argv)
    qs = load_questions(a.questions)
    if a.command == "sheets":
        chunks = {c["id"]: c for c in load_chunks(load_config())}
        print(write_sheet(a.run, qs, chunks))
        return 0
    res = score(a.run, qs)
    (Path(a.run) / "pass_fail_metrics.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
