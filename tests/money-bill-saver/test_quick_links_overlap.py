"""Behavioral checks for the focused report's account links and overlap leads."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[2] / "skills/money-bill-saver"
spec = importlib.util.spec_from_file_location("quick_report_under_test", SKILL / "scripts" / "build_quick_report.py")
quick = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quick)
preview_spec = importlib.util.spec_from_file_location("quick_preview_under_test", SKILL / "scripts" / "preview_quick.py")
preview = importlib.util.module_from_spec(preview_spec)
preview_spec.loader.exec_module(preview)


def fixture():
    return {
        "schema_version": "quick-1",
        "as_of": "2030-01-15",
        "scope": {"description": "Synthetic focused check; no mailbox accessed."},
        "services": [
            {"id": "assistant-a", "name": "Assistant A", "vendor": "assistant-a", "account_ref": None,
             "status": "user_reported", "status_note": "Named by the user; current payment is unknown.",
             "source_refs": [], "action": {"url": "https://accounts.example.com/account/billing",
                                           "link_label": "Likely account status page"},
             "overlap": [{"peer_ids": ["assistant-b"],
                          "reason": "Both tools may cover the same writing workflow.",
                          "tentative_keep_id": "assistant-a",
                          "next_check": "Compare weekly use, needed features and cancellation dependencies."}]},
            {"id": "assistant-b", "name": "Assistant B", "vendor": "assistant-b", "account_ref": None,
             "status": "uncertain", "status_note": "A possible plan was mentioned; current payment is unknown.",
             "source_refs": []},
        ],
        "cases": [],
    }


class QuickLinkAndOverlapTests(unittest.TestCase):
    def test_static_official_login_entry_is_allowed(self):
        data = fixture()
        data["services"][0]["action"]["url"] = "https://accounts.example.com/sign-in"
        self.assertEqual(quick.build(data, Path("."))["subscriptions"][0]["action"]["url"],
                         "https://accounts.example.com/sign-in")

    def test_no_issue_service_keeps_status_link_and_overlap_in_page(self):
        data = fixture()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "quick.json"
            source.write_text(json.dumps(data), encoding="utf-8")
            result = quick.run(source, root)
            self.assertEqual(preview.check(root)["status"], "passed")
            first = result["subscriptions"][0]
            self.assertFalse(first["needs_action"])
            self.assertEqual(first["action"]["url"], "https://accounts.example.com/account/billing")
            self.assertEqual(first["action"]["link_label"], "Likely account status page")
            self.assertIn("check the current account status", first["action"]["summary"])
            self.assertEqual(result["computed"]["refund_count"], 0)
            self.assertEqual(result["computed"]["review_signal_count"], 1)
            signal = first["review_signals"][0]
            self.assertEqual(signal["type"], "functional_overlap")
            self.assertEqual(signal["related_service_ids"], ["assistant-b"])
            self.assertIn("Tentatively keep Assistant A", signal["title"])
            self.assertIn("current paid status", signal["evidence_note"])
            html = (root / "dashboard.html").read_text(encoding="utf-8")
            self.assertIn("https://accounts.example.com/account/billing", html)
            self.assertIn("Tentatively keep Assistant A", html)

    def test_preview_fails_if_quick_link_or_overlap_is_dropped(self):
        for omitted, message in (("url", "Status entry missing"),
                                 ("overlap", "Possible-overlap prompt missing")):
            with self.subTest(omitted=omitted), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                source = root / "quick.json"
                source.write_text(json.dumps(fixture()), encoding="utf-8")
                quick.run(source, root)
                report = json.loads((root / "dashboard.json").read_text(encoding="utf-8"))
                first = report["subscriptions"][0]
                if omitted == "url":
                    first["action"].pop("url")
                else:
                    first["review_signals"].clear()
                html = quick.renderer.render(report)
                (root / "dashboard.json").write_text(json.dumps(report), encoding="utf-8")
                (root / "dashboard.html").write_text(html, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    preview.check(root)

    def test_unsafe_or_tokenized_action_urls_are_rejected(self):
        rejected = (
            "http://accounts.example.com/account",
            "https://user:pass@accounts.example.com/account",
            "https://accounts.example.com:443/account",
            "https://accounts.example.com/account?token=secret",
            "https://accounts.example.com/account#session",
            "https://accounts.example.com/account/8f3a9b4c",
            "https://127.0.0.1/account",
            "https://localhost/account",
        )
        for url in rejected:
            with self.subTest(url=url):
                data = fixture()
                data["services"][0]["action"]["url"] = url
                with self.assertRaises(ValueError):
                    quick.build(data, Path("."))

    def test_overlap_peers_and_keep_choice_must_be_listed_services(self):
        for bad_overlap in (
            {"peer_ids": ["missing"], "reason": "Same workflow", "next_check": "Compare use"},
            {"peer_ids": ["assistant-a"], "reason": "Same workflow", "next_check": "Compare use"},
            {"peer_ids": ["assistant-b"], "reason": "Same workflow", "next_check": "Compare use",
             "tentative_keep_id": "missing"},
        ):
            with self.subTest(overlap=bad_overlap):
                data = fixture()
                data["services"][0]["overlap"] = [bad_overlap]
                with self.assertRaises(ValueError):
                    quick.build(data, Path("."))

    def test_overlap_without_keep_choice_remains_tentative(self):
        data = fixture()
        del data["services"][0]["overlap"][0]["tentative_keep_id"]
        result = quick.build(data, Path("."))
        signal = result["subscriptions"][0]["review_signals"][0]
        self.assertIn("Consider keeping only one", signal["title"])
        self.assertEqual(signal["source_ids"], [])
        self.assertEqual(result["monthly_cost"]["items"], [])


if __name__ == "__main__":
    unittest.main()
