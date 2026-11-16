"""Infrastructure failures (Ollama down, Postgres down) surface as clear RuntimeErrors without leaking secrets."""
import sys
import unittest
from pathlib import Path
from unittest import mock

import psycopg
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import Config
from src.embed import embed_query
from src.retrievers import DenseRetriever

SECRET_URL = "postgresql://user:s3cret@127.0.0.1:15433/db"


def cfg():
    fields = Config.__dataclass_fields__
    values = {k: "x" for k in fields}
    values.update(database_url=SECRET_URL, ollama_url="http://localhost:11434", embedding_model="bge-m3")
    return Config(**values)


class ErrorHandlingTests(unittest.TestCase):
    def test_ollama_unreachable_raises_runtime_error(self):
        with mock.patch("src.embed.requests.post", side_effect=requests.ConnectionError("refused")):
            with self.assertRaisesRegex(RuntimeError, "unreachable.*ConnectionError"):
                embed_query("q", cfg())

    def test_ollama_timeout_raises_runtime_error(self):
        with mock.patch("src.embed.requests.post", side_effect=requests.Timeout()):
            with self.assertRaisesRegex(RuntimeError, "Timeout"):
                embed_query("q", cfg())

    def test_ollama_bad_body_raises_runtime_error(self):
        resp = mock.Mock(status_code=200, json=mock.Mock(return_value={"oops": []}))
        with mock.patch("src.embed.requests.post", return_value=resp):
            with self.assertRaisesRegex(RuntimeError, "unexpected body"):
                embed_query("q", cfg())

    def test_database_down_raises_without_leaking_url(self):
        r = DenseRetriever(cfg(), embed=lambda q, c: [0.0] * 1024)
        with mock.patch("src.retrievers.psycopg.connect", side_effect=psycopg.OperationalError("conn refused")):
            with self.assertRaises(RuntimeError) as ctx:
                r.search("q", filters=None, top_k=3)
        self.assertIn("vector store unavailable", str(ctx.exception))
        self.assertNotIn("s3cret", str(ctx.exception))

    def test_loading_day6_chunks_with_database_down_raises_without_leaking_url(self):
        from src.store_day6 import load_day6_chunks
        with mock.patch("src.store_day6.psycopg.connect", side_effect=psycopg.OperationalError("down")):
            with self.assertRaises(RuntimeError) as ctx:
                load_day6_chunks(cfg())
        self.assertNotIn("s3cret", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
