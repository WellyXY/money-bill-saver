import importlib.util
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "skills/money-bill-saver/scripts/phase_clock.py"
spec = importlib.util.spec_from_file_location("phase_clock", SCRIPT)
clock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(clock)


class PhaseClockTests(unittest.TestCase):
    def test_stops_at_failed_stage_without_restarting_or_advancing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.json"
            clock.begin(path, "test-revision", "replay", "six months", "test-model", "2026-09-17T00:00:00Z")
            first = clock.finish(path, "discovery", {"candidates": 20}, "2026-09-17T00:02:20Z")
            self.assertEqual(first["status"], "running")
            stopped = clock.finish(path, "evidence", {"material_messages": 4}, "2026-09-17T00:07:00Z")
            self.assertEqual(stopped["status"], "stop")
            self.assertEqual(stopped["phases"][-1]["result"], "over_budget")
            with self.assertRaisesRegex(ValueError, "stopped or completed"):
                clock.finish(path, "report", now="2026-09-17T00:07:01Z")
            with self.assertRaisesRegex(ValueError, "already exists"):
                clock.begin(path, "new", "replay", "six months", "test-model")
            clock.resume(path, "2026-09-17T01:00:00Z")
            recovered = clock.finish(path, "evidence", {"material_messages": 3}, "2026-09-17T01:04:00Z")
            self.assertEqual(recovered["status"], "running")
            self.assertEqual([row["result"] for row in recovered["phases"]],
                             ["within_budget", "over_budget", "within_budget"])
            self.assertEqual(recovered["elapsed_seconds"], 380)
            self.assertEqual(recovered["phases"][-1]["mode"], "replay")

    def test_records_all_phases_and_actual_overall_elapsed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.json"
            clock.begin(path, "test-revision", "replay", "six months", "test-model", "2026-09-17T00:00:00Z")
            for phase, end in (("discovery", "00:02:00"), ("evidence", "00:06:00"),
                               ("report", "00:08:00"), ("preview", "00:08:20")):
                result = clock.finish(path, phase, now=f"2026-09-17T{end}Z")
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["elapsed_seconds"], 500)
            self.assertEqual([row["phase"] for row in result["phases"]],
                             ["discovery", "evidence", "report", "preview"])


if __name__ == "__main__":
    unittest.main()
