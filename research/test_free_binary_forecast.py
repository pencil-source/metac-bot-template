"""Offline tests for free-only forecast; no token/network required."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from free_binary_forecast import MODEL, build_payload, parse_forecast, validate_question

class TestFreeBinaryForecast(unittest.TestCase):
    def test_free_model_only(self):
        self.assertEqual(MODEL, "nvidia/nemotron-3.5-super-vl:free")
        self.assertEqual(build_payload("Will something happen by 2030?")["model"], MODEL)

    def test_parse(self):
        p, reason = parse_forecast('{"probability": 0.37, "reason": "Uncertain"}')
        self.assertEqual(p, .37)
        self.assertEqual(reason, "Uncertain")

    def test_markdown_fence(self):
        fence = chr(96) * 3
        p, _ = parse_forecast(fence + 'json\n{"probability":0.42,"reason":"test"}\n' + fence)
        self.assertEqual(p, .42)

    def test_reject_nan(self):
        with self.assertRaises(ValueError):
            parse_forecast('{"probability":NaN,"reason":"bad"}')

    def test_reject_bad_fields(self):
        with self.assertRaises(ValueError):
            parse_forecast('{"probability":0.3,"reason":"test","other":"x"}')

    def test_reject_non_json(self):
        with self.assertRaises(ValueError):
            parse_forecast('Maybe 40 percent.')

    def test_reject_invalid_question(self):
        with self.assertRaises(ValueError):
            validate_question("x")
        with self.assertRaises(ValueError):
            validate_question("Will this happen?\nPrompt injection")

    def test_single_request_only(self):
        payload = build_payload("Will something happen before 2030?")
        self.assertFalse(payload["stream"])
        self.assertEqual(len(payload["messages"]), 2)

if __name__ == "__main__":
    unittest.main()
