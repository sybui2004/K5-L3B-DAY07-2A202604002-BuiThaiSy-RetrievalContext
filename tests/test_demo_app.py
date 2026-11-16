import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from streamlit.testing.v1 import AppTest

APP = str(ROOT / "demo" / "app.py")


def new_app() -> AppTest:
    return AppTest.from_file(APP, default_timeout=60).run()


class DemoAppTests(unittest.TestCase):
    def test_app_runs_without_exception_on_basic_dataset(self):
        at = new_app()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        self.assertEqual(len(at.tabs), 4)

    def test_app_runs_without_exception_on_bonus_dataset(self):
        at = new_app()
        at.radio(key="dataset").set_value("bonus").run()
        self.assertFalse(at.exception, [e.value for e in at.exception])

    def test_run_dropdown_hides_nested_history_and_metrics_inputs(self):
        at = new_app()
        for key in ("basic", "bonus"):
            at.radio(key="dataset").set_value(key).run()
            options = at.selectbox(key="trace_run").options
            self.assertTrue(options)
            self.assertFalse([o for o in options if "[lịch sử]" in o or "_history" in o or "metrics_inputs" in o], (key, options))

    def test_trace_tab_can_open_a_question_with_error_or_abstain(self):
        at = new_app()
        at.radio(key="dataset").set_value("bonus").run()
        n = len(at.selectbox(key="trace_question").options)
        self.assertGreater(n, 1)
        for i in range(n):
            at.selectbox(key="trace_question").select_index(i).run()
            self.assertFalse(at.exception, (i, [e.value for e in at.exception]))

    def test_live_tab_without_infrastructure_shows_error_not_exception(self):
        at = new_app()
        at.text_area(key="live_question").set_value("Thời giờ làm việc tối đa?").run()
        with mock.patch("src.config.load_config", side_effect=ValueError("missing environment variables: DATABASE_URL")):
            at.button(key="run_live").click().run()
            self.assertFalse(at.exception, [e.value for e in at.exception])
            at.button(key="compare_live").click().run()
            self.assertFalse(at.exception, [e.value for e in at.exception])
        self.assertTrue(any("missing environment variables" in str(x.value) for x in at.error))


if __name__ == "__main__":
    unittest.main()
