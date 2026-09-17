import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/money-bill-saver/scripts/index_mail_candidates.py"
spec = importlib.util.spec_from_file_location("money_bill_saver_index_mail_candidates", SCRIPT)
indexer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(indexer)


class CandidateIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def save(self, name, obj):
        path = self.base / name
        path.write_text(json.dumps(obj), encoding="utf-8")
        return path

    def test_deduplicates_across_queries_and_groups_sender_and_domain(self):
        first = self.save("first.json", {"structuredContent": {"emails": [
            {"id": "msg-a", "from": "Billing <billing@vendor.test>",
             "subject": "Invoice Alpha", "date": "2026-08-01T10:00:00Z", "has_attachments": True},
            {"id": "msg-b", "from": "Support <support@vendor.test>",
             "subject": "Receipt Beta", "date": "2026-09-01T10:00:00Z", "attachments": []}]}})
        second = self.save("second.json", {"query": "from:vendor.test", "pages": [
            {"page": 1, "response": {"emails": [
                {"id": "msg-a", "subject": "Invoice Alpha"},
                {"id": "msg-c", "from": "Billing <billing@vendor.test>",
                 "subject": "Invoice Gamma", "date": "2026-09-10T10:00:00Z",
                 "attachments": [{"filename": "invoice.pdf"}]}]}}]})
        result = indexer.build_index([first, second])
        self.assertEqual(result["message_count"], 3)
        by_id = {message["id"]: message for message in result["messages"]}
        self.assertEqual(len(by_id["msg-a"]["seen_in"]), 2)
        self.assertEqual(by_id["msg-a"]["seen_in"][1]["query"], "from:vendor.test")
        self.assertEqual(by_id["msg-a"]["has_attachments"], True)
        self.assertEqual(by_id["msg-b"]["has_attachments"], False)
        self.assertEqual(result["domains"][0]["sender_domain"], "vendor.test")
        self.assertEqual(result["domains"][0]["message_count"], 3)
        self.assertEqual(result["domains"][0]["newest_date"], "2026-09-10T10:00:00Z")
        self.assertEqual(next(g for g in result["senders"] if g["sender_email"] == "billing@vendor.test")["message_count"], 2)

    def test_id_only_pages_are_flagged_as_missing_metadata(self):
        saved = self.save("ids.json", {"query": "subject:receipt", "pages": [
            {"response": {"message_ids": ["msg-a", "msg-b"], "next_page_token": None}},
            {"response": {"ids": ["msg-a"]}}]})
        result = indexer.build_index([saved])
        self.assertEqual(result["message_count"], 2)
        self.assertEqual(result["id_only_count"], 2)
        self.assertEqual(result["needs_metadata_fetch_count"], 2)
        self.assertEqual(result["unknown_sender_count"], 2)
        self.assertEqual(result["senders"], [])
        self.assertEqual(result["domains"], [])
        for message in result["messages"]:
            self.assertTrue(message["id_only"])
            self.assertTrue(message["needs_metadata_fetch"])
            self.assertIsNone(message["has_attachments"])
            self.assertEqual(message["missing_metadata"], ["sender_email", "subject", "date", "has_attachments"])
        self.assertEqual(len(next(m for m in result["messages"] if m["id"] == "msg-a")["seen_in"]), 2)

    def test_real_gmail_email_fields_keep_available_metadata_and_subject_pattern(self):
        saved = self.save("gmail.json", {"structuredContent": {"emails": [
            {"id": "msg-1", "thread_id": "thread-1", "from_": "Bills <pay@vendor.test>",
             "subject": "Invoice 2026-08-01 #12345", "snippet": "Your bill is ready",
             "email_ts": 1785592800, "has_attachment": False, "attachments": []},
            {"id": "msg-2", "thread_id": "thread-2", "from_": "Bills <pay@vendor.test>",
             "subject": "Re: Invoice 2026-09-01 #67890", "snippet": "See invoice",
             "email_ts": 1788271200, "has_attachment": True,
             "attachments": [{"filename": "bill.pdf"}]}]}})
        result = indexer.build_index([saved])
        self.assertEqual(result["needs_metadata_fetch_count"], 0)
        self.assertEqual(result["id_only_count"], 0)
        by_id = {message["id"]: message for message in result["messages"]}
        self.assertEqual(by_id["msg-1"]["sender_email"], "pay@vendor.test")
        self.assertEqual(by_id["msg-1"]["snippet"], "Your bill is ready")
        self.assertFalse(by_id["msg-1"]["has_attachments"])
        self.assertTrue(by_id["msg-2"]["has_attachments"])
        self.assertEqual(len(result["subject_patterns"]), 1)
        self.assertEqual(result["subject_patterns"][0]["message_count"], 2)
        self.assertEqual(result["subject_patterns"][0]["subject_pattern"], "invoice <date> #<number>")
        self.assertTrue(result["navigation_only"])

    def test_empty_and_malformed_records_are_counted_without_false_candidates(self):
        saved = self.save("partial.json", {"query": "x", "pages": [
            {"response": {"emails": [{"id": "valid"}, {"subject": "no ID"}, 42]}},
            {"response": {"emails": "wrong type"}},
            {"response": {"emails": []}}]})
        result = indexer.build_index([saved])
        self.assertEqual((result["message_count"], result["invalid_pages"], result["invalid_records"]), (1, 1, 2))
        self.assertEqual(indexer.build_index([self.save("empty.json", {"emails": []})])["message_count"], 0)

    def test_cli_writes_private_file_and_stdout_contains_counts_only(self):
        secret_id = "private-message-71"
        secret_subject = "Private invoice amount"
        saved = self.save("search.json", {"query": "subject:invoice", "emails": [{"id": secret_id, "subject": secret_subject}],
                                          "next_page_token": None})
        output = self.base / "private" / "candidate-index.json"
        run = subprocess.run([sys.executable, str(SCRIPT), "--input", str(saved),
                              "--output", str(output)], capture_output=True, text=True, check=True)
        self.assertIn("1 unique messages", run.stdout)
        self.assertNotIn(secret_id, run.stdout)
        self.assertNotIn(secret_subject, run.stdout)
        self.assertEqual(run.stderr, "")
        self.assertEqual(os.stat(output).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(output.parent).st_mode & 0o777, 0o700)
        self.assertEqual(json.loads(output.read_text())["messages"][0]["subject"], secret_subject)

    def test_complete_page_chain_and_raw_search_status(self):
        bundle = self.save("complete.json", {"query": "category:purchases", "completed": True,
            "pages": [
                {"page": 1, "request_next_page_token": None,
                 "response": {"message_ids": ["a"], "next_page_token": "token-1"}},
                {"page": 2, "request_next_page_token": "token-1",
                 "response": {"message_ids": ["b"], "next_page_token": None}}]})
        complete = indexer.build_index([bundle])
        self.assertTrue(complete["saved_query_pages_complete"])
        self.assertEqual((complete["complete_queries"], complete["incomplete_queries"],
                          complete["coverage_unknown"]), (1, 0, 0))
        self.assertEqual(complete["query_runs"][0]["status"], "complete")
        self.assertEqual(complete["message_count"], 2)

        unknown = indexer.build_index([self.save("unknown.json", {"emails": [{"id": "x"}]})])
        self.assertEqual(unknown["coverage_unknown"], 1)
        self.assertFalse(unknown["saved_query_pages_complete"])
        standalone = indexer.build_index([self.save("standalone.json", {"query": "subject:receipt",
            "structuredContent": {"emails": [{"id": "x"}], "next_page_token": None}})])
        self.assertTrue(standalone["saved_query_pages_complete"])
        missing_query = indexer.build_index([self.save("missing-query.json", {
            "emails": [{"id": "x"}], "next_page_token": None})])
        self.assertEqual(missing_query["coverage_unknown"], 1)
        self.assertFalse(missing_query["saved_query_pages_complete"])
        self.assertEqual(missing_query["query_runs"][0]["reasons"], ["missing_query"])

    def test_truncated_broken_or_error_page_chains_are_incomplete(self):
        broken = [
            ({"query": "q", "pages": [{"page": 1, "request_next_page_token": None,
              "response": {"emails": [{"id": "x"}], "next_page_token": "more"}}]}, "missing_continuation"),
            ({"query": "q", "pages": [{"page": 1, "request_next_page_token": None,
              "response": {"emails": [], "next_page_token": "one"}},
              {"page": 2, "request_next_page_token": "wrong",
               "response": {"emails": [], "next_page_token": None}}]}, "token_mismatch"),
            ({"query": "q", "pages": [{"page": 1, "request_next_page_token": "later",
              "response": {"emails": [], "next_page_token": None}}]}, "missing_first_page"),
            ({"query": "q", "pages": [{"page": 1, "query": "another query",
              "response": {"emails": [], "next_page_token": None}}]}, "query_mismatch"),
            ({"query": "q", "pages": [{"page": 1, "request_next_page_token": None,
              "response": {"emails": [], "next_page_token": "loop"}},
              {"page": 2, "request_next_page_token": "loop",
               "response": {"emails": [], "next_page_token": "loop"}}]}, "token_cycle"),
            ({"query": "q", "pages": [{"page": 1, "response": {
              "isError": True, "emails": [], "next_page_token": None}}]}, "tool_error"),
            ({"query": "q", "completed": False, "pages": [{"page": 1,
              "response": {"emails": [], "next_page_token": None}}]}, "completed_flag_false"),
            ({"query": "q", "pages": [{"page": 1,
              "response": {"next_page_token": None}}]}, "invalid_page"),
            ({"query": "q", "pages": [{"page": 1,
              "response": {"emails": [{"subject": "missing ID"}],
                           "next_page_token": None}}]}, "invalid_record"),
        ]
        for index, (data, expected_reason) in enumerate(broken):
            with self.subTest(reason=expected_reason):
                result = indexer.build_index([self.save(f"broken-{index}.json", data)])
                self.assertFalse(result["saved_query_pages_complete"])
                self.assertEqual(result["incomplete_queries"], 1)
                self.assertIn(expected_reason, result["query_runs"][0]["reasons"])

    def test_cli_writes_compact_private_summary_but_exits_nonzero_for_truncation(self):
        secret_id = "private-message-71"
        secret_subject = "Private invoice amount"
        saved = self.save("truncated.json", {"query": "secret-query", "structuredContent": {
            "emails": [{"id": secret_id, "from_": "Bills <pay@vendor.test>",
                        "subject": secret_subject, "email_ts": 1785592800,
                        "has_attachment": False}], "next_page_token": "more"}})
        output = self.base / "private" / "nested" / "candidate-index.json"
        summary = self.base / "private" / "nested" / "candidate-summary.json"
        run = subprocess.run([sys.executable, str(SCRIPT), "--input", str(saved),
                              "--output", str(output), "--summary-output", str(summary)],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertIn("1 incomplete", run.stdout)
        self.assertNotIn(secret_id, run.stdout)
        self.assertNotIn(secret_subject, run.stdout)
        self.assertEqual(os.stat(output).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(summary).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(output.parent).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(output.parent.parent).st_mode & 0o777, 0o700)
        index = json.loads(output.read_text())
        compact = json.loads(summary.read_text())
        self.assertEqual(index["query_runs"][0]["status"], "incomplete")
        self.assertEqual(compact["incomplete_queries"], 1)
        self.assertNotIn("messages", compact)
        self.assertEqual(compact["query_runs"], [{"query": "secret-query", "page_count": 1,
                                                  "status": "incomplete", "reasons": ["missing_continuation"]}])
        self.assertNotIn(secret_id, summary.read_text())
        self.assertEqual(compact["senders"][0]["subject_example_preview"], secret_subject)
        self.assertEqual(compact["domains"][0]["sender_domain"], "vendor.test")

    def test_summary_is_bounded_and_marks_groups_to_review_in_full_index(self):
        emails = [{"id": f"msg-{number}", "from_": f"billing@merchant-{number}.test",
                   "subject": f"Invoice for merchant {number}", "email_ts": 1785592800}
                  for number in range(120)]
        saved = self.save("many-groups.json", {"query": "subject:invoice",
                                               "emails": emails, "next_page_token": None})
        index = indexer.build_index([saved])
        summary = indexer.build_summary(index)
        self.assertEqual(index["message_count"], 120)
        self.assertEqual((len(summary["senders"]), len(summary["domains"]),
                          len(summary["subject_patterns"])), (40, 100, 30))
        self.assertEqual(summary["omitted_groups"],
                         {"senders": 80, "domains": 20, "subject_patterns": 90})
        self.assertNotIn("messages", summary)
        self.assertNotIn("msg-0", json.dumps(summary))

    def test_separate_index_required_for_multiple_mailboxes(self):
        first = self.save("first-mailbox.json", {"mailbox": "first@example.test", "query": "q",
            "emails": [{"id": "same-id"}], "next_page_token": None})
        second = self.save("second-mailbox.json", {"mailbox": "second@example.test", "query": "q",
            "emails": [{"id": "same-id"}], "next_page_token": None})
        with self.assertRaisesRegex(indexer.CandidateIndexError, "separate index"):
            indexer.build_index([first, second])


if __name__ == "__main__":
    unittest.main()
