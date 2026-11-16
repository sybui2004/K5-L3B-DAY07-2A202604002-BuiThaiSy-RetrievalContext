"""Check the HELM benchmark against the PDF: gold evidence strings are printed on the stated page, and the
terms that make the unanswerable questions unanswerable do not occur anywhere in the document.

    python -m bonus.src.validate
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf

from .extract import PDF

ABSENT = {"D19": ["GPT-4"], "D20": ["Alpaca"], "D21": ["Pythia"],
          "T28": ["LLaMA", "Llama"], "T29": ["Gemini"], "T30": ["ChatGPT"], "T31": ["Mistral"], "T32": ["Bard"],
          "T33": ["Vicuna"],
          "N28": ["Qwen"], "N29": ["Mixtral"], "N30": ["Gemma"], "N31": ["DeepSeek"],
          "N32": ["StableLM"], "N33": ["Dolly"],
          "M28": ["Falcon"], "M29": ["Yi-34B"], "M30": ["Grok"], "M31": ["Baichuan"], "M32": ["Phi-2"],
          "M33": ["Nemotron"]}


def norm(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", s.replace("\xad", ""))).casefold()


def main(path="bonus/benchmark/questions.json") -> int:
    doc = pymupdf.open(PDF)
    pages = [norm(p.get_text()) for p in doc]
    plain = " ".join(re.sub(r"\s+", " ", p.get_text()) for p in doc)
    problems = []
    for q in json.loads(Path(path).read_text(encoding="utf-8")):
        if q["answerable"]:
            if not q["gold"]:
                problems.append(f"{q['id']}: no gold")
            for gld in q["gold"]:
                if norm(gld["evidence"]) not in pages[gld["page"] - 1]:
                    problems.append(f"{q['id']}: {gld['evidence']!r} not on page {gld['page']}")
        else:
            for term in ABSENT.get(q["id"], []):
                if re.search(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", plain):
                    problems.append(f"{q['id']}: {term!r} occurs in the document")
            if q["id"] not in ABSENT:
                problems.append(f"{q['id']}: no absence terms registered")
    print("\n".join(problems) if problems else "0 problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
