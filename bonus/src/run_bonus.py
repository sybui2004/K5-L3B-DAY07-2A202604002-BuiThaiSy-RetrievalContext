"""Run the DeepSeek agent over the HELM benchmark: python -m bonus.src.run_bonus --config bonus/configs/final.json ..."""
import argparse
import json
from pathlib import Path

from src.agent import AgentConfig, run_batch
from src.benchmark import is_answerable, load_questions
from src.config import load_config
from src.eval_retrieval import ensure_split_allowed
from src.llm import DeepSeekController
from .prompts import MULTI_PART_HINT, SYSTEM_PROMPT
from .store import build_retriever, load_chunks
from .vlm import FigureReader, ask_figure


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--split", default="dev", choices=["dev", "retired", "test"])
    p.add_argument("--final", action="store_true")
    p.add_argument("--questions", default="bonus/benchmark/questions.json")
    p.add_argument("--freeze", default="bonus/benchmark/freeze.json")
    p.add_argument("--out", required=True)
    p.add_argument("--vlm", default="qwen2.5vl:7b", help="local vision model used when the config sets figure_reader")
    a = p.parse_args(argv)
    ensure_split_allowed(a.split, a.final, a.questions, a.freeze)
    acfg = AgentConfig(**json.loads(Path(a.config).read_text(encoding="utf-8")))
    cfg = load_config()
    qs = [q for q in load_questions(a.questions) if q["split"] == a.split]
    chunks = load_chunks(cfg)
    prompt = SYSTEM_PROMPT + (MULTI_PART_HINT if acfg.rewrite else "")
    controller = DeepSeekController(cfg, system_prompt=prompt, max_tokens=1800)
    reader = None
    if acfg.figure_reader:
        reader = FigureReader(lambda img, q: ask_figure(img, q, a.vlm), model=a.vlm)
    traces = run_batch(qs, acfg, build_retriever(acfg.method, cfg, chunks), controller, a.out, all_chunks=chunks,
                       secrets=[cfg.deepseek_api_key, cfg.database_url], enrich=reader)
    by_id = {c["id"]: c for c in chunks}
    rows = []
    for t in traces:  # evidence region of every cited chunk, for manual checking against the PDF
        t["citation_regions"] = [{"id": c, "page": by_id[c]["page"], "kind": by_id[c]["metadata"]["kind"],
                                  "bbox": by_id[c]["metadata"]["bbox"], "image": by_id[c]["metadata"]["image_path"]}
                                 for c in t["citations"] if c in by_id]
    (Path(a.out) / "traces.json").write_text(json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"config": acfg.name, "split": a.split, "n_questions": len(qs),
               "status_counts": {s: sum(t["status"] == s for t in traces) for s in sorted({t["status"] for t in traces})},
               "errors": sum(t["status"] == "error" for t in traces),
               "tokens_in": sum(t["tokens_in"] for t in traces), "tokens_out": sum(t["tokens_out"] for t in traces),
               "seconds_total": round(sum(t["seconds"] for t in traces), 2), "model": cfg.deepseek_model,
               "figure_reader": ({"model": a.vlm, "calls": reader.calls, "failures": reader.failures}
                                 if reader else None)}
    (Path(a.out) / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
