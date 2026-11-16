import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import load_config

FULL = {
    "DEEPSEEK_API_KEY": "sk-secret-value", "DEEPSEEK_BASE_URL": "https://api.example",
    "DEEPSEEK_MODEL": "m", "DATABASE_URL": "postgresql://u:p@h:1/d",
    "OLLAMA_URL": "http://o", "EMBEDDING_MODEL": "bge-m3",
}


class ConfigTests(unittest.TestCase):
    def test_loads_all_fields(self):
        with mock.patch.dict(os.environ, FULL, clear=True):
            cfg = load_config(env_path=os.devnull)
        self.assertEqual(cfg.deepseek_model, "m")
        self.assertEqual(cfg.embedding_model, "bge-m3")
        self.assertEqual(cfg.database_url, FULL["DATABASE_URL"])

    def test_missing_key_raises_without_leaking_value(self):
        env = dict(FULL, DEEPSEEK_MODEL="")
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError) as cm:
                load_config(env_path=os.devnull)
        msg = str(cm.exception)
        self.assertIn("DEEPSEEK_MODEL", msg)
        self.assertNotIn("sk-secret-value", msg)
        self.assertNotIn("postgresql://", msg)


if __name__ == "__main__":
    unittest.main()
