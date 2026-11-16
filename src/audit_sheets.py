"""Blank manual-audit sheets (the author fills the score columns) and a parser for the filled sheet."""
import csv
import json
from pathlib import Path

from .benchmark import is_answerable

CONTEXT_COLS = ["query_id", "question", "expected_answer", "context_ids", "context",
                "context_score_0_2", "reason"]
ANSWER_COLS = ["query_id", "question", "expected_answer", "status", "answer", "citations",
               "answer_grade_0_2", "citation_support", "abstention_correct", "effective_status", "reason"]


def _write(path: Path, cols: list[str], rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows({c: r.get(c, "") for c in cols} for r in rows)


def write_audit_sheets(traces: list[dict], questions: list[dict], out_dir) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    qs = {q["id"]: q for q in questions}
    ctx_rows, ans_rows = [], []
    for t in traces:
        q = qs[t["query_id"]]
        expected = q.get("expected_answer") or f"(thiếu bằng chứng: {q.get('absence_reason', '')})"
        base = {"query_id": t["query_id"], "question": q["question"], "expected_answer": expected}
        if is_answerable(q):
            ctx_rows.append({**base, "context_ids": ";".join(t["context_ids"]), "context": t["context"]})
        ans_rows.append({**base, "status": t["status"], "answer": t["answer"] or t.get("error") or "",
                         "citations": ";".join(t["citations"])})
    _write(out / "context_audit.csv", CONTEXT_COLS, ctx_rows)
    _write(out / "answer_audit.csv", ANSWER_COLS, ans_rows)


def reviews_from_csv(path) -> list[dict]:
    """Parse the filled answer_audit.csv into the reviews.json shape of starter/agent_metrics.py."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    reviews = []
    for row in rows:
        qid = row["query_id"]
        support = [s.strip().lower() == "true" for s in row["citation_support"].split(";") if s.strip()]
        grade, abst = row["answer_grade_0_2"].strip(), row["abstention_correct"].strip().lower()
        if not grade and not abst:
            raise ValueError(f"{qid}: row has no label (answer_grade_0_2 or abstention_correct)")
        review = {"query_id": qid, "citation_support": support}
        if grade:
            review["answer_grade"] = int(grade)
        if abst:
            review["abstention_correct"] = abst == "true"
        if row.get("effective_status", "").strip():
            review["effective_status"] = row["effective_status"].strip()
        reviews.append(review)
    return reviews
