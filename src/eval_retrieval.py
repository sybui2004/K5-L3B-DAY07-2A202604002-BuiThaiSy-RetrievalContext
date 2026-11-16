"""Compare retrieval methods on the benchmark with original queries (Hit@1, Evidence Hit@3)."""
import argparse
import json
import time
from pathlib import Path

from .benchmark import check_freeze, hit, is_answerable, load_questions


def ensure_split_allowed(split: str, final: bool, questions_path, freeze_path) -> None:
    if split != "test":
        return
    if not final:
        raise PermissionError("the test split needs --final (config must be frozen first)")
    if not check_freeze(questions_path, freeze_path):
        raise PermissionError("benchmark/freeze.json is missing or does not match questions.json")


def run_retrieval_eval(retriever, questions: list[dict], *, top_k: int = 3, split: str = "dev") -> dict:
    rows, hit1, hit3, n = [], 0, 0, 0
    for q in questions:
        if q["split"] != split:
            continue
        t0 = time.perf_counter()
        results = retriever.search(q["question"], filters=q.get("filter"), top_k=top_k)
        seconds = time.perf_counter() - t0
        row = {"id": q["id"], "query": q["question"], "filter": q.get("filter"), "seconds": round(seconds, 3),
               "results": [], "rank_of_first_hit": None, "answerable": is_answerable(q)}
        flags = [hit(c, q["gold"]) for c in results] if row["answerable"] else []
        for rank, c in enumerate(results, start=1):
            row["results"].append({"id": c["id"], "score": c.get("score"), "page": c["page"],
                                   "hit": flags[rank - 1] if flags else None})
        if row["answerable"]:
            n += 1
            first = next((i + 1 for i, f in enumerate(flags) if f), None)
            row["rank_of_first_hit"] = first
            hit1 += first == 1
            hit3 += first is not None and first <= 3
        rows.append(row)
    return {"split": split, "top_k": top_k, "n": n, "hit1": hit1, "hit3": hit3,
            "seconds_total": round(sum(r["seconds"] for r in rows), 2), "rows": rows}


def build_retriever(method: str, cfg):
    from .retrievers import Bm25Retriever, DenseRetriever, HybridRetriever
    from .store_day6 import load_day6_chunks
    from .tokenize_vi import tokenize_syllable_bigrams
    if method == "dense":
        return DenseRetriever(cfg)
    if method == "dense-rerank":
        from .retrievers import RerankRetriever
        return RerankRetriever(DenseRetriever(cfg))
    chunks = load_day6_chunks(cfg)
    if method == "bm25":
        return Bm25Retriever(chunks)
    if method == "bm25-bigram":
        return Bm25Retriever(chunks, tokenizer=tokenize_syllable_bigrams)
    if method == "hybrid":
        return HybridRetriever(DenseRetriever(cfg), Bm25Retriever(chunks))
    if method == "hybrid-rerank":
        from .retrievers import RerankRetriever
        return RerankRetriever(HybridRetriever(DenseRetriever(cfg), Bm25Retriever(chunks)))
    raise ValueError(f"unknown method {method!r}")


def main(argv=None) -> int:
    from .config import load_config
    p = argparse.ArgumentParser()
    p.add_argument("--method", required=True, choices=["dense", "bm25", "bm25-bigram", "hybrid", "dense-rerank", "hybrid-rerank"])
    p.add_argument("--split", default="dev", choices=["dev", "test"])
    p.add_argument("--final", action="store_true")
    p.add_argument("--questions", default="benchmark/questions.json")
    p.add_argument("--freeze", default="benchmark/freeze.json")
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    ensure_split_allowed(a.split, a.final, a.questions, a.freeze)
    res = run_retrieval_eval(build_retriever(a.method, load_config()), load_questions(a.questions),
                             top_k=3, split=a.split)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "traces.json").write_text(json.dumps(res["rows"], ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {k: v for k, v in res.items() if k != "rows"} | {"method": a.method}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{a.method} {a.split}: Hit@1 {res['hit1']}/{res['n']}  Hit@3 {res['hit3']}/{res['n']}  {res['seconds_total']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
