"""Extract text passages, tables and figure regions from the HELM PDF with page/bbox provenance."""
import re
from pathlib import Path

import pymupdf

PDF = Path("bonus/data/raw/helm_2211.09110v2.pdf")
FIG_DIR = Path("bonus/data/figures")
CAP_FIG = re.compile(r"^Figure (\d+)[:.]\s*(.*)", re.M)
CAP_TAB = re.compile(r"^Table (\d+)[:.]\s*(.*)", re.M)
MAX_CHARS = 1100


def _clean(t: str) -> str:
    return re.sub(r"[ \t]+", " ", t.replace("\xad", "")).strip()


def _caption_blocks(page: pymupdf.Page, kind: str) -> list[tuple[int, str, pymupdf.Rect]]:
    """Return (number, full caption text, block rect) for blocks that start with 'Figure N:' / 'Table N:'."""
    pat = re.compile(rf"^{kind} (\d+)[:.]")
    out = []
    for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
        text = _clean(text)
        m = pat.match(text)
        if m:
            out.append((int(m.group(1)), re.sub(r"\s+", " ", text), pymupdf.Rect(x0, y0, x1, y1)))
    return out


def _union(rects: list[pymupdf.Rect]) -> pymupdf.Rect | None:
    if not rects:
        return None
    r = pymupdf.Rect(rects[0])
    for x in rects[1:]:
        r |= x
    return r


def figure_regions(page: pymupdf.Page) -> list[dict]:
    """One region per 'Figure N' caption: union of drawings/images between the previous element and the caption."""
    caps = sorted(_caption_blocks(page, "Figure"), key=lambda c: c[2].y0)
    if not caps:
        return []
    visuals = [c for c in page.cluster_drawings() if c.width > 40 and c.height > 25]
    for img in page.get_images():
        visuals += [r for r in page.get_image_rects(img[0]) if r.width > 40 and r.height > 25]
    regions, top = [], page.rect.y0 + 20
    for num, text, cap in caps:
        mine = [v for v in visuals if v.y1 <= cap.y1 + 2 and v.y0 >= top - 2 and v.y0 < cap.y0]
        box = _union(mine)
        if box is None:
            box = pymupdf.Rect(page.rect.x0 + 30, max(top, cap.y0 - 330), page.rect.x1 - 30, cap.y0)
            found = False
        else:
            found = True
        # full text width (drawings and images often miss thin edges); skip the running header at the page top
        box = pymupdf.Rect(page.rect.x0 + 30, max(box.y0 - 4, page.rect.y0 + 48), page.rect.x1 - 30, cap.y1 + 2) & page.rect
        regions.append({"number": num, "caption": text, "bbox": [round(v, 1) for v in box], "region_found": found})
        top = cap.y1
    return regions


def region_text(page: pymupdf.Page, bbox) -> str:
    """Text printed inside the figure (axis ticks, labels, legend): vector PDFs keep it as real text."""
    words = page.get_text("words", clip=pymupdf.Rect(bbox))
    return " ".join(w[4] for w in words)


def _gap_split(items, axis: int, min_gap: float):
    """Split (rect, text) items at the widest empty band along axis (0=x, 1=y)."""
    lo = (lambda r: r.x0) if axis == 0 else (lambda r: r.y0)
    hi = (lambda r: r.x1) if axis == 0 else (lambda r: r.y1)
    iv = sorted((lo(r), hi(r)) for r, _ in items)
    best, cut, end = 0.0, None, iv[0][1]
    for a, b in iv[1:]:
        if a - end > best:
            best, cut = a - end, (end + a) / 2
        end = max(end, b)
    if cut is None or best < min_gap:
        return None
    return [i for i in items if hi(i[0]) <= cut], [i for i in items if lo(i[0]) >= cut], best


def _xy_cut(items, min_gap: float = 5.0, depth: int = 0) -> list:
    """Recursive XY-cut: split at the widest whitespace band (either axis) until no band is wide enough."""
    if len(items) <= 1 or depth > 12:
        return [items]
    splits = [s for s in (_gap_split(items, 0, min_gap), _gap_split(items, 1, min_gap)) if s and s[0] and s[1]]
    if not splits:
        return [items]
    a, b, _ = max(splits, key=lambda s: s[2])
    return _xy_cut(a, min_gap, depth + 1) + _xy_cut(b, min_gap, depth + 1)


def _is_tick(reg) -> bool:
    return all(re.fullmatch(r"[−-]?\d+(\.\d+)?%?", t) for _, t in reg)


def layout_lines(items: list[tuple[pymupdf.Rect, str]], frame) -> str:
    """Text lines of a figure grouped into regions (panels, legends, axes) with their position, so that the
    order of bars/labels survives: within a region lines are listed top to bottom, then left to right."""
    if not items:
        return ""
    frame = pymupdf.Rect(frame)
    out = ["(regions with position as % of the figure box; within a region, lines are listed top to bottom)"]
    regions: list[list] = []
    for reg in _xy_cut(list(items)):  # axis ticks come out as one-number regions: merge consecutive ones
        if regions and _is_tick(reg) and _is_tick(regions[-1]):
            regions[-1] = regions[-1] + reg
        else:
            regions.append(reg)
    for reg in regions:
        u = pymupdf.Rect(reg[0][0])
        for r, _ in reg[1:]:
            u |= r
        pct = lambda v, o, w: max(0, min(100, round(100 * (v - o) / w)))  # noqa: E731
        pos = (f"x {pct(u.x0, frame.x0, frame.width)}-{pct(u.x1, frame.x0, frame.width)}%, "
               f"y {pct(u.y0, frame.y0, frame.height)}-{pct(u.y1, frame.y0, frame.height)}%")
        reg = sorted(reg, key=lambda i: (round(i[0].y0), i[0].x0))
        out.append(f"[{pos}] " + " | ".join(t for _, t in reg))
    return "\n".join(out)


def region_layout(page: pymupdf.Page, bbox, transform=None) -> str:
    """Positional version of region_text; drops the caption (from the 'Figure N:' line down).
    `transform` is applied to each line's text (e.g. to decode a font with shifted codes)."""
    items = []
    for b in page.get_text("dict", clip=pymupdf.Rect(bbox))["blocks"]:
        for ln in b.get("lines", []):
            t = re.sub(r"\s+", " ", " ".join(s["text"] for s in ln["spans"])).strip()
            if t:
                items.append((pymupdf.Rect(ln["bbox"]), t))
    cap_y = min((r.y0 for r, t in items if re.match(r"(Figure|Table)\s+\d+[:.]", t)), default=None)
    if cap_y is not None:
        items = [(r, t) for r, t in items if r.y0 < cap_y - 0.5]
    if transform:
        items = [(r, transform(t)) for r, t in items]
    return layout_lines(items, bbox)


_NUM = re.compile(r"^[−-]?\d+(\.\d+)?$")
_MEDIAN_RGB = (1.0, 0.5, 0.05)  # matplotlib's default orange median line


def _rgb_near(c, ref, tol: float = 0.08) -> bool:
    return c is not None and all(abs(a - b) <= tol for a, b in zip(c, ref))


def _tick_values(ticks: list[tuple[float, str]]) -> list[tuple[float, float]]:
    """(y, label) top->bottom to (y, value); some PDFs lose the minus glyph, so values must decrease downwards:
    once 0 is passed, the labels below it are negative."""
    out, below_zero = [], False
    for y, t in sorted(ticks):
        v = float(t.replace("−", "-"))
        if below_zero and v > 0:
            v = -v
        if v == 0:
            below_zero = True
        out.append((y, v))
    return out


def boxplot_medians(page: pymupdf.Page, bbox) -> list[tuple[str, list[tuple[str, float]]]]:
    """Read box-plot medians straight from the vector graphics: each panel's axes is a white background rect,
    medians are orange horizontal segments, the y value comes from a linear fit of the y tick labels and the
    category from the x labels below the axes. Returns [(panel title, [(category, median), ...]), ...]."""
    R = pymupdf.Rect(bbox)
    drawings = page.get_drawings()
    axes = [pymupdf.Rect(g["rect"]) for g in drawings
            if _rgb_near(g.get("fill"), (1, 1, 1), 0.01) and not g.get("color")
            and pymupdf.Rect(g["rect"]) in R and pymupdf.Rect(g["rect"]).width > 40]
    segs = [g["rect"] for g in drawings if _rgb_near(g.get("color"), _MEDIAN_RGB) and abs(g["rect"].height) < 0.5]
    lines = []
    for b in page.get_text("dict", clip=R)["blocks"]:
        for ln in b.get("lines", []):
            t = re.sub(r"\s+", " ", " ".join(s["text"] for s in ln["spans"])).strip()
            if t:
                lines.append({"r": pymupdf.Rect(ln["bbox"]), "t": t, "dir": ln["dir"]})
    lines = [l for l in lines if re.search(r"\w", l["t"])]  # drop fragments such as ")" left by missing glyphs

    def title_of(ax):
        return min((l for l in lines if l["r"].y1 <= ax.y0 + 1 and ax.y0 - l["r"].y1 < 25
                    and l["r"].x0 < (ax.x0 + ax.x1) / 2 < l["r"].x1), key=lambda l: ax.y0 - l["r"].y1, default=None)

    titles = {id(t) for t in map(title_of, axes) if t}
    out = []
    for ax in axes:
        meds = [s for s in segs if ax.x0 - 1 <= s.x0 and s.x1 <= ax.x1 + 1 and ax.y0 - 1 <= s.y0 <= ax.y1 + 1]
        ticks = [((l["r"].y0 + l["r"].y1) / 2, l["t"]) for l in lines
                 if _NUM.match(l["t"]) and l["r"].x1 <= ax.x0 + 2 and ax.x0 - l["r"].x1 < 40
                 and ax.y0 - 5 <= (l["r"].y0 + l["r"].y1) / 2 <= ax.y1 + 5]
        if not meds or len(ticks) < 2:
            continue
        pts = _tick_values(ticks)
        my, mv = sum(y for y, _ in pts) / len(pts), sum(v for _, v in pts) / len(pts)
        sxx = sum((y - my) ** 2 for y, _ in pts)
        if not sxx:
            continue
        slope = sum((y - my) * (v - mv) for y, v in pts) / sxx
        title = title_of(ax)

        def anchor(l):  # x where a category label meets its tick
            dy = l["dir"][1]
            if abs(dy) < 0.05:
                return (l["r"].x0 + l["r"].x1) / 2
            return l["r"].x0 if dy > 0 else l["r"].x1

        cats = [l for l in lines if l["r"].y0 >= ax.y1 - 1 and l["r"].y0 - ax.y1 < 40 and not _NUM.match(l["t"])
                and ax.x0 - 30 <= anchor(l) <= ax.x1 + 5 and id(l) not in titles]
        centers = [(s.x0 + s.x1) / 2 for s in meds]
        labels: dict[int, list] = {}
        for l in cats:  # each label line goes to the nearest median; multi-line labels are joined top->bottom
            i = min(range(len(meds)), key=lambda k: abs(anchor(l) - centers[k]))
            labels.setdefault(i, []).append(l)
        res = []
        for i, s in enumerate(meds):
            name = " ".join(l["t"] for l in sorted(labels.get(i, []), key=lambda l: l["r"].y0)) or f"box {i + 1}"
            name = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", name))
            res.append((name, round(mv + slope * (s.y0 - my), 3) + 0.0))
        out.append((title["t"] if title else "panel", res))
    return out


def medians_text(panels) -> str:
    if not panels:
        return ""
    rows = ["Box-plot medians measured from the PDF vector graphics (exact positions, not a model guess):"]
    for title, meds in panels:
        hi, lo = max(meds, key=lambda m: m[1]), min(meds, key=lambda m: m[1])
        rows.append(f"[panel {title}] " + "; ".join(f"{c} {v:g}" for c, v in meds)
                    + f" (highest median: {hi[0]}; lowest: {lo[0]})")
    return "\n".join(rows)


def render_region(page: pymupdf.Page, bbox, path: Path, dpi: int = 170) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    page.get_pixmap(dpi=dpi, clip=pymupdf.Rect(bbox)).save(str(path))


def table_to_markdown(rows: list[list[str | None]]) -> str:
    rows = [[re.sub(r"\s+", " ", (c or "")).strip() for c in r] for r in rows if any((c or "").strip() for c in r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    head = "| " + " | ".join(rows[0]) + " |"
    sep = "|" + "---|" * width
    body = ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join([head, sep, *body])


def short_caption(caption: str) -> str:
    """First sentence of a table caption ('Table 5: Models.'): the long description would drown a one-row chunk."""
    return re.split(r"(?<=\.)\s", caption.strip(), maxsplit=1)[0]


def split_table(md: str, limit: int = 1500, per_row: bool = False) -> list[str]:
    """Group rows into chunks of at most `limit` characters, repeating the header; `per_row` makes one chunk per row
    (for lookup tables such as the model list, where a row is the unit a question asks about)."""
    lines = md.split("\n")
    if per_row and len(lines) > 2:
        return [lines[0] + "\n" + r for r in lines[1:] if r.strip()]
    if len(md) <= limit or len(lines) <= 3:
        return [md]
    head, rows, out, cur = lines[:2], lines[2:], [], []
    for r in rows:
        if cur and len("\n".join(head + cur + [r])) > limit:
            out.append("\n".join(head + cur))
            cur = []
        cur.append(r)
    if cur:
        out.append("\n".join(head + cur))
    return out


def page_tables(page: pymupdf.Page) -> list[dict]:
    caps = sorted(_caption_blocks(page, "Table"), key=lambda c: c[2].y0)
    out = []
    for t in page.find_tables().tables:
        bbox = pymupdf.Rect(t.bbox)
        # find_tables() sometimes leaves the header row out: take the text line just above the table
        # unless it is a caption ('Table N:') or a figure label.
        above = pymupdf.Rect(bbox.x0, bbox.y0 - 14, bbox.x1, bbox.y0)
        head = region_rows(page, above)
        md = region_rows(page, bbox) or table_to_markdown(t.extract())
        if head and not re.match(r"^(Table|Figure) \d", head) and len(head) < 160 and md:
            md = head + chr(10) + md
        if len(md) < 40:
            continue
        cap = next((c for c in reversed(caps) if c[2].y1 <= bbox.y0 + 5), None) or (caps[0] if caps else None)
        out.append({"bbox": [round(v, 1) for v in bbox], "markdown": md,
                    "caption": cap[1] if cap else "", "number": cap[0] if cap else None})
    return out


def page_passages(page: pymupdf.Page, exclude: list) -> list[str]:
    """Body text split into passages of at most MAX_CHARS, skipping blocks inside figure/table regions."""
    ex = [pymupdf.Rect(r) for r in exclude]
    paras = []
    for x0, y0, x1, y1, text, *_ in sorted(page.get_text("blocks"), key=lambda b: (round(b[1]), b[0])):
        r = pymupdf.Rect(x0, y0, x1, y1)
        if any(r.intersects(e) and (r & e).get_area() > 0.5 * r.get_area() for e in ex):
            continue
        t = re.sub(r"\s*\n\s*", " ", _clean(text))
        if len(t) > 25:
            paras.append(t)
    out, cur = [], ""
    for p in paras:
        while len(p) > MAX_CHARS:
            cut = p.rfind(". ", 0, MAX_CHARS)
            cut = cut + 1 if cut > 300 else MAX_CHARS
            out.append((cur + " " + p[:cut]).strip() if cur else p[:cut])
            cur, p = "", p[cut:].strip()
        if cur and len(cur) + len(p) + 1 > MAX_CHARS:
            out.append(cur)
            cur = p
        else:
            cur = (cur + " " + p).strip()
    if cur:
        out.append(cur)
    return out


def region_rows(page: pymupdf.Page, bbox, ytol: float = 3.0, gap: float = 9.0) -> str:
    """Rebuild a table row by row from word positions: cells in a row are joined by ' | '.

    find_tables() merges cells in complex tables; the word coordinates keep rows and columns intact.
    """
    words = sorted(page.get_text("words", clip=pymupdf.Rect(bbox)), key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    rows, cur, cy = [], [], None
    for w in words:
        yc = (w[1] + w[3]) / 2
        if cy is None or abs(yc - cy) <= ytol:
            cur.append(w)
            cy = yc if cy is None else (cy + yc) / 2
        else:
            rows.append(cur)
            cur, cy = [w], yc
    if cur:
        rows.append(cur)
    lines = []
    for r in rows:
        r.sort(key=lambda w: w[0])
        cells, cell, last = [], [r[0][4]], r[0][2]
        for w in r[1:]:
            if w[0] - last > gap:
                cells.append(" ".join(cell))
                cell = [w[4]]
            else:
                cell.append(w[4])
            last = w[2]
        cells.append(" ".join(cell))
        lines.append(" | ".join(cells))
    return "\n".join(lines)
