import copy
import importlib.util
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('dashboard', ROOT / 'skills/money-bill-saver/scripts/render_dashboard.py')
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


def service(sid='sample', amount='9.90', currency='USD'):
    return {'id': sid, 'name': sid, 'status': 'observed', 'cost': {
        'kind': 'fixed_monthly', 'include_monthly': True, 'amount': amount, 'currency': currency,
    }, 'evidence': [{'label': 'Synthetic invoice'}]}


class DashboardTests(unittest.TestCase):
    def test_final_render_rejects_missing_evidence_gate(self):
        with self.assertRaisesRegex(ValueError, 'coverage is provisional'):
            dashboard.render({'subscriptions': [service()]}, require_checked=True)

    def test_render_does_not_trust_embedded_checked_flag(self):
        report = {'subscriptions': [service()], 'computed': {'audit_quality': {'status': 'checked'}}}
        page = dashboard.render(report)
        embedded = json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>', page, re.S).group(1))
        self.assertEqual(embedded['computed']['audit_quality']['status'], 'provisional')

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
        asset_urls = re.findall(r'<(?:script|img|link)\b[^>]+(?:src|href)="([^"]*)"', rendered)
        self.assertTrue(all(url.startswith('data:') for url in asset_urls))
        self.assertNotIn('__REPORT_DATA__', rendered)
        self.assertNotIn('__FONT_DATA__', rendered)
        self.assertIn('data:font/ttf;base64,', rendered)

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

    def test_screening_leads_count_services_separately_and_do_not_create_refunds(self):
        a, b = service('a'), service('b')
        a['review_signals'] = [self.review_signal(), self.review_signal('functional_overlap', ['b'])]
        b.update(status='uncertain', needs_action=True, review_group='other')
        b['cost']['include_monthly'] = False
        b['review_signals'] = [self.review_signal('trial_conversion')]
        result = dashboard.prepare({'subscriptions': [a, b], 'computed': {'review_lead_count': 999}})['computed']
        self.assertEqual(result['review_lead_count'], 2)
        self.assertEqual(result['review_signal_count'], 3)
        self.assertEqual(result['refund_count'], 0)
        self.assertEqual(result['other_issue_count'], 1)
        self.assertEqual(result['known_monthly'], {'USD': '9.90'})
        self.assertEqual(result['monthly_baseline'], {})
        self.assertEqual(a['review_group'], 'none')
        self.assertEqual(b['status'], 'uncertain')
        self.assertNotIn('refund_review', b)

    def test_legacy_service_has_no_automatic_review_signals(self):
        s = service(); s['status_note'] = 'No service update emails in the supplied files.'
        result = dashboard.prepare({'subscriptions': [s]})['computed']
        self.assertEqual(s['review_signals'], [])
        self.assertEqual(result['review_lead_count'], 0)
        self.assertEqual(result['review_signal_count'], 0)

    def test_review_signals_cannot_bypass_refund_basis_checks(self):
        s = service(); s.update(needs_action=True, review_group='refund', review_signals=[self.review_signal()])
        with self.assertRaises(ValueError): dashboard.prepare({'subscriptions': [s]})

    def test_review_signal_shape_requires_rationale_and_next_check(self):
        invalid = [('type', 'refund_eligible'), ('type', []), ('title', ''), ('reason', '  '), ('evidence_note', None), ('next_check', ''), ('related_service_ids', None), ('source_ids', 'receipt'), ('source_ids', ['']), ('source_ids', ['x', 'x'])]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                signal = self.review_signal(); signal[field] = value
                s = service(); s['review_signals'] = [signal]
                with self.assertRaises(ValueError): dashboard.prepare({'subscriptions': [s]})
        for signals in [None, {}, [None], [{}]]:
            with self.subTest(signals=signals):
                s = service(); s['review_signals'] = signals
                with self.assertRaises(ValueError): dashboard.prepare({'subscriptions': [s]})
        for field in ['amount', 'eligibility']:
            with self.subTest(field=field):
                signal = self.review_signal(); signal[field] = 'unsupported claim'
                s = service(); s['review_signals'] = [signal]
                with self.assertRaises(ValueError): dashboard.prepare({'subscriptions': [s]})

    def test_overlap_requires_a_distinct_inventory_peer(self):
        for peers in [[], ['sample'], ['missing'], ['claim'], ['peer', 'peer']]:
            with self.subTest(peers=peers):
                s = service(); s['review_signals'] = [self.review_signal('functional_overlap', peers)]
                with self.assertRaises(ValueError):
                    dashboard.prepare({'subscriptions': [s, service('peer')], 'other_cases': [{'id': 'claim'}]})

    def test_screening_sources_are_preserved_locators_not_assumed_file_paths(self):
        s = service(); signal = self.review_signal()
        signal['source_ids'] = ['mail-message-1', 'https://example.invalid/source/2']
        s['review_signals'] = [signal]
        result = dashboard.prepare({'subscriptions': [s]})
        self.assertEqual(result['subscriptions'][0]['review_signals'][0]['source_ids'], signal['source_ids'])

    def test_missing_billing_dates_stay_unknown_even_with_renewal_text(self):
        s = service(); s['renewal'] = 'Term ends 2030-02-01'
        dashboard.prepare({'subscriptions': [s]})
        self.assertEqual(set(s['billing_dates']), {'last_invoice', 'last_charge', 'next_renewal'})
        self.assertTrue(all(e['date'] is None and e['status'] == 'unknown' for e in s['billing_dates'].values()))

    def test_invoice_charge_and_term_end_remain_distinct(self):
        s = service(); s['billing_dates'] = {
            'last_invoice': {'date': '2030-01-08', 'status': 'confirmed', 'note': 'Invoice issue date', 'sources': ['invoice-1']},
            'last_charge': {'date': '2030-01-12T16:30:00-08:00', 'status': 'confirmed', 'note': 'Successful receipt timestamp', 'sources': ['receipt-1']},
            'next_renewal': {'date': None, 'status': 'unknown', 'note': 'Only a period end is known', 'sources': ['invoice-1'], 'related_date': {'date': '2030-02-08', 'label': 'Period ends'}},
        }
        dashboard.prepare({'subscriptions': [s]})
        self.assertEqual(s['billing_dates']['last_invoice']['date'], '2030-01-08')
        self.assertEqual(s['billing_dates']['last_charge']['date'], '2030-01-12T16:30:00-08:00')
        self.assertIsNone(s['billing_dates']['next_renewal']['date'])

    def test_dated_events_need_sources_and_valid_precision(self):
        for value, sources in [('2030-02-30', ['x']), ('2030-01-01T12:00:00', ['x']), ('2030-01-01', [])]:
            with self.subTest(value=value, sources=sources):
                s = service(); s['billing_dates'] = {'last_charge': {'date': value, 'status': 'confirmed', 'note': 'Receipt', 'sources': sources}}
                with self.assertRaises(ValueError): dashboard.prepare({'subscriptions': [s]})

    def test_only_renewals_may_be_estimated_and_unknown_cannot_hide_a_date(self):
        for field, state, value in [('last_charge', 'estimated', '2030-01-01'), ('last_invoice', 'unknown', '2030-01-01'), ('next_renewal', 'not_scheduled', '2030-02-01')]:
            with self.subTest(field=field, state=state):
                s = service(); s['billing_dates'] = {field: {'date': value, 'status': state, 'note': 'Test record', 'sources': ['x']}}
                with self.assertRaises(ValueError): dashboard.prepare({'subscriptions': [s]})

    def test_monthly_baseline_normalizes_current_costs_separately_from_fixed_subtotal(self):
        subscriptions = [service('monthly', '20'), service('base', '5'), service('prepaid', '163.01')]
        subscriptions[1]['cost'].update(kind='monthly_base_plus_usage', include_monthly=False)
        subscriptions[2]['cost'].update(kind='prepaid', include_monthly=False)
        items = [self.monthly_item('monthly', '20'), self.monthly_item('base', '5'), self.monthly_item('prepaid', '163.01', months=6)]
        report = {'subscriptions': subscriptions, 'monthly_cost': self.monthly_summary(items, [{'service_id': 'base', 'note': 'Variable usage unknown'}]), 'computed': {'monthly_baseline': {'USD': '999'}}}
        result = dashboard.prepare(report)['computed']
        self.assertEqual(result['known_monthly'], {'USD': '20.00'})
        self.assertEqual(result['monthly_baseline'], {'USD': '52.17'})
        self.assertEqual(result['monthly_baseline_items'][-1], {**items[-1], 'monthly_amount': '27.17'})

    def test_monthly_baseline_sums_before_rounding_half_up_and_preserves_currencies(self):
        subscriptions = [service(sid, '0') for sid in ['a', 'b', 'c', 'd']]
        items = [self.monthly_item(sid, '0.01', months=6) for sid in ['a', 'b', 'c']]
        items.append(self.monthly_item('d', '120', currency='TWD', months=12))
        result = dashboard.prepare({'subscriptions': subscriptions, 'monthly_cost': self.monthly_summary(items)})['computed']
        self.assertEqual(result['monthly_baseline'], {'TWD': '10.00', 'USD': '0.01'})
        self.assertEqual([row['monthly_amount'] for row in result['monthly_baseline_items'][:3]], ['0.00'] * 3)

    def test_absent_monthly_summary_does_not_guess_from_fixed_subtotal(self):
        result = dashboard.prepare({'subscriptions': [service()]})['computed']
        self.assertEqual(result['monthly_baseline'], {})
        self.assertEqual(result['monthly_baseline_items'], [])

    def test_monthly_baseline_rejects_unsupported_or_duplicate_services(self):
        for state in ['uncertain', 'user_reported', 'historical']:
            with self.subTest(state=state):
                s = service(); s['status'] = state; s['cost']['include_monthly'] = False
                with self.assertRaises(ValueError):
                    dashboard.prepare({'subscriptions': [s], 'monthly_cost': self.monthly_summary([self.monthly_item()])})
        for items in [[self.monthly_item('missing')], [self.monthly_item(), self.monthly_item()]]:
            with self.subTest(items=items), self.assertRaises(ValueError):
                dashboard.prepare({'subscriptions': [service()], 'monthly_cost': self.monthly_summary(items)})

    def test_monthly_baseline_rejects_invalid_amounts_cycles_and_evidence(self):
        for field, value in [('amount', '-1'), ('amount', 'NaN'), ('amount', 'Infinity'), ('amount', 5), ('currency', 'usd'), ('months', 0), ('months', 1.5), ('months', True), ('sources', []), ('sources', ['']), ('basis', '')]:
            with self.subTest(field=field, value=value):
                item = self.monthly_item(); item[field] = value
                with self.assertRaises(ValueError):
                    dashboard.prepare({'subscriptions': [service()], 'monthly_cost': self.monthly_summary([item])})

    def test_monthly_summary_requires_dated_boundary_and_traceable_unknowns(self):
        invalid = [('as_of', '2030-02-30'), ('note', ''), ('unknowns', [{'service_id': 'missing', 'note': 'Price not established'}]), ('unknowns', [{'service_id': 'sample', 'note': ''}])]
        for field, value in invalid:
            with self.subTest(field=field):
                summary = self.monthly_summary([self.monthly_item()]); summary[field] = value
                with self.assertRaises(ValueError):
                    dashboard.prepare({'subscriptions': [service()], 'monthly_cost': summary})

    @staticmethod
    def review_signal(kind='usage_unverified', peers=None):
        return {'type': kind, 'title': 'Check whether this service is still needed', 'reason': 'The supplied receipt does not establish recent use.', 'evidence_note': 'Only selected synthetic billing records were reviewed; mailbox absence and non-use are not established.', 'next_check': 'Review account activity and dependencies for the paid period.', 'related_service_ids': peers or [], 'source_ids': []}

    @staticmethod
    def monthly_item(sid='sample', amount='9.90', currency='USD', months=1):
        return {'service_id': sid, 'amount': amount, 'currency': currency, 'months': months, 'basis': 'Synthetic account-specific price for the stated term', 'sources': ['synthetic-source']}

    @staticmethod
    def monthly_summary(items, unknowns=None):
        return {'as_of': '2030-01-01', 'items': items, 'unknowns': unknowns or [], 'note': 'Known current cost equivalents; actual cash payments and unknown costs remain separate.'}


if __name__ == '__main__':
    unittest.main()
