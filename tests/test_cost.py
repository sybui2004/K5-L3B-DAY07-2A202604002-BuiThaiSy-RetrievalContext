import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cost import run_cost


class CostTests(unittest.TestCase):
    def test_flash_price_all_input_as_cache_miss(self):
        # 1M in + 1M out: peak 0.30 + 1.20, off-peak 0.15 + 0.60
        self.assertEqual(run_cost(1_000_000, 1_000_000), {"peak": 1.5, "off_peak": 0.75})

    def test_unknown_model_raises(self):
        with self.assertRaises(ValueError):
            run_cost(1, 1, "gpt-x")


if __name__ == "__main__":
    unittest.main()
