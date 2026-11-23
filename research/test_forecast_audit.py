"""Tests for the offline evaluation utility. Pure Python standard library."""
import csv
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from forecast_audit import brier, load_csv, log_loss, paired_interval, summarize

HEADER = ["question_id", "forecast_at", "resolved_at", "prediction",
          "baseline", "outcome", "model_version", "cost_usd"]
VALID = ["test-1", "2026-11-01T08:00:00+09:00",
         "2026-11-10T08:00:00+09:00", "0.7", "0.5", "1", "v1", "0"]

class TestAudit(unittest.TestCase):
    def write_csv(self, rows):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = pathlib.Path(tmp.name) / "predictions.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(HEADER)
            writer.writerows(rows)
        return path

    def test_valid(self):
        finished, pending = load_csv(self.write_csv([VALID]))
        self.assertEqual((len(finished),len(pending)), (1,0))
        self.assertIn("NOT PASSED", summarize(finished,pending))

    def test_prevents_leakage(self):
        row = VALID.copy()
        row[1] = "2026-11-11T08:00:00+09:00"
        with self.assertRaisesRegex(ValueError, "LEAKAGE"):
            load_csv(self.write_csv([row]))

    def test_rejects_duplicates(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_csv(self.write_csv([VALID, VALID]))

    def test_pending(self):
        row = VALID.copy()
        row[2] = ""
        row[5] = ""
        complete, pending = load_csv(self.write_csv([row]))
        self.assertEqual((len(complete),len(pending)), (0,1))

    def test_missing_timezone(self):
        row = VALID.copy()
        row[1] = "2026-11-01T08:00:00"
        with self.assertRaisesRegex(ValueError, "Timezone"):
            load_csv(self.write_csv([row]))

    def test_invalid_probability(self):
        row = VALID.copy()
        row[3] = "nan"
        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            load_csv(self.write_csv([row]))

    def test_negative_cost(self):
        row = VALID.copy()
        row[7] = "-1"
        with self.assertRaisesRegex(ValueError, "nonnegative"):
            load_csv(self.write_csv([row]))

    def test_metrics(self):
        self.assertAlmostEqual(brier(0.8, 1), 0.04)
        self.assertAlmostEqual(log_loss(.5, 1), .69314718056)
        self.assertEqual(paired_interval([.1]*10), (.1,.1))

if __name__ == "__main__":
    unittest.main()
