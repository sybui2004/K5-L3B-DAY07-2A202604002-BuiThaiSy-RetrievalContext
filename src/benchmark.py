"""Benchmark loading, Day 6 conversion, evidence matching (Day 6 rules) and validation."""
import json
import re
import unicodedata
from pathlib import Path

MIN_ANSWERABLE = {"dev": 15, "test": 5}
MIN_UNANSWERABLE = {"dev": 2, "test": 2}
MIN_EVIDENCE_CHARS = 30


def norm(text: str) -> str:
    """NFC + lowercase + drop all whitespace, so syllable-splitting glitches do not break matching."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", text).casefold())


def is_answerable(q: dict) -> bool:
    return q.get("answerable", True) is not False


def hit(chunk: dict, gold: list[dict]) -> bool:
    """Chunk is a hit if it is from a gold source, its page range covers the gold page and it holds the evidence."""
    start = chunk["page"]
    end = chunk.get("metadata", {}).get("page_end") or start
    text = norm(chunk["text"])
    return any(chunk["source_id"] == g["source_id"] and start <= g["page"] <= end and norm(g["evidence"]) in text
               for g in gold)


def convert_day6_question(q: dict) -> dict:
    gold = [{"source_id": q["gold_source_id"], "page": q["gold_page"], "evidence": q["evidence_quote"]}]
    gold += [{"source_id": a["source_id"], "page": a["page"], "evidence": a["evidence_quote"]}
             for a in q.get("alt_gold", [])]
    return {"id": q["id"], "split": q["split"], "type": q.get("type"), "question": q["question"],
            "expected_answer": q["expected_answer"], "gold": gold, "filter": q.get("filter")}


def load_questions(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(questions: list[dict], chunks: list[dict]) -> list[str]:
    problems: list[str] = []
    ids = [q["id"] for q in questions]
    problems += [f"duplicate id {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    for split in ("dev", "test"):
        qs = [q for q in questions if q["split"] == split]
        n_ans = sum(is_answerable(q) for q in qs)
        n_un = len(qs) - n_ans
        if n_ans < MIN_ANSWERABLE[split]:
            problems.append(f"{split}: only {n_ans} answerable (< {MIN_ANSWERABLE[split]})")
        if n_un < MIN_UNANSWERABLE[split]:
            problems.append(f"{split}: only {n_un} unanswerable (< {MIN_UNANSWERABLE[split]})")
    corpus = norm(" ".join(c["text"] for c in chunks))
    for q in questions:
        if is_answerable(q):
            if not any(len(norm(g["evidence"])) >= MIN_EVIDENCE_CHARS and
                       any(hit(c, [g]) for c in chunks) for g in q["gold"]):
                problems.append(f"{q['id']}: evidence not found in a chunk of its gold source/page")
        else:
            for phrase in q.get("key_phrases", []):
                if norm(phrase) in corpus:
                    problems.append(f"{q['id']}: key phrase found in corpus, question may be answerable")
    return problems


def file_sha256(path: str | Path) -> str:
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_freeze(questions_path: str | Path, freeze_path: str | Path) -> None:
    Path(freeze_path).write_text(json.dumps({"questions_sha256": file_sha256(questions_path)}, indent=2),
                                 encoding="utf-8")


def check_freeze(questions_path: str | Path, freeze_path: str | Path) -> bool:
    try:
        saved = json.loads(Path(freeze_path).read_text(encoding="utf-8"))["questions_sha256"]
    except (OSError, KeyError, ValueError):
        return False
    return saved == file_sha256(questions_path)


def main(argv: list[str] | None = None) -> int:
    import argparse
    from .config import load_config
    from .store_day6 import load_day6_chunks
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["validate", "freeze"])
    p.add_argument("--questions", default="benchmark/questions.json")
    p.add_argument("--freeze", default="benchmark/freeze.json")
    a = p.parse_args(argv)
    if a.command == "freeze":
        write_freeze(a.questions, a.freeze)
        print("frozen", file_sha256(a.questions))
        return 0
    problems = validate(load_questions(a.questions), load_day6_chunks(load_config()))
    print("\n".join(problems) if problems else "0 problems")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
