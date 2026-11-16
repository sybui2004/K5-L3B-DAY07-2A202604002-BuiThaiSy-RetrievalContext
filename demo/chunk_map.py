"""Dữ liệu cho tab "Bản đồ chunk": chunk nằm ở trang nào và dài bao nhiêu (không import streamlit).
Theo ý tưởng bản đồ chunk của Day 6; chạy được cho cả bộ Cơ bản (Luật Lao động) và Bonus (HELM)."""
import html

KIND_HUE = {"text": 210, "table": 28, "figure": 140}
KIND_LABEL = {"text": "văn bản", "table": "bảng", "figure": "hình"}


def chunk_rows(chunks: list[dict]) -> list[dict]:
    """Chunk Day 7 (id, source_id, page, text, metadata) -> hàng gọn, sắp theo tài liệu rồi trang."""
    rows = []
    for c in chunks:
        meta = c.get("metadata") or {}
        rows.append({"id": c["id"], "doc": c.get("source_id") or "", "page_start": c["page"],
                     "page_end": meta.get("page_end") or c["page"], "char_count": len(c.get("text") or ""),
                     "kind": meta.get("kind") or "text", "dieu": meta.get("dieu")})
    return sorted(rows, key=lambda r: (r["doc"], r["page_start"], r["id"]))


def length_histogram(rows: list[dict], bins: int = 10) -> list[tuple[int, int]]:
    """[(cận dưới của khoảng, số chunk)] theo độ dài ký tự; [] khi không có chunk."""
    lengths = [r["char_count"] for r in rows]
    if not lengths:
        return []
    lo, hi = min(lengths), max(lengths)
    width = max(1, -(-(hi - lo + 1) // bins))
    counts = [0] * bins
    for n in lengths:
        counts[min((n - lo) // width, bins - 1)] += 1
    return [(lo + i * width, c) for i, c in enumerate(counts)]


def kind_stats(rows: list[dict]) -> list[dict]:
    """Thống kê theo loại chunk: số lượng và độ dài nhỏ nhất / trung bình / lớn nhất."""
    out = []
    for kind in sorted({r["kind"] for r in rows}, key=lambda k: list(KIND_HUE).index(k) if k in KIND_HUE else 99):
        ls = [r["char_count"] for r in rows if r["kind"] == kind]
        out.append({"loại": KIND_LABEL.get(kind, kind), "số chunk": len(ls), "ngắn nhất": min(ls),
                    "trung bình": round(sum(ls) / len(ls)), "dài nhất": max(ls)})
    return out


def map_html(rows: list[dict]) -> str:
    """Mỗi tài liệu một dải: mỗi cột là một trang, mỗi ô là một chunk bắt đầu ở trang đó.
    Màu: sắc độ theo loại chunk, độ đậm theo độ dài (càng đậm càng dài)."""
    if not rows:
        return ""
    longest = max(r["char_count"] for r in rows) or 1
    by_doc: dict[str, dict[int, list[dict]]] = {}
    for r in rows:
        by_doc.setdefault(r["doc"], {}).setdefault(r["page_start"], []).append(r)
    out = []
    for doc, pages in by_doc.items():
        out.append(f"<div style='margin:8px 0 2px;font-weight:600'>{html.escape(doc)}</div>"
                   "<div style='display:flex;flex-wrap:wrap;gap:3px'>")
        for page in sorted(pages):
            boxes = "".join(
                f"<div title='{html.escape(r['id'])} · {KIND_LABEL.get(r['kind'], r['kind'])} · "
                f"{r['char_count']} ký tự · trang {r['page_start']}-{r['page_end']}' "
                f"style='width:14px;height:14px;border-radius:2px;"
                f"background:hsl({KIND_HUE.get(r['kind'], 0)},70%,{85 - 55 * r['char_count'] // longest}%)'></div>"
                for r in pages[page])
            out.append("<div style='display:flex;flex-direction:column;gap:2px;align-items:center'>"
                       f"<span style='font-size:9px;color:#888'>{page}</span>{boxes}</div>")
        out.append("</div>")
    return "".join(out)
