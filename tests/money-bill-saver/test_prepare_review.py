import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / 'skills/money-bill-saver/scripts/prepare_review.py'
spec = importlib.util.spec_from_file_location('prepare_review_test', SCRIPT)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class ReviewPacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.report = {'subscriptions': [
            {'id': 'alpha', 'name': 'Alpha', 'status': 'uncertain'},
            {'id': 'beta', 'name': 'Beta', 'status': 'uncertain'}],
            'monthly_cost': {'as_of': '2026-09-16', 'items': [], 'unknowns': [],
                             'note': 'Both current account costs are unknown.'},
            'coverage': {'summary': 'Synthetic mailbox fixture; no bank ledger.'}}
        self.manifest = {
            'scope': {'mode': 'mailbox', 'description': 'Synthetic discovery fixture.', 'as_of': '2026-09-16',
                      'workflow_version': 'audit-1', 'search_plan': {
                          'schema_version': '1', 'generic_invoice_receipt': {
                              'search_ids': ['generic'], 'coverage': 'all_categories',
                              'note': 'Generic invoice/receipt discovery; exact query requires semantic review.'}}},
            'searches': [{'id': 'generic', 'scope': 'discovery', 'service_ids': [], 'kind': 'billing',
                          'query': 'after:2026/08/16 (invoice OR receipt OR 帳單)', 'result_file': 'search.json'}],
            'sources': [], 'independent_review_file': 'independent-review.json'}
        for mid, entity in [('a', 'alpha'), ('b', 'beta')]:
            self.write(mid + '.json', {'id': mid, 'payload': {'mime_type': 'text/plain', 'body': {
                'content': f'Synthetic {entity} invoice delivered outside purchases. Amount due; not proof of payment.'}}})
            self.manifest['sources'].append({'id': 'gmail:' + mid, 'kind': 'message', 'service_ids': [entity],
                                             'file': mid + '.json', 'disposition': 'reviewed',
                                             'note': 'Author read full body; independent review not performed yet.'})
        self.manifest['sources'] += [
            {'id': 'gmail:news', 'kind': 'message', 'service_ids': [], 'disposition': 'irrelevant',
             'note': 'Editorial newsletter, no billing event.'},
            {'id': 'gmail:unknown', 'kind': 'message', 'service_ids': [], 'disposition': 'unread',
             'note': 'Potential merchant candidate; identity not yet established.'}]
        self.write('search.json', {'emails': [{'id': mid} for mid in ['a', 'b', 'news', 'unknown']],
                                    'next_page_token': None})
        self.write('audit-evidence.json', self.manifest)

    def write(self, name, data):
        (self.base / name).write_text(json.dumps(data), encoding='utf-8')

    def packets(self, previous=None):
        return review.prepare_packets(self.report, self.base / 'audit-evidence.json', previous)

    @staticmethod
    def previous(packets):
        return {'report_sha256': packets['global']['report_sha256'],
                'evidence_sha256': packets['global']['evidence_sha256'],
                'services': [{'service_id': p['service_id'], 'service_sha256': p['service_sha256'],
                              'entity_evidence_sha256': p['entity_evidence_sha256']}
                             for p in packets['entities']]}

    def test_packets_keep_material_sources_local_and_unknown_candidates_global(self):
        original_report = copy.deepcopy(self.report)
        original_manifest = (self.base / 'audit-evidence.json').read_bytes()
        packets = self.packets()
        self.assertEqual([[s['id'] for s in p['sources']] for p in packets['entities']], [['gmail:a'], ['gmail:b']])
        self.assertEqual([list(p['evidence_files']) for p in packets['entities']], [['a.json'], ['b.json']])
        self.assertEqual({s['id'] for s in packets['global']['triage']['unassigned_candidates']},
                         {'gmail:unknown'})
        self.assertEqual({s['id'] for s in packets['global']['triage']['irrelevant_sources']}, {'gmail:news'})
        self.assertEqual(packets['global']['triage']['unique_returned_messages'], 4)
        self.assertEqual(packets['global']['report_context']['monthly_cost'], self.report['monthly_cost'])
        self.assertEqual(self.report, original_report)
        self.assertEqual((self.base / 'audit-evidence.json').read_bytes(), original_manifest)
        self.assertEqual(packets['global']['gate']['status'], 'provisional')
        for packet in packets['entities']:
            self.assertEqual(packet['status'], 'unreviewed_packet')
            self.assertNotIn('verdict', packet)
        self.assertFalse((self.base / 'independent-review.json').exists())

    def test_source_change_marks_only_affected_entity_and_global_evidence(self):
        previous = self.previous(self.packets())
        self.write('a.json', {'id': 'a', 'payload': {'mime_type': 'text/plain', 'body': {
            'content': 'Changed Alpha material payment evidence.'}}})
        packets = self.packets(previous)
        a, b = [p['changes_since_previous_review'] for p in packets['entities']]
        self.assertFalse(a['row_changed'])
        self.assertTrue(a['material_evidence_changed'])
        self.assertFalse(b['row_changed'])
        self.assertFalse(b['material_evidence_changed'])
        self.assertTrue(packets['global']['changes_since_previous_review']['global_evidence_changed'])
        self.assertFalse(packets['global']['changes_since_previous_review']['report_changed'])

    def test_monthly_or_coverage_change_requires_global_review_without_repeating_rows(self):
        previous = self.previous(self.packets())
        self.report['coverage']['summary'] = 'Changed source coverage boundary.'
        packets = self.packets(previous)
        self.assertTrue(packets['global']['changes_since_previous_review']['report_changed'])
        self.assertTrue(all(not p['changes_since_previous_review']['row_changed'] for p in packets['entities']))
        self.assertTrue(all(not p['changes_since_previous_review']['material_evidence_changed'] for p in packets['entities']))

    def test_missing_candidate_is_reported_in_global_gate(self):
        self.manifest['sources'].pop()
        self.write('audit-evidence.json', self.manifest)
        codes = {item['code'] for item in self.packets()['global']['gate']['issues']}
        self.assertIn('untriaged_search_result', codes)

    def test_evidence_escape_is_rejected_before_writing_packets(self):
        self.manifest['sources'][0]['file'] = str(SCRIPT)
        self.write('audit-evidence.json', self.manifest)
        with self.assertRaises(ValueError):
            self.packets()

    def test_cli_writes_private_packets_without_approving_or_mutating_sources(self):
        self.write('report.json', self.report)
        output = self.base / 'review-packets'
        command = [sys.executable, str(SCRIPT), '--report', str(self.base / 'report.json'),
                   '--evidence', str(self.base / 'audit-evidence.json'), '--output-dir', str(output)]
        first = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
        summary = json.loads((output / 'global-review.json').read_text())
        self.assertEqual(len(summary['packet_files']), 2)
        self.assertEqual((output.stat().st_mode & 0o777), 0o700)
        self.assertTrue(all((p.stat().st_mode & 0o777) == 0o600 for p in output.iterdir()))
        self.assertFalse((self.base / 'independent-review.json').exists())

    def test_force_preflights_all_targets_before_touching_any_packet(self):
        output = self.base / 'review-packets'
        output.mkdir()
        original = b'Unrelated user-authored report; never overwrite this.'
        (output / 'global-review.json').write_bytes(original)
        with self.assertRaisesRegex(OSError, 'not a generated review packet'):
            review.write_packets(self.packets(), output, force=True)
        self.assertEqual((output / 'global-review.json').read_bytes(), original)
        self.assertEqual([p.name for p in output.iterdir()], ['global-review.json'])

    def test_force_preserves_original_evidence_even_when_it_looks_like_generated_output(self):
        output = self.base / 'review-packets'
        review.write_packets(self.packets(), output)
        original = {p.name: p.read_bytes() for p in output.iterdir()}
        self.manifest['sources'].append({
            'id': 'original-report', 'kind': 'document', 'service_ids': [],
            'file': 'review-packets/global-review.json', 'disposition': 'irrelevant',
            'note': 'Supplied older report retained as original input, excluded from current findings.'})
        self.write('audit-evidence.json', self.manifest)
        with self.assertRaisesRegex(OSError, 'input or original evidence'):
            review.write_packets(self.packets(), output, force=True)
        self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, original)

    def test_force_can_replace_generated_packets_but_not_explicit_input_aliases(self):
        output = self.base / 'review-packets'
        packets = self.packets()
        review.write_packets(packets, output)
        review.write_packets(packets, output, force=True)
        original = {p.name: p.read_bytes() for p in output.iterdir()}
        with self.assertRaisesRegex(OSError, 'input or original evidence'):
            review.write_packets(packets, output, force=True,
                                 protected_inputs=[output / 'global-review.json'])
        self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, original)

    def test_cli_force_cannot_replace_report_input_with_global_packet(self):
        report_path = self.base / 'global-review.json'
        self.write(report_path.name, self.report)
        before = {p.name: p.read_bytes() for p in self.base.iterdir() if p.is_file()}
        command = [sys.executable, str(SCRIPT), '--report', str(report_path),
                   '--evidence', str(self.base / 'audit-evidence.json'), '--output-dir', str(self.base), '--force']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('input or original evidence', result.stderr)
        self.assertEqual({p.name: p.read_bytes() for p in self.base.iterdir() if p.is_file()}, before)


if __name__ == '__main__':
    unittest.main()
