"""Cross-merchant billing scenarios; every document and identity is synthetic."""

from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "skills/subscription-audit/scripts/check_facts.py"
SPEC = importlib.util.spec_from_file_location("generic_bills_checker", SCRIPT)
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def bill(record, vendor, currency, due, lines, subscription=None, **changes):
    result = {
        "record_id": record,
        "vendor": vendor,
        "account_ref": f"synthetic-account-{vendor}",
        "invoice_ref": f"synthetic-document-{record}",
        "subscription_ref": f"synthetic-subscription-{vendor}",
        "issued_on": "2026-09-01",
        "currency": currency,
        "amount_due": due,
        "line_items_complete": True,
        "source_refs": ["synthetic-invoice"],
        "line_items": lines,
    }
    if subscription is not None:
        result["subscription"] = subscription
    result.update(changes)
    return result


def evidence(*bills):
    return {
        "schema_version": "0.1",
        "scope": {
            "description": "Synthetic cross-merchant documents; no live accounts",
            "start": "2026-01-01",
            "end": "2027-01-01",
            "limitations": ["No independently verified cash settlement or usage"],
        },
        "sources": [
            {"id": "synthetic-invoice", "type": "pdf", "locator": "synthetic/bill.pdf#page=1"},
            {"id": "synthetic-receipt", "type": "receipt", "locator": "synthetic/receipt.pdf#page=1"},
            {"id": "synthetic-context", "type": "user_statement", "locator": "synthetic/context.txt"},
        ],
        "invoices": list(bills),
    }


class GenericBillsTests(unittest.TestCase):
    def test_annual_membership_retains_full_due_and_service_period(self):
        period = {"start": "2026-09-01", "end": "2027-09-01"}
        inv = bill("annual", "example-fitness", "JPY", "10800", [
            {"label": "Annual membership", "kind": "base", "amount": "12000", "period": period},
            {"label": "Annual promotion", "kind": "discount", "amount": "-1200"},
        ], {"cycle": "annual", "recurring": True, "activity": "unknown", "dependency": "unknown"})

        result = checker.check_facts(evidence(inv))
        self.assertEqual(result["documented_due"], [{"currency": "JPY", "amount": "10800", "invoice_count": 1}])
        checked = result["invoices"][0]
        self.assertEqual(checked["line_items"][0]["period"], period)
        self.assertEqual(checked["subscription_observations"][0]["subscription"]["cycle"], "annual")
        self.assertNotIn("monthly_cost", checked)

    def test_telecom_variable_usage_preserves_three_decimal_currency(self):
        inv = bill("mobile", "example-mobile", "BHD", "3.740", [
            {"label": "Access fee", "kind": "base", "amount": "2.500"},
            {"label": "Metered calls", "kind": "usage_gross", "amount": "0.875"},
            {"label": "Roaming", "kind": "other", "amount": "0.025"},
            {"label": "Tax", "kind": "tax", "amount": "0.340"},
        ], {"cycle": "usage", "recurring": True, "activity": "unknown", "dependency": "unknown"})

        result = checker.check_facts(evidence(inv))
        self.assertEqual(result["invoices"][0]["delta"], "0.000")
        self.assertEqual(result["documented_due"][0]["amount"], "3.740")
        self.assertNotIn("annual_spend", result)

    def test_billed_renewal_after_trial_does_not_establish_use_or_refund(self):
        observation = {"plan": "Post-trial monthly", "cycle": "monthly", "recurring": True,
                       "renews_on": "2026-10-01", "activity": "unknown", "dependency": "unknown"}
        inv = bill("renewal", "example-streaming", "USD", "14.99", [
            {"label": "Monthly renewal after trial", "kind": "base", "amount": "14.99"},
        ], observation)

        result = checker.check_facts(evidence(inv))
        checked = result["invoices"][0]
        self.assertEqual(checked["status"], "reconciled")
        self.assertEqual(checked["subscription_observations"][0]["subscription"], observation)
        for unsupported in ("paid", "unused", "refund_eligible", "recommendation", "cash_refund"):
            self.assertNotIn(unsupported, checked)
            self.assertNotIn(unsupported, result)

    def test_one_off_repair_bill_does_not_require_a_subscription(self):
        inv = bill("repair", "example-repair-shop", "TWD", "1890", [
            {"label": "Replacement part", "kind": "other", "amount": "1200"},
            {"label": "Labour", "kind": "other", "amount": "600"},
            {"label": "Tax", "kind": "tax", "amount": "90"},
        ], {"cycle": "one_time", "recurring": False}, subscription_ref=None)

        result = checker.check_facts(evidence(inv))
        checked = result["invoices"][0]
        self.assertTrue(checked["included_in_documented_due"])
        self.assertIsNone(checked["subscription_ref"])
        self.assertFalse(checked["subscription_observations"][0]["subscription"]["recurring"])
        self.assertEqual(result["documented_due"][0]["amount"], "1890")
        self.assertNotIn("subscription_identity_unknown", checked["warnings"])

    def test_receipt_and_invoice_observations_count_one_obligation_not_payments(self):
        original = bill("invoice-view", "example-learning", "EUR", "24.00", [
            {"label": "Monthly course access", "kind": "base", "amount": "24.00"},
        ])
        receipt_view = deepcopy(original)
        receipt_view.update(record_id="receipt-view", source_refs=["synthetic-receipt"])

        result = checker.check_facts(evidence(original, receipt_view))
        self.assertEqual(result["counts"]["unique_records"], 1)
        self.assertEqual(result["documented_due"][0]["amount"], "24.00")
        self.assertEqual(result["invoices"][0]["source_refs"], ["synthetic-invoice", "synthetic-receipt"])
        self.assertNotIn("payment_count", result)
        self.assertNotIn("duplicate_charge", result["invoices"][0])

    def test_equal_amounts_on_distinct_invoices_do_not_become_duplicate_payments(self):
        first = bill("first", "example-utility", "GBP", "50.00", [
            {"label": "Metered supply", "kind": "usage_gross", "amount": "50.00"},
        ])
        second = deepcopy(first)
        second.update(record_id="second", invoice_ref="synthetic-document-second", issued_on="2026-08-01")

        result = checker.check_facts(evidence(first, second))
        self.assertEqual(result["counts"]["unique_records"], 2)
        self.assertEqual(result["documented_due"], [{"currency": "GBP", "amount": "100.00", "invoice_count": 2}])
        self.assertTrue(all(inv["status"] == "reconciled" for inv in result["invoices"]))
        self.assertTrue(all("duplicate_charge" not in inv for inv in result["invoices"]))

    def test_cancellation_context_does_not_erase_final_past_period_bill(self):
        service_period = {"start": "2026-08-01", "end": "2026-09-01"}
        inv = bill("final", "example-broadband", "CAD", "45.00", [
            {"label": "Final prior-period service", "kind": "base", "amount": "45.00", "period": service_period},
        ], {"cycle": "monthly", "recurring": False, "activity": "inactive_confirmed",
            "dependency": "noncritical_confirmed", "renews_on": None},
            source_refs=["synthetic-invoice", "synthetic-context"])

        result = checker.check_facts(evidence(inv))
        self.assertEqual(result["documented_due"][0]["amount"], "45.00")
        checked = result["invoices"][0]
        self.assertEqual(checked["line_items"][0]["period"], service_period)
        self.assertEqual(checked["subscription_observations"][0]["source_refs"], inv["source_refs"])
        self.assertNotIn("wrongful_charge", checked)

    def test_negative_document_amount_is_not_cash_received_and_currencies_stay_separate(self):
        # v0.1 checks the printed signed balance. It has no credit-note settlement model.
        adjustment = bill("adjustment", "example-storage", "EUR", "-8.50", [
            {"label": "Signed adjustment balance", "kind": "other", "amount": "-8.50"},
        ], subscription_ref=None)
        purchase = bill("purchase", "example-news", "USD", "8.50", [
            {"label": "Issue purchase", "kind": "other", "amount": "8.50"},
        ], {"cycle": "one_time", "recurring": False}, subscription_ref=None)

        result = checker.check_facts(evidence(adjustment, purchase))
        self.assertEqual(result["documented_due"], [
            {"currency": "EUR", "amount": "-8.50", "invoice_count": 1},
            {"currency": "USD", "amount": "8.50", "invoice_count": 1},
        ])
        self.assertNotIn("cash_refund", result)
        self.assertNotIn("recovered", result)


if __name__ == "__main__":
    unittest.main()
