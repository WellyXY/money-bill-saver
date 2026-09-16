import copy
import importlib.util
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('dashboard', ROOT / 'skills/subscription-audit/scripts/render_dashboard.py')
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


def service(sid='sample', amount='9.90', currency='USD'):
    return {'id': sid, 'name': sid, 'status': 'observed', 'cost': {
        'kind': 'fixed_monthly', 'include_monthly': True, 'amount': amount, 'currency': currency,
    }, 'evidence': [{'label': 'Synthetic invoice'}]}


class DashboardTests(unittest.TestCase):
    def test_currency_totals_are_exact_and_separate(self):
        r = dashboard.prepare({'subscriptions': [service('a', '0.10'), service('b', '0.20'), service('c', '100', 'TWD')]})
        self.assertEqual(r['computed']['known_monthly'], {'USD': '0.30', 'TWD': '100.00'})

    def test_unknown_and_prepaid_cannot_enter_monthly_total(self):
        for status, kind in [('uncertain', 'fixed_monthly'), ('observed', 'prepaid'), ('historical', 'fixed_monthly')]:
            with self.subTest(status=status, kind=kind):
                s = service(); s['status'] = status; s['cost']['kind'] = kind
                with self.assertRaises(ValueError): dashboard.prepare({'subscriptions': [s]})

    def test_counted_price_needs_evidence(self):
        s = service(); s['evidence'] = []
        with self.assertRaises(ValueError): dashboard.prepare({'subscriptions': [s]})

    def test_invalid_money_is_rejected(self):
        for amount in ['NaN', 'Infinity', '-1', 'not-a-number', None]:
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                dashboard.prepare({'subscriptions': [service(amount=amount)]})

    def test_duplicate_ids_including_other_cases_are_rejected(self):
        for report in [{'subscriptions': [service(), service()]}, {'subscriptions': [service()], 'other_cases': [{'id': 'sample'}]}]:
            with self.assertRaises(ValueError): dashboard.prepare(report)

    def test_false_as_string_is_not_silently_counted(self):
        s = service(); s['cost']['include_monthly'] = 'false'
        with self.assertRaises(ValueError): dashboard.prepare({'subscriptions': [s]})

    def test_embedded_json_cannot_close_script(self):
        payload = '</script><script>alert("x")</script>&\u2028'
        report = {'title': payload, 'subscriptions': [service()]}
        rendered = dashboard.render(copy.deepcopy(report))
        self.assertNotIn(payload, rendered)
        embedded = re.search(r'<script id="report-data" type="application/json">(.*?)</script>', rendered, re.S).group(1)
        self.assertEqual(json.loads(embedded)['title'], payload)

    def test_document_needs_no_remote_assets(self):
        rendered = dashboard.render({'subscriptions': [service()]})
        self.assertNotRegex(rendered, r'<(?:script|img|link)\b[^>]+(?:src|href)=')
        self.assertNotIn('__REPORT_DATA__', rendered)

    def test_legacy_issues_never_become_refund_claims_automatically(self):
        s = service(); s['needs_action'] = True
        r = dashboard.prepare({'subscriptions': [s], 'other_cases': [{'id': 'reimbursement'}]})
        self.assertEqual(r['computed']['refund_count'], 0)
        self.assertEqual(r['computed']['other_issue_count'], 2)
        self.assertEqual(s['review_group'], 'other')

    def test_refund_review_does_not_change_spend_or_hide_service(self):
        s = service(); s.update(needs_action=True, review_group='refund', refund_review={
            'reason': 'Synthetic cancellation receipt predates this charged period.',
            'amount_label': 'USD 9.90 under review; no refund received',
            'eligibility': 'unverified', 'missing_evidence': ['Applicable terms'],
        })
        report = {'subscriptions': [s], 'other_cases': [{'id': 'claim', 'needs_action': True, 'review_group': 'other'}]}
        r = dashboard.prepare(report)
        self.assertEqual(r['computed']['refund_count'], 1)
        self.assertEqual(r['computed']['other_issue_count'], 1)
        self.assertEqual(r['computed']['service_count'], 1)
        self.assertEqual(r['computed']['known_monthly'], {'USD': '9.90'})

    def test_refund_requires_reason_evidence_and_valid_eligibility(self):
        valid = {'reason': 'Synthetic billing discrepancy', 'amount_label': 'Unknown', 'eligibility': 'unverified'}
        for field in ['reason', 'amount_label', 'eligibility', 'evidence']:
            with self.subTest(field=field):
                s = service(); s.update(needs_action=True, review_group='refund', refund_review=valid.copy())
                if field == 'evidence': s['evidence'] = []
                else: s['refund_review'].pop(field)
                with self.assertRaises(ValueError): dashboard.prepare({'subscriptions': [s]})

    def test_resolved_case_cannot_remain_in_open_refund_queue(self):
        s = service(); s.update(needs_action=False, review_group='refund')
        with self.assertRaises(ValueError): dashboard.prepare({'subscriptions': [s]})


if __name__ == '__main__':
    unittest.main()
