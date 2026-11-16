"""Turn a run's hand-filled answer_audit.csv into the metrics of starter/agent_metrics.py."""
import argparse
import json
import sys
from pathlib import Path

from .audit_sheets import reviews_from_csv
from .benchmark import load_questions
from .eval_agent import to_agent_metrics_inputs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "starter"))
from agent_metrics import aggregate  # noqa: E402


def score_run(run_dir, questions: list[dict], split: str) -> dict:
    run = Path(run_dir)
    traces = json.loads((run / "traces.json").read_text(encoding="utf-8"))
    reviews = reviews_from_csv(run / "audit" / "answer_audit.csv")
    overrides = {r["query_id"]: r["effective_status"] for r in reviews if "effective_status" in r}
    to_agent_metrics_inputs(traces, questions, run / "metrics_inputs", status_overrides=overrides)
    cases = json.loads((run / "metrics_inputs" / "cases.json").read_text(encoding="utf-8"))
    eff = json.loads((run / "metrics_inputs" / "traces.json").read_text(encoding="utf-8"))
    reviews = [{k: v for k, v in r.items() if k != "effective_status"} for r in reviews]
    out = aggregate([c for c in cases if c["split"] == split], eff, reviews)
    (run / "agent_metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--split", required=True, choices=["dev", "test"])
    p.add_argument("--questions", default="benchmark/questions.json")
    a = p.parse_args(argv)
    print(json.dumps(score_run(a.run, load_questions(a.questions), a.split), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
