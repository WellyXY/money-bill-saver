"""Financial evidence checks use synthetic invoices only."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / "skills/money-bill-saver/scripts/check_facts.py"
spec = importlib.util.spec_from_file_location("check_facts", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def invoice(record="inv-1", due="5.00", lines=None, **changes):
    result = {"record_id": record, "vendor": "railway", "account_ref": "acct-a", "invoice_ref": "bill-a",
              "subscription_ref": "sub-a", "issued_on": "2026-08-01", "currency": "USD", "amount_due": due,
              "line_items_complete": True, "source_refs": ["src-1"],
              "line_items": lines if lines is not None else [{"label": "Hobby", "kind": "base", "amount": "5.00"}],
              "subscription": {"cycle": "monthly", "activity": "unknown", "dependency": "unknown", "recurring": True}}
    result.update(changes)
    return result


def facts(*invoices):
    return {"schema_version": "0.1", "scope": {"start": "2026-07-01", "end": "2026-09-01"},
            "sources": [{"id": "src-1", "type": "pdf", "locator": "synthetic.pdf#page=1"},
                        {"id": "src-2", "type": "receipt", "locator": "synthetic-copy.pdf#page=1"}],
            "invoices": list(invoices or [invoice()])}


class ReconciliationTests(unittest.TestCase):
    def test_base_invoice_due_is_not_payment(self):
        result = checker.check_facts(facts())
        self.assertEqual(result["invoices"][0]["status"], "reconciled")
        self.assertEqual(result["documented_due"], [{"currency": "USD", "amount": "5.00", "invoice_count": 1}])
        self.assertNotIn("paid", result)

    def test_gross_allowance_tax_and_mixed_periods(self):
        lines = [{"label": "Hobby", "kind": "base", "amount": "5.00", "period": {"start": "2026-08-01", "end": "2026-09-01"}},
                 {"label": "Resources", "kind": "usage_gross", "amount": "30.00", "period": {"start": "2026-07-01", "end": "2026-08-01"}},
                 {"label": "Allowance", "kind": "included_usage", "amount": "-5.00"},
                 {"label": "Tax", "kind": "tax", "amount": "2.40"}]
        item = checker.check_facts(facts(invoice(due="32.40", lines=lines)))["invoices"][0]
        self.assertEqual((item["known_sum"], item["delta"], item["status"]), ("32.40", "0.00", "reconciled"))
        self.assertEqual(item["line_items"][1]["period"], lines[1]["period"])

    def test_overage_double_credit_requires_review_despite_equal_sum(self):
        lines = [{"label": "Overage", "kind": "usage_overage", "amount": "30"},
                 {"label": "Allowance", "kind": "included_usage", "amount": "-5"}]
        result = checker.check_facts(facts(invoice(due="25", lines=lines)))
        item = result["invoices"][0]
        self.assertEqual(item["status"], "reconciled")
        self.assertIn("possible_included_usage_double_credit", item["excluded_reasons"])
        self.assertEqual(result["documented_due"], [])

    def test_incomplete_residual_is_not_mismatch(self):
        result = checker.check_facts(facts(invoice(due="32.40", line_items_complete=False)))
        item = result["invoices"][0]
        self.assertEqual((item["status"], item["delta"], item["delta_meaning"]), ("incomplete", "27.40", "unexplained_residual"))
        self.assertEqual(result["counts"]["excluded_records"], 1)
        unknown = invoice(lines=[{"label": "Unknown", "kind": "other", "amount": None}])
        item = checker.check_facts(facts(unknown))["invoices"][0]
        self.assertIsNone(item["known_sum"])
        self.assertIsNone(item["delta"])

    def test_complete_arithmetic_mismatch(self):
        item = checker.check_facts(facts(invoice(due="7")))["invoices"][0]
        self.assertEqual(item["status"], "mismatch")
        self.assertEqual(item["delta"], "2.00")

    def test_duplicate_documents_merge_not_repeated_payments(self):
        second = invoice(record="inv-2", due="5.0", source_refs=["src-2"])
        second["line_items"][0]["amount"] = "5"
        result = checker.check_facts(facts(invoice(), second))
        self.assertEqual(result["counts"]["unique_records"], 1)
        self.assertEqual(result["invoices"][0]["source_refs"], ["src-1", "src-2"])
        self.assertEqual(result["invoices"][0]["line_items"][0]["source_refs"], ["src-1", "src-2"])
        self.assertEqual(result["documented_due"][0]["amount"], "5.00")

    def test_conflicting_duplicate_excluded(self):
        second = invoice(record="inv-2", due="6", source_refs=["src-2"])
        result = checker.check_facts(facts(invoice(), second))
        self.assertEqual(result["invoices"][0]["status"], "identity_conflict")
        self.assertEqual(len(result["invoices"][0]["observations"]), 2)
        self.assertEqual(result["documented_due"], [])

    def test_subscription_observations_preserve_their_own_sources(self):
        first = invoice()
        second = invoice(record="inv-2", source_refs=["src-2"])
        first["subscription"]["owner"] = "Reported owner A"
        second["subscription"]["owner"] = "Reported owner B"
        result = checker.check_facts(facts(first, second))["invoices"][0]
        self.assertEqual(result["status"], "reconciled")
        observations = result["subscription_observations"]
        self.assertEqual(observations[0]["source_refs"], ["src-1"])
        self.assertEqual(observations[1]["source_refs"], ["src-2"])
        self.assertEqual(observations[1]["subscription"]["owner"], "Reported owner B")

    def test_reordered_duplicate_lines_keep_all_line_evidence(self):
        lines = [{"label": "Base", "kind": "base", "amount": "5"},
                 {"label": "Usage", "kind": "usage_gross", "amount": "10", "source_refs": ["src-2"]}]
        result = checker.check_facts(facts(invoice(due="15", lines=lines),
                                          invoice(record="inv-2", due="15.00", lines=list(reversed(lines)))))
        self.assertEqual(result["counts"]["unique_records"], 1)
        self.assertEqual(result["invoices"][0]["source_refs"], ["src-1", "src-2"])
        self.assertEqual(result["documented_due"][0]["amount"], "15")

    def test_separate_accounts_and_currencies(self):
        items = [invoice(), invoice(record="inv-2", account_ref="acct-b"),
                 invoice(record="inv-3", account_ref="acct-c", currency="TWD")]
        result = checker.check_facts(facts(*items))
        self.assertEqual(result["documented_due"], [{"currency": "TWD", "amount": "5.00", "invoice_count": 1},
                                                  {"currency": "USD", "amount": "10.00", "invoice_count": 2}])

    def test_unknown_identity_stays_separate_and_excluded(self):
        result = checker.check_facts(facts(invoice(account_ref=None, subscription_ref=None),
                                          invoice(record="inv-2", account_ref=None)))
        self.assertEqual(result["counts"]["unique_records"], 2)
        self.assertEqual(result["documented_due"], [])
        self.assertIn("subscription_identity_unknown", result["invoices"][0]["warnings"])
        self.assertEqual(result["invoices"][0]["status"], "reconciled")

    def test_annual_cancellation_preserves_service_period_and_unknown_activity(self):
        inv = invoice(lines=[{"label": "Annual", "kind": "base", "amount": "5.00",
                              "period": {"start": "2026-01-15", "end": "2027-01-15"}}])
        inv["subscription"] = {"cycle": "annual", "recurring": False, "renews_on": None,
                               "activity": "unknown", "dependency": "unknown"}
        item = checker.check_facts(facts(inv))["invoices"][0]
        self.assertEqual(item["line_items"][0]["period"]["end"], "2027-01-15")
        self.assertEqual(item["subscription_observations"][0]["subscription"], inv["subscription"])
        self.assertNotIn("recommendation", item)

    def test_exact_high_precision_amounts_and_negative_credit(self):
        large = "1234567890123456789012345678901234567890.00000000000000000001"
        item = checker.check_facts(facts(invoice(due=large, lines=[{"label": "Exact", "kind": "other", "amount": large}])))["invoices"][0]
        self.assertEqual(item["known_sum"], large)
        self.assertEqual(item["status"], "reconciled")
        item = checker.check_facts(facts(invoice(due="-5.00", lines=[{"label": "Credit", "kind": "credit_applied", "amount": "-5.00"}])))["invoices"][0]
        self.assertEqual(item["delta"], "0.00")
        negative = "-" + large
        item = checker.check_facts(facts(invoice(due=negative, lines=[{"label": "Credit", "kind": "credit_applied", "amount": negative}])))["invoices"][0]
        self.assertEqual(item["status"], "reconciled")


class ValidationTests(unittest.TestCase):
    def test_invalid_money_formats(self):
        for value in (5.0, 5, True, "1e3", "NaN", "Infinity", "1,000", "$5", " 5", "5 ", ".5", "5.", "１２"):
            with self.subTest(value=value), self.assertRaises(checker.FactsError):
                checker.check_facts(facts(invoice(due=value)))

    def test_invalid_refs_dates_identifiers_and_enums(self):
        changes = [{"source_refs": ["missing"]}, {"source_refs": []}, {"record_id": " "},
                   {"issued_on": "2026-02-30"}, {"issued_on": "20260801"}, {"currency": "usd"},
                   {"account_ref": ""}, {"line_items_complete": 1}, {"subscription": {"activity": "probably_unused"}}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(checker.FactsError):
                checker.check_facts(facts(invoice(**change)))
        data = facts(invoice(), invoice())
        with self.assertRaises(checker.FactsError):
            checker.check_facts(data)
        inv = invoice()
        inv["line_items"][0]["source_refs"] = ["missing"]
        with self.assertRaises(checker.FactsError):
            checker.check_facts(facts(inv))
        inv["line_items"][0].pop("source_refs")
        inv["line_items"][0]["period"] = {"start": "2026-08-01", "end": "2026-08-01"}
        with self.assertRaises(checker.FactsError):
            checker.check_facts(facts(inv))

    def test_cli_preserves_output_requires_force_and_preserves_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "facts.json"
            output = Path(directory) / "checks.json"
            source.write_text(json.dumps(facts()), encoding="utf-8")
            output.write_text("existing output", encoding="utf-8")
            command = [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(output.read_text(), "existing output")
            run = subprocess.run(command + ["--force"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(output.read_text())["schema_version"], "0.1")
            original = source.read_text()
            run = subprocess.run(command[:-1] + [str(source), "--force"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(source.read_text(), original)

    def test_cli_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "facts.json"
            output = Path(directory) / "checks.json"
            source.write_text('{"schema_version":"0.1","schema_version":"0.1"}')
            run = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertIn("duplicate object key", run.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
