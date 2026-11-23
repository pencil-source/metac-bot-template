"""History scoring tests: no external network calls, no credentials."""
from datetime import datetime, timezone
from io import BytesIO
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parent))
import forecastlab_v03 as lab
import history_scoring as history

def fake_record(when="2026-11-24T00:00:00+00:00",p=.7):
    rec={
        "schema":lab.FORECAST_SCHEMA,"recorded_at_utc":when,
        "post_id":46544,"question_id":46807,
        "title":"Will an event occur by December 4, 2026?",
        "source_url":"https://www.metaculus.com/questions/46544/",
        "expected_resolve_at":"2026-12-04T00:00:00+00:00",
        "close_at":"2026-12-01T00:00:00+00:00",
        "p_yes":p,"baseline_p_yes":.5,
        "requested_model":lab.FREE_MODEL,"served_model":lab.FREE_MODEL,
        "provider_reported_cost_usd":0,"reason":"test",
        "submitted_to_metaculus":False
    }
    rec["sha256"]=hashlib.sha256(json.dumps(rec,sort_keys=True,
          ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
    return rec

def zipped_forecasts(*records):
    buf=BytesIO()
    with ZipFile(buf,"w") as z:
        z.writestr("forecasts.jsonl","".join(json.dumps(r)+"\n" for r in records))
    return buf.getvalue()

class HistoryScoringTests(unittest.TestCase):
    def test_yes_resolution(self):
        q={"id":46807,"status":"resolved","resolution":"yes",
           "actual_resolve_time":"2026-12-04T12:00:00Z"}
        self.assertEqual(history.parse_resolution(q)[0],1)

    def test_no_resolution(self):
        q={"status":"resolved","resolution":0,
           "actual_resolve_time":"2026-12-04T12:00:00Z"}
        self.assertEqual(history.parse_resolution(q)[0],0)

    def test_ambiguous_hidden_and_unresolved(self):
        for q in [
           {"status":"resolved","resolution":"ambiguous","actual_resolve_time":"2026-12-05T00:00:00Z"},
           {"status":"resolved","resolution":None,"actual_resolve_time":"2026-12-05T00:00:00Z"},
           {"status":"open","resolution":"yes","actual_resolve_time":"2026-12-05T00:00:00Z"},
           {"status":"resolved","resolution":"annulled","actual_resolve_time":"2026-12-05T00:00:00Z"}
        ]:
            with self.subTest(q=q):
                self.assertIsNone(history.parse_resolution(q))

    def test_read_zip_file(self):
        rows=history.decode_forecasts(zipped_forecasts(fake_record()))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["question_id"],46807)

    def test_empty_zip_no_forecast(self):
        buf=BytesIO()
        with ZipFile(buf,"w") as z:z.writestr("ignore.txt","nothing")
        self.assertEqual(history.decode_forecasts(buf.getvalue()),[])

    def test_invalid_zip(self):
        with self.assertRaises(ValueError):
            history.decode_forecasts(b"not a zip")

    def test_bad_hash_refused(self):
        r=fake_record();r["p_yes"]=.1
        with self.assertRaisesRegex(ValueError,"hash mismatch"):
            history.decode_forecasts(zipped_forecasts(r))

    def test_get_official_outcome(self):
        q={"question":{"id":46807,"status":"resolved","resolution":"no",
                      "actual_resolve_time":"2026-12-04T12:00:00Z"}}
        with patch.object(lab,"get_post",return_value=q):
            resolved,pending,errors=history.check_metaculus_resolutions([fake_record()])
        self.assertEqual((len(resolved),len(pending),len(errors)),(1,0,0))
        evaluated,_=lab.score([fake_record()],resolved)
        self.assertEqual(evaluated[0]["y"],0)

    def test_restricted_resolution_remains_pending(self):
        q={"question":{"id":46807,"status":"resolved","resolution":None,
                      "actual_resolve_time":"2026-12-04T12:00:00Z"}}
        with patch.object(lab,"get_post",return_value=q):
            resolved,pending,errors=history.check_metaculus_resolutions([fake_record()])
        self.assertEqual((len(resolved),len(pending),len(errors)),(0,1,0))

    def test_network_failure_does_not_fabricate_no(self):
        with patch.object(lab,"get_post",side_effect=RuntimeError("HTTP 403")):
            resolved,pending,errors=history.check_metaculus_resolutions([fake_record()])
        self.assertEqual((len(resolved),len(pending),len(errors)),(0,1,1))

    def test_dedup_earliest_across_runs(self):
        runs={"workflow_runs":[
            {"id":2,"name":"PencilForecast v0.3 - research (manual, free only)",
             "status":"completed","conclusion":"success"},
            {"id":1,"name":"PencilForecast v0.3 integration smoke test (one free call)",
             "status":"completed","conclusion":"success"}]}
        artifacts={"artifacts":[{"id":200,"name":"pencil-forecast-research","expired":False}]}
        def response(path,token):
            return runs if path.endswith("runs?per_page=100") else artifacts
        artifacts_in_order=iter([
            zipped_forecasts(fake_record("2026-11-25T00:00:00+00:00",.9)),
            zipped_forecasts(fake_record("2026-11-24T00:00:00+00:00",.7))
        ])
        with patch.object(history,"github_get_json",side_effect=response),\
             patch.object(history,"github_get_artifact_zip",side_effect=lambda aid,key: next(artifacts_in_order)):
            # Choose the earliest forecast, never the later more accurate-looking one.
            selected,meta=history.load_history("FAKE",2)
        self.assertEqual(len(selected),1)
        self.assertEqual(selected[0]["p_yes"],.7)
        self.assertEqual(meta["duplicates_ignored"],1)

    def test_max_runs_bounded(self):
        with self.assertRaises(ValueError):
            history.load_history("FAKE",1000)

    def test_download_id_validation(self):
        with self.assertRaises(ValueError):
            history.github_get_artifact_zip(-2,"FAKE")

if __name__=="__main__":
    unittest.main()
