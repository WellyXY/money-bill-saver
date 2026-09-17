import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/money-bill-saver"
spec = importlib.util.spec_from_file_location("audit_builder", SKILL / "scripts/build_audit.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BuildAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.data = json.loads((SKILL / "assets/example-audit.json").read_text())
        self.save()

    def save(self):
        (self.base / "audit.json").write_text(json.dumps(self.data))

    def build(self):
        return builder.build(self.data, self.base)[0]

    def row(self):
        return self.build()["dashboard.json"]["subscriptions"][0]

    def event(self, kind, occurred="2030-01-12", **fields):
        row = {"id": "event-" + str(len(self.data["events"])), "entity_id": "notes-personal", "type": kind,
               "occurred_on": occurred, "source_refs": ["synthetic-observations"], "note": "Synthetic observed event."}
        row.update(fields)
        self.data["events"].append(row)
        return row

    def test_example_builds_existing_contracts_and_accurate_dates(self):
        artifacts = self.build()
        report = artifacts["dashboard.json"]
        self.assertEqual(artifacts["facts.json"]["schema_version"], "0.1")
        self.assertEqual(artifacts["audit-evidence.json"]["scope"]["workflow_version"], "audit-1")
        self.assertEqual(report["computed"]["monthly_baseline"], {"USD": "12.00"})
        dates = report["subscriptions"][0]["billing_dates"]
        self.assertEqual(dates["last_invoice"]["date"], "2030-01-01")
        self.assertEqual(dates["last_charge"]["date"], "2030-01-01")
        self.assertEqual(dates["next_renewal"]["status"], "unknown")
        self.assertEqual(dates["next_renewal"]["related_date"]["date"], "2030-02-01")
        self.assertEqual(artifacts["checks.json"]["documented_due"][0]["amount"], "12.00")
        self.assertNotIn("outcomes.json", artifacts)
        self.assertEqual(self.data["invoices"][0].get("vendor"), None)  # input is not mutated

    def test_invoice_is_never_a_cash_payment(self):
        self.data["events"] = []
        self.assertEqual(self.row()["billing_dates"]["last_charge"]["status"], "unknown")

    def test_explained_one_time_purchase_remains_visible(self):
        entity = self.data["entities"][0]
        entity["kind"] = "case"
        entity["decision"]["review_group"] = "none"
        entity["cost"]["include_monthly"] = False
        report = self.build()["dashboard.json"]
        self.assertEqual(report["subscriptions"], [])
        self.assertEqual(len(report["other_cases"]), 1)
        self.assertEqual(report["appendix"][0]["name"], report["other_cases"][0]["name"])
        self.assertEqual(report["appendix"][0]["note"], entity["decision"]["status_note"])

    def test_undated_payment_keeps_observation_separate_and_does_not_claim_latest(self):
        self.event("payment_succeeded", None, observed_on="2030-01-14")
        row = self.row()
        last = row["billing_dates"]["last_charge"]
        self.assertIsNone(last["date"])
        self.assertEqual(last["status"], "unknown")
        self.assertEqual(last["related_date"]["date"], "2030-01-01")
        undated = next(e for e in row["evidence"] if e.get("id") == "event-2")
        self.assertIsNone(undated["date"])
        self.assertIn("Observed on 2030-01-14", undated["note"])

    def test_undated_invoice_does_not_make_older_invoice_the_latest(self):
        invoice = copy.deepcopy(self.data["invoices"][0])
        invoice.update(record_id="undated", invoice_ref="SYN-002", issued_on=None)
        self.data["invoices"].append(invoice)
        self.assertEqual(self.row()["billing_dates"]["last_invoice"]["status"], "unknown")

    def test_reactivation_invalidates_previous_disabled_state(self):
        self.event("renewal_disabled", "2030-01-09")
        self.event("subscription_reactivated", "2030-01-11")
        self.assertEqual(self.row()["billing_dates"]["next_renewal"]["status"], "unknown")

    def test_compatible_reactivation_and_schedule_from_same_source(self):
        self.event("subscription_reactivated")
        self.event("renewal_scheduled", renews_on="2030-02-12")
        self.assertEqual(self.row()["billing_dates"]["next_renewal"]["date"], "2030-02-12")

    def test_conflicting_schedule_and_disabled_event_remain_unknown(self):
        self.event("renewal_scheduled", renews_on="2030-02-12")
        self.event("renewal_disabled")
        self.assertEqual(self.row()["billing_dates"]["next_renewal"]["status"], "unknown")

    def test_undated_lifecycle_prevents_old_schedule_reuse(self):
        self.event("renewal_scheduled", renews_on="2030-02-12")
        self.event("subscription_cancelled", None, observed_on="2030-01-14")
        self.assertEqual(self.row()["billing_dates"]["next_renewal"]["status"], "unknown")

    def test_expired_schedule_is_not_advanced_automatically(self):
        self.event("renewal_scheduled", "2030-01-02", renews_on="2030-01-03")
        self.assertEqual(self.row()["billing_dates"]["next_renewal"]["status"], "unknown")

    def test_date_preserves_explicit_timezone_and_rejects_unqualified_clock(self):
        event = self.event("payment_succeeded", "2030-01-12T23:40:00-08:00")
        self.assertEqual(self.row()["billing_dates"]["last_charge"]["date"], event["occurred_on"])
        event["occurred_on"] = "2030-01-12T23:40:00"
        with self.assertRaises(ValueError):
            self.build()

    def test_as_of_uses_scope_timezone_for_timestamp_day_boundary(self):
        self.data["scope"]["timezone"] = "America/Los_Angeles"
        event = self.event("payment_succeeded", "2030-01-16T01:00:00Z")
        self.assertEqual(self.row()["billing_dates"]["last_charge"]["date"], event["occurred_on"])
        event["occurred_on"] = "2030-01-16T09:00:00Z"
        with self.assertRaisesRegex(ValueError, "after the report date"):
            self.build()

    def test_same_local_day_mixed_precision_does_not_claim_latest_clock_time(self):
        self.data["scope"]["timezone"] = "America/Los_Angeles"
        self.event("payment_succeeded", "2030-01-16T01:00:00Z")
        self.event("payment_succeeded", "2030-01-15")
        self.assertEqual(self.row()["billing_dates"]["last_charge"]["date"], "2030-01-15")

    def test_duplicate_ids_and_missing_references_fail(self):
        original = copy.deepcopy(self.data)
        for collection, field in (("entities", "id"), ("events", "id"), ("invoices", "record_id"), ("sources", "id")):
            with self.subTest(collection=collection):
                self.data = copy.deepcopy(original)
                self.data[collection].append(copy.deepcopy(self.data[collection][0]))
                with self.assertRaisesRegex(ValueError, "Duplicate"):
                    self.build()
        self.data = original
        self.data["events"][0]["source_refs"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "unknown source"):
            self.build()

    def test_decimal_monthly_estimates_and_accounts_currencies_stay_separate(self):
        base_entity = self.data["entities"][0]
        base_entity["cost"] = {"kind": "fixed_term", "amount": "1.00", "currency": "USD", "months": 6,
                               "include_monthly": True, "basis": "Explicit six-month price.", "source_refs": ["synthetic-observations"]}
        for sid, account, currency in (("work", "work", "USD"), ("europe", "europe", "EUR")):
            entity = copy.deepcopy(base_entity)
            entity.update(id=sid, account_ref=account)
            entity["cost"]["currency"] = currency
            self.data["entities"].append(entity)
        report = self.build()["dashboard.json"]
        self.assertEqual(report["computed"]["monthly_baseline"], {"EUR": "0.17", "USD": "0.33"})
        self.assertEqual(len(report["subscriptions"]), 3)
        self.assertIn("personal", report["subscriptions"][0]["name"])
        self.assertIn("work", report["subscriptions"][1]["name"])

    def test_unknown_identity_is_preserved_in_arithmetic_facts(self):
        self.data["entities"][0]["account_ref"] = None
        artifacts = self.build()
        self.assertIsNone(artifacts["facts.json"]["invoices"][0]["account_ref"])
        self.assertEqual(artifacts["checks.json"]["documented_due"], [])

    def test_prepaid_unknown_and_historical_cannot_enter_baseline(self):
        for mutation in ("prepaid", "unknown", "historical"):
            with self.subTest(mutation=mutation):
                original = copy.deepcopy(self.data)
                if mutation == "historical":
                    self.data["entities"][0]["decision"]["status"] = mutation
                else:
                    self.data["entities"][0]["cost"]["kind"] = mutation
                with self.assertRaises(ValueError):
                    self.build()
                self.data = original

    def test_latest_lifecycle_source_must_be_considered_in_decision(self):
        source = copy.deepcopy(self.data["sources"][0])
        source["id"] = "cancel-source"
        self.data["sources"].append(source)
        self.event("subscription_cancelled", source_refs=["cancel-source"])
        with self.assertRaisesRegex(ValueError, "latest lifecycle"):
            self.build()

    def test_material_sources_cannot_be_marked_irrelevant(self):
        self.data["sources"][0]["disposition"] = "irrelevant"
        with self.assertRaisesRegex(ValueError, "material assertion"):
            self.build()

    def test_imports_preserve_unread_and_rebase_without_blanket_association(self):
        folder = self.base / "mime"
        folder.mkdir()
        (folder / "body.txt").write_text("Synthetic saved evidence.")
        source = {"id": "imported", "kind": "document", "file": "body.txt", "service_ids": [],
                  "disposition": "unread", "note": "Saved but not read."}
        (folder / "manifest.json").write_text(json.dumps({"messages": [{"evidence_sources": [source]}]}))
        self.data["imports"] = [{"file": "mime/manifest.json"}]
        result = next(s for s in self.build()["audit-evidence.json"]["sources"] if s["id"] == "imported")
        self.assertEqual(result["file"], "mime/body.txt")
        self.assertEqual(result["disposition"], "unread")
        self.assertEqual(result["service_ids"], [])
        self.data["source_updates"] = [{"id": "imported", "disposition": "reviewed", "note": "Actually inspected this synthetic evidence.", "service_ids": ["notes-personal"]}]
        result = next(s for s in self.build()["audit-evidence.json"]["sources"] if s["id"] == "imported")
        self.assertEqual(result["disposition"], "reviewed")

    def test_import_rejects_escape(self):
        self.data["imports"] = [{"file": "../outside.json"}]
        with self.assertRaisesRegex(ValueError, "parent traversal"):
            self.build()

    def test_supplied_source_links_and_ids_reach_timeline(self):
        self.data["sources"][0]["url"] = "https://mail.example.test/message/1"
        evidence = self.row()["evidence"]
        self.assertTrue(any(e.get("url") == "https://mail.example.test/message/1" for e in evidence))
        self.assertTrue(all(e.get("source_refs") for e in evidence))

    def test_refund_outcome_requires_explicit_status_not_inferred_from_notice(self):
        event = self.event("refund_received", amount="12.00", currency="USD")
        self.assertNotIn("outcomes.json", self.build())
        event.update(outcome_status="verified", pre_existing=True)
        outcome = self.build()["outcomes.json"]["events"][0]
        self.assertEqual(outcome["type"], "cash_refund")
        self.assertTrue(outcome["pre_existing"])
        self.assertNotIn("computed_recovery", self.build()["dashboard.json"])

    def test_zero_invoice_settlement_is_not_a_cash_charge(self):
        self.event("payment_succeeded", amount="0.00", currency="USD")
        with self.assertRaisesRegex(ValueError, "not a successful cash"):
            self.build()

    def test_rebuild_removes_only_recognized_obsolete_optional_output(self):
        self.event("refund_received", amount="12.00", currency="USD", outcome_status="verified", pre_existing=True)
        self.save()
        builder.run(self.base / "audit.json", self.base)
        self.assertTrue((self.base / "outcomes.json").exists())
        self.data["events"].pop()
        self.save()
        builder.run(self.base / "audit.json", self.base, force=True)
        self.assertFalse((self.base / "outcomes.json").exists())
        (self.base / "outcomes.json").write_text('{"manual":"preserve"}')
        with self.assertRaisesRegex(ValueError, "unrecognized optional"):
            builder.run(self.base / "audit.json", self.base, force=True)

    def test_full_build_is_provisional_then_stale_review_is_rejected(self):
        first = builder.run(self.base / "audit.json", self.base)
        self.assertEqual(first["status"], "provisional")
        evidence_path = self.base / "audit-evidence.json"
        report = json.loads((self.base / "dashboard.json").read_text())
        row = report["subscriptions"][0]
        review_row = {"service_id": row["id"], "service_sha256": builder.gate.service_digest(row),
                      "reviewed_source_ids": ["synthetic-observations"], "verdict": "pass", "note": "Synthetic gate fixture only."}
        if hasattr(builder.gate, "entity_evidence_digest"):
            review_row["entity_evidence_sha256"] = builder.gate.entity_evidence_digest(evidence_path, row["id"])
        review = {"reviewer": "Synthetic test reviewer", "evidence_sha256": builder.gate.evidence_digest(evidence_path),
                  "report_sha256": builder.gate.report_digest(report), "services": [review_row], "issues": []}
        (self.base / "independent-review.json").write_text(json.dumps(review))
        checked = builder.run(self.base / "audit.json", self.base, force=True)
        self.assertEqual(checked["status"], "checked", checked["issues"])
        self.data["entities"][0]["decision"]["status_note"] += " Revised conclusion."
        self.save()
        stale = builder.run(self.base / "audit.json", self.base, force=True)
        self.assertEqual(stale["status"], "provisional")
        self.assertTrue(any("stale" in item["code"] or "mismatch" in item["code"] for item in stale["issues"]))
        with self.assertRaises(ValueError):
            builder.renderer.render(json.loads((self.base / "dashboard.json").read_text()), evidence_path, require_checked=True)

    def test_overwrite_protection(self):
        builder.run(self.base / "audit.json", self.base)
        with self.assertRaisesRegex(ValueError, "Output exists"):
            builder.run(self.base / "audit.json", self.base)
        self.data["sources"][0]["file"] = "dashboard.json"
        self.save()
        with self.assertRaisesRegex(ValueError, "overwrite canonical input or imported evidence"):
            builder.run(self.base / "audit.json", self.base, force=True)

    def test_generated_outputs_cannot_overwrite_independent_review(self):
        self.data["independent_review_file"] = "dashboard.json"
        (self.base / "dashboard.json").write_text('{"reviewer":"Original independent review"}')
        self.save()
        with self.assertRaisesRegex(ValueError, "overwrite canonical input or imported evidence"):
            builder.run(self.base / "audit.json", self.base, force=True)
        self.assertIn("Original independent review", (self.base / "dashboard.json").read_text())


if __name__ == "__main__":
    unittest.main()
