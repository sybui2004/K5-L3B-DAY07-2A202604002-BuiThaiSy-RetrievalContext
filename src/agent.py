"""Agent loop around any retriever: search -> pack context -> cited answer or abstention, with full traces."""
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .llm import LlmError

ABSTAIN_TEXT = "Không đủ bằng chứng để trả lời."
INSUFFICIENT_MARK = "không đủ bằng chứng"


@dataclass(frozen=True)
class AgentConfig:
    name: str
    method: str            # dense | bm25 | bm25-bigram | hybrid
    top_k: int
    max_searches: int
    budget_chars: int
    neighbors: bool        # add chunks of the adjacent Điều (same document) to the candidates
    rewrite: bool          # prompt hint: reformulate into legal wording / split multi-part questions
    pack: str = "order"    # order: candidates in arrival order | round_robin: rank-interleave the search rounds
    figure_reader: bool = False  # bonus only: ask a vision model the question about retrieved figure crops


def pack_context(candidates: list[dict], budget: int) -> tuple[str, list[str]]:
    blocks, ids, seen = [], [], set()
    for c in candidates:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        block = f"[{c['id']} | {c['source']} | page {c['page']}]\n{c['text']}"
        if len("\n\n".join(blocks + [block])) <= budget:
            blocks.append(block)
            ids.append(c["id"])
    return "\n\n".join(blocks), ids


def interleave_rounds(rounds: list[list[dict]]) -> list[dict]:
    """Rank 1 of every round, then rank 2 of every round, ... so a later search is not starved by earlier ones."""
    out = []
    for i in range(max((len(r) for r in rounds), default=0)):
        out += [r[i] for r in rounds if i < len(r)]
    return out


def _neighbors(results: list[dict], all_chunks: list[dict]) -> list[dict]:
    wanted = set()
    for r in results:
        dieu = r["metadata"].get("dieu")
        if dieu is not None:
            wanted |= {(r["source_id"], dieu - 1), (r["source_id"], dieu + 1)}
    return [c for c in all_chunks if (c["source_id"], c["metadata"].get("dieu")) in wanted]


def _scrub(text: str, secrets: list[str]) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "<hidden>")
    return text


def run_question(q: dict, cfg: AgentConfig, retriever, controller, *, all_chunks: list[dict],
                 secrets: list[str] | None = None, enrich=None) -> dict[str, Any]:
    """Run one question. Only the question text and the user-provided filter reach the agent (never gold).
    `enrich(question, results) -> results` may add question-specific evidence (e.g. reading a figure image)."""
    question, filters = q["question"], q.get("filter")
    secrets = secrets or []
    trace: dict[str, Any] = {"query_id": q["id"], "split": q["split"], "config": cfg.name, "status": "error",
                             "answer": None, "citations": [], "events": [], "searches": 0, "context": "",
                             "context_ids": [], "error": None}
    t0 = time.perf_counter()
    rounds: list[list[dict]] = []
    history: list[dict] = []
    controller.pop_usage()
    try:
        for _ in range(cfg.max_searches + 1):
            action = controller.decide(question, history, allow_search=trace["searches"] < cfg.max_searches)
            if action["action"] == "search":
                if trace["searches"] >= cfg.max_searches:
                    trace.update(status="abstain", answer=ABSTAIN_TEXT)
                    trace["events"].append({"event": "search_limit"})
                    break
                results = retriever.search(action["query"], filters=filters, top_k=cfg.top_k)
                trace["searches"] += 1
                if enrich:
                    results = enrich(question, results)
                rounds.append(results + (_neighbors(results, all_chunks) if cfg.neighbors else []))
                candidates = interleave_rounds(rounds) if cfg.pack == "round_robin" else sum(rounds, [])
                trace["context"], trace["context_ids"] = pack_context(candidates, cfg.budget_chars)
                trace["events"].append({"event": "search", "query": action["query"], "filter": filters,
                                        "results": [{"id": r["id"], "score": r.get("score"), "page": r["page"]}
                                                    for r in results],
                                        "context_ids": list(trace["context_ids"])})
                history = [{"tool": "search",
                            "queries": [e["query"] for e in trace["events"] if e["event"] == "search"],
                            "context": trace["context"], "context_ids": trace["context_ids"]}]
            else:
                answer, cites = action["answer"], action["citations"]
                ok = bool(answer.strip() and cites and all(c in trace["context_ids"] and f"[{c}]" in answer
                                                           for c in cites))
                if ok and INSUFFICIENT_MARK in answer.lower():
                    # The model says it lacks evidence but still cites chunks to explain why: that is a refusal.
                    trace.update(status="abstain", answer=ABSTAIN_TEXT, raw_answer=answer)
                    trace["events"].append({"event": "insufficient_evidence"})
                elif ok:
                    trace.update(status="answered", answer=answer, citations=cites)
                    trace["events"].append({"event": "answer"})
                else:
                    reason = "answered_without_search" if not trace["searches"] else "no_valid_citation"
                    trace.update(status="abstain", answer=ABSTAIN_TEXT, raw_answer=answer)
                    trace["events"].append({"event": reason})
                break
        else:
            trace.update(status="abstain", answer=ABSTAIN_TEXT)
    except Exception as e:  # noqa: BLE001 - recorded, never silently replaced by fake output
        trace.update(status="error", answer=None, error=_scrub(f"{type(e).__name__}: {e}", secrets)[:300])
        if isinstance(e, LlmError):
            trace["error"] = _scrub(str(e), secrets)[:300]
    usage = controller.pop_usage()
    trace.update(seconds=round(time.perf_counter() - t0, 2), tokens_in=usage["tokens_in"],
                 tokens_out=usage["tokens_out"], llm_calls=usage["calls"])
    return trace


def run_batch(questions: list[dict], cfg: AgentConfig, retriever, controller, out_dir, *,
              all_chunks: list[dict], secrets: list[str] | None = None, enrich=None) -> list[dict]:
    out = Path(out_dir)
    if (out / "traces.json").exists():
        raise FileExistsError(f"{out}/traces.json exists; use a new output dir per config/run")
    traces = [run_question(q, cfg, retriever, controller, all_chunks=all_chunks, secrets=secrets, enrich=enrich)
              for q in questions]
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.json").write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "traces.json").write_text(json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")
    return traces
