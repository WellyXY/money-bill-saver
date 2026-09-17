import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'skills/money-bill-saver/scripts'


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load('money_bill_saver_build_report', 'build_report.py')
renderer = load('money_bill_saver_build_renderer', 'render_dashboard.py')
audit_check = load('money_bill_saver_build_gate', 'check_audit.py')


def service(**overrides):
    row = {'id': 'acme', 'name': 'Acme Cloud', 'category': 'SaaS', 'plan': 'Pro',
           'status': 'observed', 'status_label': 'Paid term covers the audit date',
           'status_note': 'Latest invoice dated 2026-08-01; no later cancellation found.',
           'cost': {'label': 'US$12.00 per month', 'note': 'Account plan price from the invoice.',
                    'kind': 'fixed_monthly', 'amount': '12.00', 'currency': 'USD'},
           'evidence': [{'date': '2026-08-01', 'label': 'Acme invoice', 'note': 'Plan price and period.'}],
           'sources': ['invoice']}
    row.update(overrides)
    return row


def plan(**overrides):
    base = {
        'report': {'title': 'Billing review', 'intro': 'What to decide.', 'as_of': '2026-09-16',
                   'status_boundary': 'Status comes from reviewed sources, not live accounts.',
                   'cost_boundary': 'Fixed monthly prices only.',
                   'coverage': {'summary': 'One supplied invoice.', 'notes': ['No mailbox search.']},
                   'footer_note': 'Private review.'},
        'services': [service()],
    }
    base.update(overrides)
    return base


class BuildReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def build(self, data):
        report, manifest = builder.build(data)
        renderer.prepare(json.loads(json.dumps(report)))
        return report, manifest

    def test_contract_shape_is_expanded_from_a_compact_row(self):
        report, manifest = self.build(plan())
        self.assertIsNone(manifest)
        row = report['subscriptions'][0]
        self.assertEqual(row['initials'], 'AC')
        self.assertEqual(row['review_group'], 'none')
        self.assertFalse(row['needs_action'])
        self.assertEqual(row['review_signals'], [])
        self.assertEqual(set(row['billing_dates']), {'last_invoice', 'last_charge', 'next_renewal'})
        for event in row['billing_dates'].values():
            self.assertEqual((event['date'], event['status'], event['sources']), (None, 'unknown', []))
            self.assertTrue(event['note'].strip())
        self.assertNotIn('computed', report)

    def test_supplied_date_becomes_a_confirmed_event_without_inference(self):
        rows = [service(dates={
            'last_invoice': {'date': '2026-08-01', 'note': 'Invoice issue date.', 'sources': ['invoice']},
            'last_charge': {'note': 'No successful payment is evidenced.'},
            'next_renewal': {'date': '2026-09-01', 'status': 'estimated',
                             'note': 'Monthly cadence from two invoices.', 'sources': ['invoice']}})]
        row = self.build(plan(services=rows))[0]['subscriptions'][0]
        self.assertEqual(row['billing_dates']['last_invoice']['status'], 'confirmed')
        self.assertEqual(row['billing_dates']['last_charge']['status'], 'unknown')
        self.assertIsNone(row['billing_dates']['last_charge']['date'])
        self.assertEqual(row['billing_dates']['next_renewal']['status'], 'estimated')

    def test_monthly_baseline_is_derived_from_rows_once(self):
        monthly = {'amount': '12.00', 'currency': 'USD', 'months': 1,
                   'basis': 'Account plan price from the August invoice.', 'sources': ['invoice']}
        annual = service(id='beta', name='Beta Docs', monthly={
            'amount': '120.00', 'currency': 'USD', 'months': 12,
            'basis': 'Prepaid annual term still covering the audit date.', 'sources': ['invoice']},
            cost={'label': 'US$120.00 per year', 'note': 'Prepaid annual term.', 'kind': 'prepaid',
                  'amount': '120.00', 'currency': 'USD'},
            cost_unknown='Usage add-ons for the current month are unknown.')
        report = self.build(plan(services=[service(monthly=monthly), annual],
                                 monthly_cost={'note': 'Known current cost equivalents only.'}))[0]
        self.assertEqual([i['service_id'] for i in report['monthly_cost']['items']], ['acme', 'beta'])
        self.assertEqual(report['monthly_cost']['unknowns'],
                         [{'service_id': 'beta', 'note': 'Usage add-ons for the current month are unknown.'}])
        # Fixed subtotal and normalized baseline stay different subsets.
        self.assertTrue(report['subscriptions'][0]['cost']['include_monthly'])
        self.assertFalse(report['subscriptions'][1]['cost']['include_monthly'])
        computed = renderer.prepare(json.loads(json.dumps(report)))['computed']
        self.assertEqual(computed['known_monthly'], {'USD': '12.00'})
        self.assertEqual(computed['monthly_baseline'], {'USD': '22.00'})

    def test_supplied_baseline_items_are_refused(self):
        with self.assertRaises(builder.BuildError):
            builder.build(plan(monthly_cost={'note': 'x', 'items': []}))

    def test_uncounted_rows_never_opt_into_the_fixed_subtotal(self):
        rows = [service(status='uncertain'), service(id='gamma', name='Gamma', evidence=[])]
        report = self.build(plan(services=rows, monthly_cost=None))[0]
        self.assertFalse(any(r['cost']['include_monthly'] for r in report['subscriptions']))

    def test_refund_shorthand_sets_group_action_and_defaults(self):
        row = service(refund={'reason': 'Charged after the cancellation date.',
                              'amount_label': 'USD 12.00 under review',
                              'eligibility': 'unverified'})
        built = self.build(plan(services=[row]))[0]['subscriptions'][0]
        self.assertEqual(built['review_group'], 'refund')
        self.assertTrue(built['needs_action'])
        self.assertEqual(built['refund_review']['missing_evidence'], [])

    def test_contradictory_action_and_group_are_refused(self):
        with self.assertRaises(builder.BuildError):
            builder.build(plan(services=[service(review_group='other', needs_action=False)]))

    def test_mistyped_field_names_fail_loudly(self):
        with self.assertRaises(builder.BuildError):
            builder.build(plan(services=[service(billing_dates={})]))
        with self.assertRaises(builder.BuildError):
            builder.build(plan(services=[service(signals=[{'type': 'usage_unverified', 'title': 't',
                                                           'reason': 'r', 'evidence_note': 'n',
                                                           'next_step': 'wrong key'}])]))

    def test_evidence_service_ids_are_inverted_from_row_references(self):
        evidence = {'scope': {'mode': 'files', 'description': 'One supplied Acme invoice PDF.',
                              'as_of': '2026-09-16'},
                    'searches': [],
                    'sources': [{'id': 'invoice', 'kind': 'document', 'file': 'invoice.txt',
                                 'disposition': 'reviewed',
                                 'note': 'Read plan price, period and payment status.'}]}
        case = {'id': 'refund-case', 'name': 'Acme refund', 'status': 'observed',
                'status_label': 'Open', 'status_note': 'Awaiting reply.',
                'evidence': [{'date': '2026-08-02', 'label': 'Support reply', 'note': 'Ticket opened.'}],
                'refund': {'reason': 'Duplicate charge on the same period.',
                           'amount_label': 'USD 12.00 under review', 'eligibility': 'unverified'},
                'sources': ['invoice']}
        report, manifest = self.build(plan(evidence=evidence, cases=[case]))
        self.assertEqual(manifest['sources'][0]['service_ids'], ['acme', 'refund-case'])
        self.assertEqual(manifest['scope']['mode'], 'files')

        (self.base / 'invoice.txt').write_text('Synthetic invoice USD 12.00', encoding='utf-8')
        (self.base / 'audit-evidence.json').write_text(json.dumps(manifest), encoding='utf-8')
        result = audit_check.assess(renderer.prepare(report), self.base / 'audit-evidence.json')
        # The built pair passes evidence coverage with no independent review requested.
        self.assertEqual(result['status'], 'checked', result['issues'])
        self.assertEqual(result['independent_review'], 'not_requested')

    def test_dangling_and_orphan_evidence_references_are_refused(self):
        evidence = {'scope': {'mode': 'files', 'description': 'Supplied invoice.', 'as_of': '2026-09-16'},
                    'searches': [],
                    'sources': [{'id': 'invoice', 'kind': 'document', 'file': 'invoice.txt',
                                 'disposition': 'reviewed', 'note': 'Read the invoice.'}]}
        row = service(dates={'last_invoice': {'date': '2026-08-01', 'note': 'Issue date.',
                                              'sources': ['not-declared']}})
        with self.assertRaises(builder.BuildError):
            builder.build(plan(evidence=evidence, services=[row]))
        with self.assertRaises(builder.BuildError):
            builder.build(plan(evidence=evidence, services=[service(sources=['missing'])]))
        spare = {**evidence, 'sources': evidence['sources'] + [
            {'id': 'spare', 'kind': 'document', 'file': 'spare.txt', 'disposition': 'irrelevant',
             'note': 'Unrelated newsletter.'}]}
        with self.assertRaises(builder.BuildError):
            builder.build(plan(evidence=spare))
        # An external locator is a reference, not a manifest entry.
        external = service(signals=[{'type': 'usage_unverified', 'title': 'Check recent use',
                                     'reason': 'No activity in the reviewed records.',
                                     'evidence_note': 'Records cover 2026-01 to 2026-09.',
                                     'next_check': 'Open the account usage page.',
                                     'source_ids': ['https://acme.example/usage']}])
        self.assertIsNotNone(builder.build(plan(evidence=evidence, services=[external]))[1])

    def test_cli_writes_private_files_and_prints_counts_only(self):
        source = self.base / 'plan.json'
        source.write_text(json.dumps(plan(services=[service(monthly={
            'amount': '12.00', 'currency': 'USD', 'months': 1,
            'basis': 'Account plan price.', 'sources': ['invoice']})],
            monthly_cost={'note': 'Known equivalents only.'})), encoding='utf-8')
        out = self.base / 'work'
        command = [sys.executable, str(SCRIPTS / 'build_report.py'), '--input', str(source),
                   '--output-dir', str(out)]
        proc = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        summary = json.loads(proc.stdout)
        self.assertEqual(summary['services'], 1)
        self.assertEqual(summary['monthly_items'], 1)
        self.assertEqual(summary['files'], ['dashboard.json'])
        self.assertNotIn('12.00', proc.stdout)
        self.assertEqual(oct((out / 'dashboard.json').stat().st_mode & 0o777), '0o600')
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
        self.assertEqual(subprocess.run(command + ['--force'], capture_output=True).returncode, 0)

    def test_bundled_example_plan_builds_and_renders(self):
        example = ROOT / 'skills/money-bill-saver/assets/example-report-plan.json'
        report, manifest = builder.build(json.loads(example.read_text(encoding='utf-8')))
        self.assertIsNone(manifest)
        prepared = renderer.prepare(json.loads(json.dumps(report)))
        self.assertEqual(prepared['computed']['known_monthly'], {'USD': '12.00'})
        self.assertEqual(prepared['computed']['monthly_baseline'], {'USD': '22.00'})
        self.assertEqual(prepared['computed']['refund_count'], 1)
        self.assertEqual(prepared['computed']['review_lead_count'], 1)
        page = renderer.render(json.loads(json.dumps(report)))
        self.assertIn('Sample Monthly Tool', page)

    def test_invalid_plan_reports_the_contract_failure(self):
        with self.assertRaises(builder.BuildError):
            builder.build(plan(services=[service(status='active')]))
        with self.assertRaises(builder.BuildError):
            builder.build(plan(services=[service(), service()]))


if __name__ == '__main__':
    unittest.main()
