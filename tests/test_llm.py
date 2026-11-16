import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

try:
    import httpx
except ImportError:  # openai 3.x ships httpx2
    import httpx2 as httpx
import openai

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import Config
from src.llm import DeepSeekController, LlmError
from src.prompts import SEARCH_TOOL, SYSTEM_PROMPT

CFG = Config("sk-very-secret", "http://b", "deepseek-v4-flash", "db", "http://o", "bge-m3")


def reply(content=None, tool_query=None, usage=(10, 5)):
    calls = None
    if tool_query is not None:
        calls = [NS(id="call1", function=NS(name="search", arguments=json.dumps({"query": tool_query})))]
    return NS(choices=[NS(message=NS(content=content, tool_calls=calls))],
              usage=NS(prompt_tokens=usage[0], completion_tokens=usage[1]))


class FakeClient:
    def __init__(self, *outcomes):
        self.outcomes, self.requests = list(outcomes), []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.requests.append(kw)
        o = self.outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return o


def ctrl(*outcomes):
    c = FakeClient(*outcomes)
    return DeepSeekController(CFG, client=c, sleep=lambda s: None), c


HISTORY = [{"tool": "search", "queries": ["q"], "context": "[A:1] nội dung", "context_ids": ["A:1"]}]


class ControllerTests(unittest.TestCase):
    def test_tool_call_parsed_to_search_action(self):
        c, client = ctrl(reply(tool_query="nghỉ hằng năm"))
        self.assertEqual(c.decide("Hỏi?", []), {"action": "search", "query": "nghỉ hằng năm"})
        req = client.requests[0]
        self.assertEqual(req["model"], "deepseek-v4-flash")
        self.assertEqual(req["tools"], [SEARCH_TOOL])
        self.assertEqual(req["tool_choice"], "auto")  # thinking mode rejects "required"
        self.assertEqual(req["messages"][0], {"role": "system", "content": SYSTEM_PROMPT})

    def test_final_message_parsed_with_only_context_citations(self):
        c, client = ctrl(reply(content="Là 12 ngày [A:1] và [ghi chú] theo [Z:9]."))
        act = c.decide("Hỏi?", HISTORY)
        self.assertEqual(act["action"], "answer")
        self.assertEqual(act["citations"], ["A:1"])
        self.assertEqual(client.requests[0]["tool_choice"], "auto")
        self.assertIn("[A:1] nội dung", json.dumps(client.requests[0]["messages"], ensure_ascii=False))

    def test_timeout_retries_then_succeeds(self):
        err = openai.APITimeoutError(request=httpx.Request("POST", "http://x"))
        c, client = ctrl(err, err, reply(tool_query="x"))
        self.assertEqual(c.decide("Hỏi?", [])["action"], "search")
        self.assertEqual(len(client.requests), 3)

    def test_persistent_failure_raises_llm_error_without_secret(self):
        boom = RuntimeError("401 for key sk-very-secret")
        c, _ = ctrl(boom, boom, boom)
        with self.assertRaises(LlmError) as cm:
            c.decide("Hỏi?", [])
        self.assertNotIn("sk-very-secret", str(cm.exception))

    def test_malformed_tool_arguments_raise_llm_error(self):
        bad = reply(tool_query="x")
        bad.choices[0].message.tool_calls[0].function.arguments = "{not json"
        c, _ = ctrl(bad, bad, bad)
        with self.assertRaises(LlmError):
            c.decide("Hỏi?", [])

    def test_usage_accumulates_and_resets(self):
        c, _ = ctrl(reply(tool_query="x", usage=(100, 20)), reply(content="ok [A:1]", usage=(50, 10)))
        c.decide("Hỏi?", [])
        c.decide("Hỏi?", HISTORY)
        u = c.pop_usage()
        self.assertEqual((u["tokens_in"], u["tokens_out"], u["calls"]), (150, 30, 2))
        self.assertEqual(c.pop_usage()["calls"], 0)

    def test_allow_search_false_omits_tools_and_says_so(self):
        c, client = ctrl(reply(content="Là 12 ngày [A:1]"))
        act = c.decide("Hỏi?", HISTORY, allow_search=False)
        self.assertEqual(act["action"], "answer")
        req = client.requests[0]
        self.assertNotIn("tools", req)
        self.assertNotIn("tool_choice", req)
        self.assertIn("hết lượt tìm kiếm", json.dumps(req["messages"], ensure_ascii=False))

    def test_custom_system_prompt_is_used(self):
        client = FakeClient(reply(tool_query="x"))
        DeepSeekController(CFG, client=client, sleep=lambda s: None, system_prompt="SP").decide("Hỏi?", [])
        self.assertEqual(client.requests[0]["messages"][0], {"role": "system", "content": "SP"})

    def test_rewrite_hint_extends_base_prompt(self):
        from src.prompts import REWRITE_HINT, build_system_prompt
        self.assertEqual(build_system_prompt(False), SYSTEM_PROMPT)
        self.assertTrue(build_system_prompt(True).startswith(SYSTEM_PROMPT))
        self.assertIn(REWRITE_HINT, build_system_prompt(True))

    def test_system_prompt_says_documents_are_data(self):
        self.assertIn("dữ liệu", SYSTEM_PROMPT)
        self.assertIn("không đủ bằng chứng", SYSTEM_PROMPT.lower())

    def test_empty_answer_cut_by_length_is_retried_with_larger_budget(self):
        cut = reply(content="", usage=(10, 1500))
        cut.choices[0].finish_reason = "length"  # reasoning used the whole budget
        ok = reply(content="Đáp án [A:1]")
        c, client = ctrl(cut, ok)
        out = c.decide("Hỏi?", HISTORY)
        self.assertEqual(out["answer"], "Đáp án [A:1]")
        self.assertEqual(len(client.requests), 2)
        self.assertGreater(client.requests[1]["max_tokens"], client.requests[0]["max_tokens"])
        self.assertEqual(c.pop_usage()["calls"], 2)

    def test_empty_answer_with_normal_stop_is_not_retried(self):
        empty = reply(content="")
        empty.choices[0].finish_reason = "stop"
        c, client = ctrl(empty)
        self.assertEqual(c.decide("Hỏi?", HISTORY)["answer"], "")
        self.assertEqual(len(client.requests), 1)


if __name__ == "__main__":
    unittest.main()
