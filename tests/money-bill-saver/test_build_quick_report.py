import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/money-bill-saver"
spec = importlib.util.spec_from_file_location("quick_builder", SKILL / "scripts/build_quick_report.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class QuickReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.data = json.loads((SKILL / "assets/example-quick.json").read_text())

    def build(self):
        return builder.build(self.data, self.base)

    def test_four_sections_dates_and_partial_cost(self):
        self.data["cases"].append({
            "id": "support-case", "name": "Example support case", "vendor": "example-support", "account_ref": "personal",
            "status": "uncertain", "status_note": "The cited message asks for a billing explanation.",
            "source_refs": ["synthetic-other"],
            "issue": {"group": "other", "title": "Confirm account adjustment", "summary": "An adjustment is mentioned without a posted date.",
                      "next": "Check the account ledger.", "source_refs": ["synthetic-other"]}
        })
        report = self.build()
        self.assertEqual(report["report_mode"], "focused")
        self.assertEqual(report["computed"]["service_count"], 2)
        self.assertEqual(report["computed"]["refund_count"], 1)
        self.assertEqual(report["computed"]["other_issue_count"], 1)
        self.assertEqual(report["computed"]["monthly_baseline"], {"USD": "12.00"})
        self.assertEqual(len(report["monthly_cost"]["unknowns"]), 1)
        self.assertEqual(len(report["appendix"]), 1)
        dates = report["subscriptions"][0]["billing_dates"]
        self.assertEqual(dates["last_invoice"]["date"], "2030-01-01")
        self.assertEqual(dates["last_charge"]["date"], "2030-01-02")
        self.assertEqual(dates["next_renewal"]["status"], "unknown")

    def test_run_writes_page_without_invoice_or_event_authoring(self):
        path = self.base / "quick.json"
        path.write_text(json.dumps(self.data))
        report = builder.run(path, self.base)
        self.assertTrue((self.base / "dashboard.html").exists())
        self.assertEqual(report["report_mode"], "focused")
        self.assertEqual(json.loads((self.base / "dashboard.json").read_text())["report_mode"], "focused")
        with self.assertRaisesRegex(ValueError, "Output exists"):
            builder.run(path, self.base)

    def test_invoice_does_not_become_cash_charge_or_monthly_price(self):
        service = self.data["services"][1]
        self.assertEqual(self.build()["subscriptions"][1]["billing_dates"]["last_charge"]["status"], "unknown")
        service["cost"]["include_monthly"] = True
        with self.assertRaisesRegex(ValueError, "Only observed current services"):
            self.build()
        service["status"] = "observed"
        with self.assertRaisesRegex(ValueError, "recurring amount"):
            self.build()

    def test_unknown_source_and_unsupported_active_claim_rejected(self):
        self.data["services"][0]["source_refs"] = ["not-a-real-source"]
        with self.assertRaisesRegex(ValueError, "unknown source"):
            self.build()
        self.data["services"][0]["source_refs"] = []
        with self.assertRaisesRegex(ValueError, "needs a source ID"):
            self.build()

    def test_past_renewal_and_future_charge_rejected(self):
        service = self.data["services"][0]
        service["dates"]["next_renewal"] = {"date": "2030-01-10", "source_refs": ["synthetic-plan"]}
        with self.assertRaisesRegex(ValueError, "past schedule"):
            self.build()
        service["dates"].pop("next_renewal")
        service["dates"]["last_charge"]["date"] = "2030-01-16"
        with self.assertRaisesRegex(ValueError, "after the report date"):
            self.build()

    def test_timestamp_boundaries_use_declared_timezone(self):
        self.data["scope"]["timezone"] = "America/Los_Angeles"
        service = self.data["services"][0]
        service["dates"]["last_charge"]["date"] = "2030-01-16T01:00:00Z"
        self.assertEqual(self.build()["subscriptions"][0]["billing_dates"]["last_charge"]["date"],
                         "2030-01-16T01:00:00Z")
        service["dates"]["last_charge"]["date"] = "2030-01-16T09:00:00Z"
        with self.assertRaisesRegex(ValueError, "after the report date"):
            self.build()

    def test_saved_source_index_avoids_rewriting_source_metadata(self):
        sources = self.data.pop("sources")
        (self.base / "source-index.json").write_text(json.dumps({"sources": sources}))
        self.data["source_index"] = "source-index.json"
        self.assertEqual(self.build()["subscriptions"][0]["evidence"][0]["id"], "synthetic-plan")
        self.data["source_index"] = "../source-index.json"
        with self.assertRaisesRegex(ValueError, "traverse"):
            self.build()

    def test_force_cannot_replace_source_index(self):
        self.data.pop("sources")
        self.data["source_index"] = "dashboard.json"
        index = self.base / "dashboard.json"
        index.write_text(json.dumps({"sources": json.loads((SKILL / "assets/example-quick.json").read_text())["sources"]}))
        input_file = self.base / "quick.json"
        input_file.write_text(json.dumps(self.data))
        before = index.read_bytes()
        with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
            builder.run(input_file, self.base, force=True)
        self.assertEqual(index.read_bytes(), before)

    def test_refund_basis_and_cited_appendix_required(self):
        self.data["services"][1]["issue"].pop("amount_label")
        with self.assertRaisesRegex(ValueError, "amount_label"):
            self.build()
        self.data["services"][1]["issue"]["amount_label"] = "Amount unknown"
        self.data["appendix"][0]["source_refs"] = []
        with self.assertRaisesRegex(ValueError, "source ID"):
            self.build()


if __name__ == "__main__":
    unittest.main()
