import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import forecastlab_v04 as v
import forecastlab_v03 as lab

NOW=datetime(2026,11,24,3,tzinfo=timezone.utc)
def post(id,days=5):
    return {"id":id,"question":{"id":id+100,"title":"Will NVIDIA announce a new product?",
        "type":"binary","status":"open","resolution_criteria":"Official announcement",
        "scheduled_close_time":(NOW+timedelta(days=1)).isoformat(),
        "scheduled_resolve_time":(NOW+timedelta(days=days)).isoformat()}}
def question():
    return v.rank_candidates([post(1)],NOW)[0]
def snapshot():
    return {"status":"ok","articles":[{"title":"Company discusses new product",
        "url":"https://example.com/news","seen_at":NOW.isoformat(),"domain":"example.com"}]}
def pair():
    p={"schema":v.SCHEMA,"status":"complete","question":question(),
        "control":{"p_yes":.6,"recorded_at":NOW.isoformat()},
        "news":{"p_yes":.8,"recorded_at":NOW.isoformat()}}
    p["sha256"]=v.digest(p)
    return p

class Tests(unittest.TestCase):
    def test_rank_short_and_exclude(self):
        result=v.rank_candidates([post(1,20),post(2,2),post(3,60),post(4,1),post(2,2)],NOW,seen={104})
        self.assertEqual([x["post_id"] for x in result],[2,1])
    def test_close_buffer(self):
        x=post(1)
        x["question"]["scheduled_close_time"]=(NOW+timedelta(minutes=5)).isoformat()
        self.assertEqual(v.rank_candidates([x],NOW),[])
    def test_query(self):
        self.assertEqual(v.search_terms("Will NVIDIA announce a new product?"),'"nvidia" "new" "product"')
    def test_news_date_url_dedup(self):
        raw={"title":"Headline","url":"https://example.com/article","seendate":"20261124T020000Z"}
        with patch.object(lab,"request_json",return_value={"articles":[raw,raw,
            dict(raw,title="Future",seendate="20261125T020000Z"),
            dict(raw,title="Bad",url="file:///etc/passwd")]}):
            snap=v.news_snapshot(question(),NOW)
        self.assertEqual(len(snap["articles"]),1)
        self.assertEqual(snap["status"],"ok")
    def test_news_unavailable(self):
        with patch.object(lab,"request_json",side_effect=RuntimeError("unavailable")):
            self.assertEqual(v.news_snapshot(question(),NOW)["status"],"unavailable")
    def test_payload_only_evidence_changes(self):
        a=v.payload(question())
        b=v.payload(question(),snapshot())
        self.assertEqual(a["model"],lab.FREE_MODEL)
        self.assertEqual(a["messages"][0],b["messages"][0])
        x=json.loads(a["messages"][1]["content"]);y=json.loads(b["messages"][1]["content"])
        self.assertEqual(x.pop("headlines"),[])
        self.assertEqual(len(y.pop("headlines")),1)
        self.assertEqual(x,y)
    def test_zero_cost_required(self):
        data={"model":lab.FREE_MODEL,"usage":{"cost":0},"choices":[{"message":{
            "content":'{"probability":0.7,"reason":"uncertain"}'}}]}
        with patch.object(lab,"request_json",return_value=data) as call:
            self.assertEqual(v.predict(question(),"FAKE")["p_yes"],.7)
            self.assertEqual(call.call_args.args[0],lab.OPENROUTER_CHAT)
        for cost in (None,.01,float("nan")):
            bad=copy.deepcopy(data);bad["usage"]["cost"]=cost
            with patch.object(lab,"request_json",return_value=bad):
                with self.assertRaises(RuntimeError):v.predict(question(),"FAKE")
    def test_wrong_model(self):
        with patch.object(lab,"request_json",return_value={"model":"paid"}):
            with self.assertRaises(RuntimeError):v.predict(question(),"FAKE")
    def test_pair_scores(self):
        rows=v.pair_metrics([pair()],{"101":{"outcome":1,"resolved_at":"2026-12-01T00:00:00Z"}})
        self.assertAlmostEqual(rows[0]["control_brier"],.16)
        self.assertAlmostEqual(rows[0]["news_brier"],.04)
        self.assertAlmostEqual(rows[0]["news_gain"],.12)
    def test_pending(self):
        self.assertEqual(v.pair_metrics([pair()],{}),[])
    def test_hash(self):
        p=pair();p["news"]["p_yes"]=.99
        with self.assertRaisesRegex(ValueError,"hash"):v.pair_metrics([p],{})
    def test_late(self):
        with self.assertRaisesRegex(ValueError,"Late"):
            v.pair_metrics([pair()],{"101":{"outcome":0,"resolved_at":NOW.isoformat()}})
    def test_duplicate(self):
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            v.pair_metrics([pair(),pair()],{"101":{"outcome":1,"resolved_at":"2026-12-01T00:00:00Z"}})
