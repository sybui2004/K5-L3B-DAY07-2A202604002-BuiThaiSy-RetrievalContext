"""Read-only access to the Day 6 pgvector tables, mapped to the Day 7 chunk schema."""
import psycopg

from .config import Config

VERSIONS = {"2012", "2019"}
_COLS = ("chunk_id, document_id, version, source, page_start, page_end, printed_page_start, "
         "chuong, dieu, dieu_title, text")


def row_to_chunk(row) -> dict:
    (chunk_id, document_id, version, source, page_start, page_end, printed, chuong, dieu, dieu_title, text) = row
    return {"id": chunk_id, "text": text, "source_id": document_id, "source": source, "page": page_start,
            "metadata": {"version": version, "page_end": page_end, "printed_page_start": printed,
                         "chuong": chuong, "dieu": dieu, "dieu_title": dieu_title}}


def load_day6_chunks(cfg: Config, table: str = "chunks_b") -> list[dict]:
    if table not in {"chunks_a", "chunks_b", "chunks_c"}:
        raise ValueError(f"unexpected table {table!r}")
    try:
        with psycopg.connect(cfg.database_url, connect_timeout=10) as conn:
            rows = conn.execute(f"SELECT {_COLS} FROM {table} ORDER BY chunk_id").fetchall()
    except psycopg.Error as e:  # never echo DATABASE_URL (it holds the password)
        raise RuntimeError(f"cannot read Day 6 table {table} (check Postgres on DATABASE_URL): {type(e).__name__}") from e
    return [row_to_chunk(r) for r in rows]
