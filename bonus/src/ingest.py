"""Index the HELM paper: text passages, tables (markdown) and figures (crop + in-figure text + VLM description).

    python -m bonus.src.ingest --vlm qwen2.5vl:7b            # full run (resumes from the description cache)
    python -m bonus.src.ingest --vlm qwen2.5vl:7b --pages 14-30   # partial run for testing (does not touch other pages)
"""
import argparse
import json
import re
import time
from pathlib import Path

import psycopg
import pymupdf
import requests

from src.config import load_config
from .extract import (FIG_DIR, PDF, boxplot_medians, figure_regions, medians_text, page_passages, page_tables, region_layout, region_text,
                      render_region, short_caption,
                      split_table)
from .vlm import describe

DESC_CACHE = Path("bonus/data/figure_descriptions.json")
STATS = Path("bonus/data/index_stats.json")
TABLE_SQL = """
CREATE TABLE IF NOT EXISTS helm_chunks (
  chunk_id text PRIMARY KEY, page int NOT NULL, kind text NOT NULL, label text, caption text,
  text text NOT NULL, bbox jsonb, image_path text, embedding vector(1024) NOT NULL)"""
# Lookup tables (model list, hardware, contamination): one chunk per row so a row is retrieved by its model name
# instead of sinking inside a 700-character block (round 4 failures D13, T01, T23, N20).
ROW_TABLES = {"Table 5", "Table 6", "Table 13"}
_WORDS = set("the of and to in for is are with on that this model models figure table accuracy metric scenario "
             "input output data from by as at be an or which each".split())


def _englishness(s: str) -> float:
    toks = re.findall(r"[a-z]+", s.lower())
    return sum(t in _WORDS for t in toks) / max(1, len(toks))


def fix_text(s: str) -> str:
    """Some figure fonts are embedded with codes shifted by 29 (',QSXW' = 'Input'); keep whichever reads as English."""
    if not s:
        return s
    shifted = _shift(s)
    return shifted if _englishness(shifted) > _englishness(s) else s


def _shift(s: str) -> str:
    return "".join(chr(ord(c) + 29) if 33 <= ord(c) <= 98 else c for c in s)


def figure_text(page, bbox) -> str:
    """In-figure text grouped by region. Only in figures detected as using the shifted font, a line is decoded
    when it has almost no lowercase letters and its decoded form is mostly lowercase (normal-font lines stay)."""
    raw = region_text(page, bbox)
    if not raw or fix_text(raw) == raw:
        return region_layout(page, bbox)
    return region_layout(page, bbox, transform=_fix_line)


def _lower_frac(s: str) -> float:
    vis = [c for c in s if not c.isspace()]
    return sum(c.islower() for c in vis) / max(1, len(vis))


def _fix_line(s: str) -> str:
    shifted = _shift(s)
    return shifted if _lower_frac(s) < 0.3 and _lower_frac(shifted) > 0.5 else s


def embed_docs(texts: list[str], cfg) -> list[list[float]]:
    out = []
    for i in range(0, len(texts), 16):
        batch = [t.replace(chr(0), " ")[:6000] for t in texts[i:i + 16]]
        for attempt in range(4):
            r = requests.post(f"{cfg.ollama_url}/api/embed", json={"model": cfg.embedding_model, "input": batch},
                              timeout=300)
            if r.status_code == 200:
                break
            time.sleep(3 * (attempt + 1))
        else:
            raise RuntimeError(f"embedding failed: HTTP {r.status_code} {r.text[:200]}")
        out += r.json()["embeddings"]
    return out


def page_range(spec: str | None, n: int) -> list[int]:
    if not spec:
        return list(range(1, n + 1))
    a, _, b = spec.partition("-")
    return list(range(int(a), int(b or a) + 1))


def build_chunks(doc, pages: list[int], vlm_model: str, use_vlm: bool = True,
                 table_limit: int = 1500) -> tuple[list[dict], dict]:
    cache = json.loads(DESC_CACHE.read_text(encoding="utf-8")) if DESC_CACHE.exists() else {}
    chunks, stats = [], {"pages": len(pages), "text_chunks": 0, "table_chunks": 0, "figures": 0,
                         "figures_region_not_found": [], "vlm_failures": [], "pages_without_text": []}
    for pn in pages:
        page = doc[pn - 1]
        figs, tabs = figure_regions(page), page_tables(page)
        exclude = [f["bbox"] for f in figs] + [t["bbox"] for t in tabs]
        passages = page_passages(page, exclude)
        if not passages and not figs and not tabs:
            stats["pages_without_text"].append(pn)
        for i, p in enumerate(passages, 1):
            chunks.append({"chunk_id": f"helm-p{pn:03d}-t{i}", "page": pn, "kind": "text", "label": None,
                           "caption": None, "text": p, "bbox": None, "image_path": None})
            stats["text_chunks"] += 1
        for j, t in enumerate(tabs, 1):
            label = f"Table {t['number']}" if t["number"] else f"table on page {pn}"
            per_row = label in ROW_TABLES
            cap = short_caption(t["caption"]) if per_row else t["caption"]
            for k, part in enumerate(split_table(t["markdown"], table_limit, per_row=per_row), 1):
                chunks.append({"chunk_id": f"helm-p{pn:03d}-tab{j}-{k}", "page": pn, "kind": "table", "label": label,
                               "caption": t["caption"], "bbox": t["bbox"], "image_path": None,
                               "text": f"{label} (page {pn}). {cap}\n{part}"})
                stats["table_chunks"] += 1
        for f in figs:
            key = f"{f['number']}|{vlm_model}"
            img = FIG_DIR / f"fig{f['number']:02d}_p{pn:03d}.png"
            render_region(page, f["bbox"], img)
            inside = figure_text(page, f["bbox"])
            desc = cache.get(key)
            if desc is None and use_vlm:
                try:
                    t0 = time.time()
                    desc = describe(img, vlm_model)
                    cache[key] = desc
                    DESC_CACHE.parent.mkdir(parents=True, exist_ok=True)
                    DESC_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
                    print(f"  fig {f['number']} (p{pn}) described in {time.time() - t0:.0f}s", flush=True)
                except Exception as e:  # noqa: BLE001 - recorded, the figure is still indexed by caption + text
                    stats["vlm_failures"].append({"figure": f["number"], "error": str(e)[:120]})
            if not f["region_found"]:
                stats["figures_region_not_found"].append(f["number"])
            meds = medians_text(boxplot_medians(page, f["bbox"]))
            body = (f"Figure {f['number']} (page {pn}). {f['caption']}\n" + (meds + "\n" if meds else "")
                    + f"Text printed inside the figure {inside[:2400]}\n"
                    f"Visual description (generated by {vlm_model}, may contain errors): {desc or 'not available'}")
            chunks.append({"chunk_id": f"helm-p{pn:03d}-fig{f['number']}", "page": pn, "kind": "figure",
                           "label": f"Figure {f['number']}", "caption": f["caption"], "bbox": f["bbox"],
                           "image_path": str(img).replace("\\", "/"), "text": body})
            stats["figures"] += 1
    return chunks, stats


def store(chunks: list[dict], pages: list[int], cfg) -> None:
    vecs = embed_docs([c["text"] for c in chunks], cfg)
    with psycopg.connect(cfg.database_url) as conn:
        conn.execute(TABLE_SQL)
        conn.execute("DELETE FROM helm_chunks WHERE page = ANY(%s)", (pages,))
        for c, v in zip(chunks, vecs):
            conn.execute(
                "INSERT INTO helm_chunks VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::vector)",
                (c["chunk_id"], c["page"], c["kind"], c["label"], c["caption"], c["text"],
                 json.dumps(c["bbox"]) if c["bbox"] else None, c["image_path"],
                 "[" + ",".join(repr(float(x)) for x in v) + "]"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--vlm", default="qwen2.5vl:7b")
    p.add_argument("--pages")
    p.add_argument("--no-vlm", action="store_true")
    p.add_argument("--table-limit", type=int, default=1500, help="max characters per table chunk (rows are grouped)")
    a = p.parse_args(argv)
    cfg = load_config()
    doc = pymupdf.open(PDF)
    pages = page_range(a.pages, doc.page_count)
    chunks, stats = build_chunks(doc, pages, a.vlm, use_vlm=not a.no_vlm, table_limit=a.table_limit)
    store(chunks, pages, cfg)
    stats |= {"total_chunks": len(chunks), "vlm_model": a.vlm, "embedding_model": cfg.embedding_model,
              "table_limit": a.table_limit}
    if not a.pages:
        STATS.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
