"""Offline-only unit tests for PencilForecast v0.3. No keys or internet required."""
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import forecastlab_v03 as lab

NOW = datetime(2026,11,24,3,0,tzinfo=timezone.utc)

def sample_post():
    return {
        "id": 43210, "title": "Will a public event occur this year?",
        "question": {
            "id": 98765, "type": "binary", "status": "open",
            "title": "Will a public event occur before December 10, 2026?",
            "resolution_criteria": "Resolves YES if verified by an official source.",
            "description": "Public example, not a real Metaculus question.",
            "fine_print": "Annulled/ambiguous outcomes are excluded.",
            "scheduled_close_time": "2026-12-01T00:00:00Z",
            "scheduled_resolve_time": "2026-12-10T00:00:00Z",
        }
    }

def sample_record():
    q=lab.normalize_post(sample_post(),now=NOW)
    rec={
        "schema":lab.FORECAST_SCHEMA,
        "recorded_at_utc":"2026-11-24T06:00:00+00:00",
        "post_id":q["post_id"],"question_id":q["question_id"],
        "title":q["title"],"source_url":q["source_url"],
        "expected_resolve_at":q["expected_resolve_at"],
        "close_at":q["close_at"],"p_yes":.3,"baseline_p_yes":.5,
        "requested_model":lab.FREE_MODEL,"served_model":lab.FREE_MODEL,
        "provider_reported_cost_usd":0,"reason":"Uncertain.",
        "submitted_to_metaculus":False
    }
    import hashlib
    rec["sha256"]=hashlib.sha256(json.dumps(
        rec,sort_keys=True,ensure_ascii=False,separators=(",",":")
    ).encode()).hexdigest()
    return rec

class ForecastLabTests(unittest.TestCase):
    def test_free_variant_is_pinned(self):
        self.assertTrue(lab.FREE_MODEL.endswith(":free"))
        self.assertEqual(lab.MAX_QUESTIONS,3)

    def test_valid_binary_selection(self):
        q=lab.normalize_post(sample_post(),now=NOW)
        self.assertEqual(q["question_id"],98765)
        self.assertEqual(q["baseline_p_yes"],.5)

    def test_status_closed_rejected(self):
        post=sample_post()
        post["question"]["status"]="closed"
        self.assertIsNone(lab.normalize_post(post,now=NOW))

    def test_nonbinary_rejected(self):
        post=sample_post()
        post["question"]["type"]="numeric"
        self.assertIsNone(lab.normalize_post(post,now=NOW))

    def test_missing_criteria_rejected(self):
        post=sample_post()
        post["question"]["resolution_criteria"]=None
        self.assertIsNone(lab.normalize_post(post,now=NOW))

    def test_expired_close_rejected(self):
        post=sample_post()
        post["question"]["scheduled_close_time"]="2026-11-01T00:00:00Z"
        self.assertIsNone(lab.normalize_post(post,now=NOW))

    def test_long_horizon_rejected(self):
        post=sample_post()
        post["question"]["scheduled_resolve_time"]="2029-11-01T00:00:00Z"
        self.assertIsNone(lab.normalize_post(post,now=NOW))

    def test_discover_deduplicates_and_caps(self):
        with patch.object(lab,"list_posts",return_value=[sample_post(),sample_post()]):
            questions=lab.collect(max_questions=3,now=NOW)
        self.assertEqual(len(questions),1)
        with self.assertRaises(ValueError):
            lab.collect(max_questions=4,now=NOW)

    def test_invalid_timestamp_timezone(self):
        with self.assertRaises(ValueError):
            lab.parse_time("2026-11-24T03:00:00")

    def test_prediction_schema(self):
        self.assertEqual(lab.parse_prediction('{"probability":0.25,"reason":"Some uncertainty"}')[0],.25)
        fence=chr(96)*3
        self.assertEqual(lab.parse_prediction(fence+'json\n{"probability":0.33,"reason":"ok"}\n'+fence)[0],.33)

    def test_non_json_or_invalid_prob_rejected(self):
        for text in ('{"probability":NaN,"reason":"x"}',
                     '{"probability":1.0,"reason":"x"}',
                     '{"probability":"0.5","reason":"x"}',
                     '{"probability":0.3,"reason":"x","extra":1}',"40%"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                lab.parse_prediction(text)

    def test_zero_budget_forecast_request_and_record(self):
        q=lab.normalize_post(sample_post(),now=NOW)
        api={"model":lab.FREE_MODEL, "choices":[{"message":{"content":
             '{"probability":0.3,"reason":"uncertainty"}'}}],"usage":{"cost":0}}
        with patch.object(lab,"request_json",return_value=api) as call:
            r=lab.forecast_one(q,"FAKE")
        self.assertEqual(r["p_yes"],.3)
        self.assertFalse(r["submitted_to_metaculus"])
        self.assertEqual(call.call_args.kwargs["method"],"POST")
        self.assertEqual(call.call_args.args[0],lab.OPENROUTER_CHAT)
        body=json.loads(call.call_args.kwargs["data"])
        self.assertEqual(body["model"],lab.FREE_MODEL)
        self.assertEqual(body["reasoning"],{"enabled":False})
        lab.validate_record(r)

    def test_wrong_model_rejected(self):
        q=lab.normalize_post(sample_post(),now=NOW)
        api={"model":"some/paid-model", "choices":[{"message":{"content":
             '{"probability":0.5,"reason":"x"}'}}],"usage":{"cost":0}}
        with patch.object(lab,"request_json",return_value=api):
            with self.assertRaisesRegex(RuntimeError,"Served model"):
                lab.forecast_one(q,"FAKE")

    def test_nonzero_cost_rejected(self):
        q=lab.normalize_post(sample_post(),now=NOW)
        api={"model":lab.FREE_MODEL, "choices":[{"message":{"content":
             '{"probability":0.5,"reason":"x"}'}}],"usage":{"cost":1}}
        with patch.object(lab,"request_json",return_value=api):
            with self.assertRaisesRegex(RuntimeError,"nonzero cost"):
                lab.forecast_one(q,"FAKE")

    def test_normalize_final_content(self):
        self.assertEqual(lab.normalize_final_content([{"type":"text","text":"hi"}]),"hi")
        self.assertEqual(lab.normalize_final_content(None),"")

    def test_record_sha256_mismatch_rejected(self):
        r=sample_record()
        lab.validate_record(r)
        r["p_yes"]=.9
        with self.assertRaisesRegex(ValueError,"hash mismatch"):
            lab.validate_record(r)

    def test_read_jsonl(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"a.jsonl"
            lab.write_jsonl(path,[sample_record()])
            self.assertEqual(len(lab.read_jsonl(path)),1)

    def test_resolved_scoring(self):
        r=sample_record()
        res=[{"question_id":"98765","outcome":"no",
              "resolved_at_utc":"2026-12-11T00:00:00Z",
              "verification_url":"https://www.metaculus.com/questions/43210/"}]
        resolved,pending=lab.score([r],res)
        self.assertEqual((len(resolved),len(pending)),(1,0))
        self.assertLess(lab.brier(.3,0),lab.brier(.5,0))
        self.assertIn("NOT MET",lab.report(resolved,pending))

    def test_missing_resolutions_are_pending(self):
        resolved,pending=lab.score([sample_record()],[])
        self.assertEqual((len(resolved),len(pending)),(0,1))
        self.assertIn("Accuracy cannot be assessed",lab.report(resolved,pending))

    def test_ambiguous_not_treated_as_no(self):
        with self.assertRaisesRegex(ValueError,"Only explicit"):
            lab.score([sample_record()],[{
                "question_id":"98765","outcome":"ambiguous",
                "resolved_at_utc":"2026-12-11T00:00:00Z",
                "verification_url":"https://www.metaculus.com/questions/43210/"}])

    def test_pre_outcome_constraint(self):
        with self.assertRaisesRegex(ValueError,"LEAKAGE"):
            lab.score([sample_record()],[{
                "question_id":"98765","outcome":"yes",
                "resolved_at_utc":"2026-11-24T02:00:00Z",
                "verification_url":"https://www.metaculus.com/questions/43210/"}])

    def test_duplicate_records_rejected(self):
        r=sample_record()
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            lab.score([r,r],[])

    def test_quota_missing_is_unknown(self):
        with patch.object(lab,"request_json",return_value={"data":{}}):
            self.assertIsNone(lab.free_quota_remaining("FAKE"))

    def test_quota_available(self):
        with patch.object(lab,"request_json",return_value={
            "data":{"free_model_daily_requests":{"remaining":8}}}):
            self.assertEqual(lab.free_quota_remaining("FAKE"),8)

if __name__ == "__main__":
    unittest.main()
