import base64
import copy
from email.message import EmailMessage
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'skills/money-bill-saver/scripts/check_audit.py'
spec = importlib.util.spec_from_file_location('audit_check', SCRIPT)
audit_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_check)
mime_spec = importlib.util.spec_from_file_location('audit_test_mime', SCRIPT.with_name('extract_mime.py'))
mime_extract = importlib.util.module_from_spec(mime_spec)
mime_spec.loader.exec_module(mime_extract)


class AuditCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.service = {'id': 'acme', 'name': 'Acme', 'status': 'uncertain',
                        'billing_dates': {'last_charge': {'date': None, 'status': 'unknown',
                                                         'note': 'Payment not established.', 'sources': []}}}
        self.report = {'subscriptions': [self.service]}
        self.manifest = {'scope': {'mode': 'files', 'description': 'Only the supplied invoice PDF.', 'as_of': '2026-09-16'},
                         'searches': [],
                         'sources': [{'id': 'invoice', 'service_ids': ['acme'], 'kind': 'document',
                                      'file': 'invoice.txt', 'disposition': 'reviewed',
                                      'note': 'Amount due is not proof of a successful payment.'}],
                         'independent_review_file': 'review.json'}
        (self.base / 'invoice.txt').write_text('Synthetic invoice: amount due USD9.00', encoding='utf-8')
        self.review = {'reviewer': 'Independent reviewer B', 'services': [
            {'service_id': 'acme', 'service_sha256': audit_check.service_digest(self.service),
             'reviewed_source_ids': ['invoice'], 'verdict': 'pass',
             'note': 'Checked invoice and payment distinction; last charge remains unestablished.'}], 'issues': []}

    def write(self, path, data):
        (self.base / path).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

    def assess(self):
        self.write('audit-evidence.json', self.manifest)
        self.review.setdefault('report_sha256', audit_check.report_digest(self.report))
        try:
            self.review.setdefault('evidence_sha256', audit_check.evidence_digest(self.base / 'audit-evidence.json'))
        except (OSError, ValueError, TypeError, KeyError):
            pass
        self.write('review.json', self.review)
        return audit_check.assess(self.report, self.base / 'audit-evidence.json')

    def codes(self, result):
        return {i['code'] for i in result['issues']}

    def mailbox(self, entries=None, next_token=None):
        self.manifest['scope'] = {'mode': 'mailbox', 'description': 'All available Acme merchant mail including lifecycle notices.', 'as_of': '2026-09-16'}
        self.manifest['searches'] = [{'id': 'discovery', 'service_ids': ['acme'], 'kind': 'merchant_discovery',
                                      'query': 'in:anywhere (from:acme.example OR Acme)', 'result_file': 'page1.json'}]
        self.write('page1.json', {'structuredContent': {'emails': entries or [], 'next_page_token': next_token}})

    def message(self, message_id='abc', payload=None, disposition='reviewed'):
        sid = 'gmail:' + message_id
        payload = payload or {'mime_type': 'text/plain', 'body': {'content': 'Synthetic receipt: paid USD9.00 on September 1.'}}
        self.write(message_id + '.json', {'structuredContent': {'id': message_id, 'payload': payload}})
        self.manifest['sources'].append({'id': sid, 'service_ids': ['acme'], 'kind': 'message',
                                         'file': message_id + '.json', 'disposition': disposition,
                                         'note': 'Read full receipt MIME; date paid checked independently.'})
        if disposition == 'reviewed':
            self.review['services'][0]['reviewed_source_ids'].append(sid)
        return sid

    def converted_message(self, reviewed=True, raw=None, source_format='gmail_raw_json', extract_pdf=False):
        if raw is None:
            email = EmailMessage()
            email['From'] = 'billing@acme.example'
            email['Subject'] = 'Synthetic billing evidence'
            email.set_content('Synthetic receipt body: USD9.00 due.')
            email.add_attachment(b'Invoice image bytes', maintype='image', subtype='png',
                                 filename='invoice.png', disposition='inline', cid='invoice-image')
            email.add_attachment('amount,currency\n9,USD\n', subtype='csv', filename='invoice.csv')
            raw = email.as_bytes()
        source = self.base / ('raw.json' if source_format == 'gmail_raw_json' else 'original.eml')
        if source_format == 'gmail_raw_json':
            self.write(source.name, {'structuredContent': {'id': 'converted', 'raw': base64.urlsafe_b64encode(raw).decode()}})
        else:
            source.write_bytes(raw)
        output = self.base / 'mime'
        result = mime_extract.convert_files([source], output, extract_pdf=extract_pdf)
        row = result['messages'][0]
        for entry in row['evidence_sources']:
            entry = copy.deepcopy(entry)
            entry['service_ids'] = ['acme']
            if entry.get('file'):
                entry['file'] = 'mime/' + entry['file']
            if reviewed:
                entry.update(disposition='reviewed', note='Read the saved original, body and associated attachment evidence.')
                self.review['services'][0]['reviewed_source_ids'].append(entry['id'])
            self.manifest['sources'].append(entry)
        self.message_path = output / row['message_file']
        self.converted_record = json.loads(self.message_path.read_text(encoding='utf-8'))
        return row

    def save_converted_record(self):
        self.message_path.write_text(json.dumps(self.converted_record), encoding='utf-8')

    def extracted_file(self, role):
        entry = next(item for item in self.converted_record['extraction']['files'] if item['role'] == role)
        return self.message_path.parent / entry['file']

    def test_clean_files_review_is_checked_and_preserves_unknown_payment(self):
        original = copy.deepcopy(self.report)
        result = self.assess()
        self.assertEqual(result['status'], 'checked')
        self.assertEqual(result['scope']['mode'], 'files')
        self.assertEqual(self.report, original)
        self.assertIsNone(self.service['billing_dates']['last_charge']['date'])

    def test_missing_manifest_is_provisional(self):
        result = audit_check.assess(self.report)
        self.assertEqual(result['status'], 'provisional')
        self.assertIn('missing_evidence_manifest', self.codes(result))

    def test_chinese_invoice_returned_by_search_cannot_be_silently_dropped(self):
        self.mailbox([{'id': 'zh-invoice', 'subject': '您的 Google Workspace 帳單已開立'}])
        result = self.assess()
        self.assertEqual(result['status'], 'provisional')
        self.assertIn('untriaged_search_result', self.codes(result))

    def test_missing_cancellation_detected_by_independent_review_blocks(self):
        self.review['issues'] = [{'service_id': 'acme', 'message': 'Later cancellation email was ignored; the active status is unsupported.'}]
        result = self.assess()
        self.assertIn('independent_blocking_issue', self.codes(result))
        self.assertEqual(result['status'], 'provisional')

    def test_independent_paid_invoice_vs_successful_charge_concern_blocks(self):
        self.review['services'][0].update(verdict='needs_review', note='Invoice says paid from account credit; a new card charge has not been established.')
        self.assertIn('independent_needs_review', self.codes(self.assess()))

    def test_pdf_attachment_cannot_hide_behind_reviewed_message(self):
        self.mailbox([{'id': 'abc'}])
        self.message(payload={'mime_type': 'multipart/mixed', 'parts': [
            {'mime_type': 'application/pdf', 'filename': 'invoice.pdf', 'part_id': '1',
             'body': {'attachment_id': 'attach-123'}}]})
        self.assertIn('untriaged_attachment', self.codes(self.assess()))

    def test_unread_attachment_blocks_even_when_declared(self):
        self.message()
        self.manifest['sources'].append({'id': 'pdf', 'parent_id': 'gmail:abc', 'attachment_id': 'attach-123',
                                         'service_ids': ['acme'], 'kind': 'attachment', 'disposition': 'unread',
                                         'note': 'PDF has not been downloaded yet.'})
        self.assertIn('unreviewed_source', self.codes(self.assess()))

    def test_read_attachment_and_independent_review_pass(self):
        self.mailbox([{'id': 'abc'}])
        self.message(payload={'mime_type': 'multipart/mixed', 'parts': [
            {'mime_type': 'application/pdf', 'filename': 'invoice.pdf', 'part_id': '1',
             'body': {'attachment_id': 'attach-123'}}]})
        self.manifest['sources'].append({'id': 'pdf', 'parent_id': 'gmail:abc', 'attachment_id': 'attach-123',
                                         'service_ids': ['acme'], 'kind': 'attachment', 'file': 'invoice.txt',
                                         'disposition': 'reviewed', 'note': 'Attachment text and totals reviewed.'})
        self.review['services'][0]['reviewed_source_ids'].append('pdf')
        self.assertEqual(self.assess()['status'], 'checked')

    def test_inline_logo_requires_explicit_irrelevant_triage(self):
        self.mailbox([{'id': 'abc'}])
        self.message(payload={'mime_type': 'multipart/related', 'parts': [
            {'mime_type': 'image/png', 'filename': 'logo.png', 'headers': [{'name': 'Content-ID', 'value': 'logo'}],
             'body': {'attachment_id': 'logo'}}]})
        self.assertIn('untriaged_attachment', self.codes(self.assess()))
        self.manifest['sources'].append({'id': 'logo', 'parent_id': 'gmail:abc', 'attachment_id': 'logo',
                                         'service_ids': ['acme'], 'kind': 'attachment',
                                         'disposition': 'irrelevant', 'note': 'Visually confirmed this is only the merchant logo.'})
        self.review.pop('evidence_sha256', None)
        self.assertNotIn('untriaged_attachment', self.codes(self.assess()))
        self.assertEqual(self.assess()['status'], 'checked')

    def test_converted_evidence_stays_unread_until_read_and_independently_reviewed(self):
        self.converted_message(reviewed=False)
        self.assertIn('unreviewed_source', self.codes(self.assess()))
        for source in self.manifest['sources'][1:]:
            source['disposition'] = 'reviewed'
        self.review.pop('evidence_sha256', None)
        self.assertIn('incomplete_independent_sources', self.codes(self.assess()))
        self.review['services'][0]['reviewed_source_ids'] = [source['id'] for source in self.manifest['sources']]
        self.assertEqual(self.assess()['status'], 'checked')

    def test_converted_inline_invoice_cannot_be_omitted_from_triage(self):
        self.converted_message()
        self.manifest['sources'] = [source for source in self.manifest['sources']
                                    if not source.get('file', '').endswith('invoice.png')]
        self.assertIn('untriaged_attachment', self.codes(self.assess()))

    def test_converted_original_and_all_derivatives_are_bound(self):
        self.converted_message()
        self.assertEqual(self.assess()['status'], 'checked')
        for role in ('original', 'body_text', 'attachment', 'attachment_text'):
            with self.subTest(role=role):
                path = self.extracted_file(role)
                original = path.read_bytes()
                path.write_bytes(original + b'Changed evidence')
                result = self.assess()
                self.assertEqual(result['status'], 'provisional')
                self.assertIn('message_extraction_unverified', self.codes(result))
                self.assertIn('invalid_evidence_digest', self.codes(result))
                path.write_bytes(original)
        self.assertEqual(self.assess()['status'], 'checked')

    def test_updating_a_derived_hash_still_invalidates_independent_review(self):
        self.converted_message()
        self.assertEqual(self.assess()['status'], 'checked')
        body = self.extracted_file('body_text')
        body.write_text('Different extracted body', encoding='utf-8')
        entry = next(item for item in self.converted_record['extraction']['files'] if item['role'] == 'body_text')
        entry['sha256'] = hashlib.sha256(body.read_bytes()).hexdigest()
        self.save_converted_record()
        self.assertIn('stale_evidence_review', self.codes(self.assess()))

    def test_missing_original_or_derived_file_blocks_even_with_complete_review(self):
        self.converted_message()
        self.assertEqual(self.assess()['status'], 'checked')
        for role in ('original', 'body_text', 'attachment_text'):
            with self.subTest(role=role):
                path = self.extracted_file(role)
                original = path.read_bytes()
                path.unlink()
                self.assertIn('message_extraction_unverified', self.codes(self.assess()))
                path.write_bytes(original)

    def test_extraction_manifest_must_be_complete_and_well_formed(self):
        self.converted_message()
        original = copy.deepcopy(self.converted_record)
        malformed = [None, {}, {'schema_version': '2', 'files': []},
                     {'schema_version': '1', 'files': []},
                     {'schema_version': '1', 'files': [None]}]
        for extraction in malformed:
            with self.subTest(extraction=extraction):
                self.converted_record = copy.deepcopy(original)
                self.converted_record['extraction'] = extraction
                self.save_converted_record()
                self.assertIn('message_extraction_unverified', self.codes(self.assess()))
        for role in ('original', 'body_text', 'attachment', 'attachment_text'):
            with self.subTest(missing_role=role):
                self.converted_record = copy.deepcopy(original)
                self.converted_record['extraction']['files'] = [entry for entry in original['extraction']['files'] if entry['role'] != role]
                self.save_converted_record()
                self.assertIn('message_extraction_unverified', self.codes(self.assess()))

    def test_raw_markers_cannot_omit_extraction_contract(self):
        self.converted_message()
        del self.converted_record['extraction']
        self.save_converted_record()
        self.assertIn('message_extraction_unverified', self.codes(self.assess()))
        del self.converted_record['source_format']
        self.save_converted_record()
        self.assertIn('message_extraction_unverified', self.codes(self.assess()))

    def test_missing_mime_attachment_link_cannot_fake_completed_review(self):
        self.converted_message()
        attachment = self.converted_record['payload']['parts'][1]
        del attachment['body']['file']
        self.save_converted_record()
        self.assertIn('message_extraction_unverified', self.codes(self.assess()))

    def test_reviewed_extracted_attachment_cannot_point_at_unrelated_file(self):
        self.converted_message()
        self.manifest['sources'][-1]['file'] = 'invoice.txt'
        self.assertIn('attachment_file_mismatch', self.codes(self.assess()))

    def test_original_gmail_id_must_match_source_and_normalized_message(self):
        self.converted_message()
        original = self.extracted_file('original')
        data = json.loads(original.read_text(encoding='utf-8'))
        data['structuredContent']['id'] = 'different-original-id'
        original.write_text(json.dumps(data), encoding='utf-8')
        entry = next(item for item in self.converted_record['extraction']['files'] if item['role'] == 'original')
        entry['sha256'] = hashlib.sha256(original.read_bytes()).hexdigest()
        self.save_converted_record()
        self.assertIn('message_extraction_unverified', self.codes(self.assess()))

    def test_extracted_file_paths_cannot_escape_or_refer_to_message_itself(self):
        self.converted_message()
        original = copy.deepcopy(self.converted_record)
        outside = self.base / 'invoice.txt'
        for name in (str(outside), '../invoice.txt', 'message.json', 'attachments/../body.txt'):
            with self.subTest(name=name):
                self.converted_record = copy.deepcopy(original)
                self.converted_record['extraction']['files'][0]['file'] = name
                self.save_converted_record()
                self.assertIn('message_extraction_unverified', self.codes(self.assess()))
        self.converted_record = original
        body = self.extracted_file('body_text')
        body.unlink()
        body.symlink_to(outside)
        self.save_converted_record()
        self.assertIn('message_extraction_unverified', self.codes(self.assess()))

    def test_complete_extracted_bundle_can_be_relocated_without_invalidating_review(self):
        self.converted_message(source_format='rfc822')
        self.assertEqual(self.assess()['status'], 'checked')
        with tempfile.TemporaryDirectory() as destination:
            moved = Path(destination) / 'moved'
            shutil.copytree(self.base, moved)
            self.assertEqual(audit_check.assess(self.report, moved / 'audit-evidence.json')['status'], 'checked')
            self.assertEqual(audit_check.evidence_digest(self.base / 'audit-evidence.json'),
                             audit_check.evidence_digest(moved / 'audit-evidence.json'))

    def test_nested_message_and_inline_invoice_keep_distinct_review_requirements(self):
        forwarded = EmailMessage()
        forwarded.set_content('Forwarded billing body')
        forwarded.add_attachment(b'Inline forwarded invoice', maintype='image', subtype='png',
                                 disposition='inline', cid='forwarded-invoice')
        outer = EmailMessage()
        outer.set_content('Please see the original receipt below.')
        outer.add_attachment(forwarded)
        self.converted_message(raw=outer.as_bytes())
        self.assertEqual(self.assess()['status'], 'checked')
        attachments = [source for source in self.manifest['sources'] if source['kind'] == 'attachment']
        self.assertEqual(len(attachments), 2)
        self.assertEqual(len({source['part_id'] for source in attachments}), 2)
        self.manifest['sources'].remove(attachments[-1])
        self.assertIn('untriaged_attachment', self.codes(self.assess()))

    def test_pdf_manifest_and_extracted_pages_are_bound_and_relocatable(self):
        from reportlab.pdfgen import canvas

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.drawString(40, 700, 'Synthetic invoice amount due USD9.00; no payment confirmed.')
        pdf.save()
        email = EmailMessage()
        email.set_content('The invoice is attached.')
        email.add_attachment(buffer.getvalue(), maintype='application', subtype='pdf', filename='invoice.pdf')
        self.converted_message(raw=email.as_bytes(), extract_pdf=True)
        self.assertEqual(self.assess()['status'], 'checked')
        with tempfile.TemporaryDirectory() as destination:
            moved = Path(destination) / 'moved'
            shutil.copytree(self.base, moved)
            self.assertEqual(audit_check.assess(self.report, moved / 'audit-evidence.json')['status'], 'checked')
        for role in ('pdf_manifest', 'attachment_text'):
            with self.subTest(role=role):
                target = self.extracted_file(role)
                original = target.read_bytes()
                target.write_bytes(original + b'Changed PDF extraction')
                self.assertIn('message_extraction_unverified', self.codes(self.assess()))
                target.write_bytes(original)

    def test_decoding_warning_can_be_resolved_by_reading_and_independent_review(self):
        raw = (b'Content-Type: text/plain; charset=does-not-exist\r\n'
               b'Content-Transfer-Encoding: base64\r\n\r\n' +
               base64.b64encode(b'Synthetic billing body with a charset warning.') + b'\r\n')
        self.converted_message(raw=raw)
        self.assertTrue(self.converted_record['extraction']['decoding_warnings'])
        self.assertEqual(self.assess()['status'], 'checked')

    def test_truncated_pagination_blocks(self):
        self.mailbox(next_token='page2')
        self.assertIn('incomplete_pagination', self.codes(self.assess()))

    def test_continuation_must_match_exact_query(self):
        self.mailbox(next_token='page2')
        self.manifest['searches'].append({'id': 'continuation', 'service_ids': ['acme'], 'kind': 'billing',
                                         'query': 'different query', 'request_page_token': 'page2', 'result_file': 'page2.json'})
        self.write('page2.json', {'ids': [], 'next_page_token': None})
        result = self.assess()
        self.assertIn('incomplete_pagination', self.codes(result))
        self.assertIn('missing_first_page', self.codes(result))

    def test_complete_pagination_and_triage_pass(self):
        self.mailbox(next_token='page2')
        self.manifest['searches'].append({**self.manifest['searches'][0], 'id': 'continuation',
                                         'request_page_token': 'page2', 'result_file': 'page2.json'})
        self.write('page2.json', {'ids': ['abc'], 'next_page_token': None})
        self.message()
        self.assertEqual(self.assess()['status'], 'checked')

    def test_disconnected_token_cycle_cannot_pass(self):
        self.mailbox()
        self.manifest['searches'].append({**self.manifest['searches'][0], 'id': 'cycle',
                                         'request_page_token': 'cycle', 'result_file': 'cycle.json'})
        self.write('cycle.json', {'ids': [], 'next_page_token': 'cycle'})
        self.assertIn('disconnected_search_page', self.codes(self.assess()))

    def test_metadata_only_saved_message_is_not_full_review_evidence(self):
        self.message(payload={'mime_type': 'multipart/mixed', 'headers': [{'name': 'Subject', 'value': 'Receipt'}]})
        self.assertIn('message_body_unverified', self.codes(self.assess()))

    def test_plain_fallback_does_not_hide_omitted_nonempty_html_body(self):
        self.message(payload={'mime_type': 'multipart/alternative', 'body': {'size': 0}, 'parts': [
            {'mime_type': 'text/plain', 'part_id': '0', 'body': {'size': 18, 'content': 'HTML not supported'}},
            {'mime_type': 'text/html', 'part_id': '1', 'body': {'size': 50000, 'content': None,
                                                                         'base64_url_content': None,
                                                                         'attachment_id': None}}]})
        result = self.assess()
        self.assertEqual(result['status'], 'provisional')
        self.assertIn('message_body_unverified', self.codes(result))

    def test_empty_alternative_bodies_with_unknown_size_are_not_full_content(self):
        self.message(payload={'mime_type': 'multipart/alternative', 'parts': [
            {'mime_type': 'text/plain', 'body': {'content': ''}},
            {'mime_type': 'text/html', 'body': {'content': None}}]})
        self.assertIn('message_body_unverified', self.codes(self.assess()))

    def test_saved_external_html_body_passes_after_attachment_review(self):
        self.message(payload={'mime_type': 'multipart/alternative', 'body': {'size': 0}, 'parts': [
            {'mime_type': 'text/plain', 'body': {'content': 'HTML not supported'}},
            {'mime_type': 'text/html', 'part_id': '1', 'body': {'size': 50000, 'attachment_id': 'html-body'}}]})
        self.manifest['sources'].append({'id': 'html', 'parent_id': 'gmail:abc', 'attachment_id': 'html-body',
                                         'service_ids': ['acme'], 'kind': 'attachment', 'file': 'invoice.txt',
                                         'disposition': 'reviewed', 'note': 'Read the externally stored HTML billing body.'})
        self.review['services'][0]['reviewed_source_ids'].append('html')
        self.assertEqual(self.assess()['status'], 'checked')

    def test_failed_tool_result_cannot_pass_as_empty_success(self):
        self.mailbox()
        self.write('page1.json', {'isError': True, 'structuredContent': {'emails': []}})
        self.assertIn('failed_search', self.codes(self.assess()))

    def test_bill_keyword_query_does_not_count_as_broad_discovery(self):
        self.mailbox()
        self.manifest['searches'][0]['query'] = 'from:acme.example (invoice OR receipt)'
        result = self.assess()
        self.assertIn('narrow_merchant_discovery', self.codes(result))
        self.assertIn('missing_merchant_discovery', self.codes(result))

    def test_billing_word_in_sender_address_is_permitted(self):
        self.mailbox()
        self.manifest['searches'][0]['query'] = 'from:billing@acme.example'
        self.assertEqual(self.assess()['status'], 'checked')

    def test_service_change_invalidates_review_digest(self):
        self.service['status'] = 'observed'
        self.assertIn('stale_independent_review', self.codes(self.assess()))

    def test_source_bytes_changed_after_review_invalidates_evidence_digest(self):
        self.assertEqual(self.assess()['status'], 'checked')
        (self.base / 'invoice.txt').write_text('Different invoice: USD900.00 paid', encoding='utf-8')
        self.assertIn('stale_evidence_review', self.codes(self.assess()))

    def test_changed_top_level_monthly_cost_invalidates_report_review(self):
        self.report['monthly_cost'] = {'items': [{'service_id': 'acme', 'amount': '9.00', 'currency': 'USD', 'months': 1}]}
        self.assertEqual(self.assess()['status'], 'checked')
        self.report['monthly_cost']['items'][0]['amount'] = '90.00'
        self.assertIn('stale_report_review', self.codes(self.assess()))

    def test_report_digest_keeps_summary_and_coverage_but_omits_computed(self):
        self.report['summary'] = 'Known cost only.'
        original = audit_check.report_digest(self.report)
        self.report['computed'] = {'monthly_baseline': {'USD': '999.00'}, 'audit_quality': {'status': 'checked'}}
        self.assertEqual(audit_check.report_digest(self.report), original)
        self.report['summary'] = 'Changed summary'
        self.assertNotEqual(audit_check.report_digest(self.report), original)
        self.report['summary'] = 'Known cost only.'
        self.report['coverage'] = {'scope': 'Changed mailbox coverage'}
        self.assertNotEqual(audit_check.report_digest(self.report), original)

    def test_search_bytes_changed_after_review_invalidates_evidence_digest(self):
        self.mailbox()
        self.assertEqual(self.assess()['status'], 'checked')
        self.write('page1.json', {'emails': [], 'next_page_token': None, 'extra': 'changed bytes'})
        self.assertIn('stale_evidence_review', self.codes(self.assess()))

    def test_shadow_file_on_search_cannot_hide_changed_result_bytes(self):
        self.mailbox()
        self.manifest['searches'][0]['file'] = 'invoice.txt'
        self.write('audit-evidence.json', self.manifest)
        before = audit_check.evidence_digest(self.base / 'audit-evidence.json')
        self.review['evidence_sha256'] = before
        self.write('page1.json', {'emails': [], 'next_page_token': None, 'changed': 'actual search response bytes'})
        after = audit_check.evidence_digest(self.base / 'audit-evidence.json')
        self.assertNotEqual(before, after)
        result = self.assess()
        self.assertIn('ambiguous_search_file', self.codes(result))
        self.assertIn('stale_evidence_review', self.codes(result))

    def test_shadow_result_file_on_source_does_not_replace_source_file(self):
        self.manifest['sources'][0]['result_file'] = 'unused.json'
        self.write('unused.json', {'synthetic': 'unrelated'})
        self.write('audit-evidence.json', self.manifest)
        before = audit_check.evidence_digest(self.base / 'audit-evidence.json')
        self.review['evidence_sha256'] = before
        (self.base / 'invoice.txt').write_text('Changed actual invoice bytes', encoding='utf-8')
        self.assertNotEqual(before, audit_check.evidence_digest(self.base / 'audit-evidence.json'))
        result = self.assess()
        self.assertIn('ambiguous_source_file', self.codes(result))
        self.assertIn('stale_evidence_review', self.codes(result))

    def test_independent_review_contents_are_not_in_evidence_digest(self):
        self.assess()
        before = audit_check.evidence_digest(self.base / 'audit-evidence.json')
        self.write('review.json', {'different': 'review content'})
        self.assertEqual(audit_check.evidence_digest(self.base / 'audit-evidence.json'), before)

    def test_other_refund_case_cannot_be_omitted_from_independent_review(self):
        self.report['other_cases'] = [{'id': 'deposit', 'name': 'Deposit refund', 'review_group': 'refund'}]
        result = self.assess()
        self.assertEqual(result['status'], 'provisional')
        self.assertIn('missing_independent_service', self.codes(result))
        self.assertEqual(result['counts']['entities'], 2)

    def test_other_case_gets_its_own_digest_and_source_review(self):
        case = {'id': 'deposit', 'name': 'Deposit refund', 'review_group': 'refund'}
        self.report['other_cases'] = [case]
        self.manifest['sources'][0]['service_ids'].append('deposit')
        self.review['services'].append({'service_id': 'deposit', 'service_sha256': audit_check.service_digest(case),
                                       'reviewed_source_ids': ['invoice'], 'verdict': 'pass',
                                       'note': 'Independently assessed the deposit terms and unresolved refund evidence.'})
        result = self.assess()
        self.assertEqual(result['status'], 'checked')
        self.assertEqual(result['counts']['independently_reviewed_entities'], 2)
        case['name'] = 'Changed refund claim'
        self.assertIn('stale_independent_review', self.codes(self.assess()))

    def test_hash_is_canonical_and_keeps_all_fields(self):
        self.assertEqual(audit_check.service_digest({'b': '中文', 'a': 1}), audit_check.service_digest({'a': 1, 'b': '中文'}))
        self.assertNotEqual(audit_check.service_digest({'a': 1}), audit_check.service_digest({'a': 1, 'review_note': 'changed'}))

    def test_new_reviewed_source_requires_independent_coverage(self):
        self.message()
        self.review['services'][0]['reviewed_source_ids'].remove('gmail:abc')
        self.assertIn('incomplete_independent_sources', self.codes(self.assess()))

    def test_irrelevant_result_requires_reason_but_no_download(self):
        self.mailbox([{'id': 'news'}])
        self.manifest['sources'].append({'id': 'gmail:news', 'kind': 'message', 'service_ids': ['acme'],
                                         'disposition': 'irrelevant', 'note': 'Generic release announcement, no account billing or lifecycle facts.'})
        self.assertEqual(self.assess()['status'], 'checked')
        self.manifest['sources'][-1]['note'] = ''
        self.assertIn('missing_source_reason', self.codes(self.assess()))

    def test_escape_paths_and_symlinks_are_rejected(self):
        self.manifest['sources'][0]['file'] = '../outside.txt'
        self.assertIn('inaccessible_evidence_file', self.codes(self.assess()))
        (self.base / 'escape').symlink_to(SCRIPT)
        self.manifest['sources'][0]['file'] = 'escape'
        self.assertIn('inaccessible_evidence_file', self.codes(self.assess()))

    def test_malformed_manifest_returns_provisional_instead_of_crashing(self):
        self.manifest['sources'][0]['kind'] = ['bad']
        self.assertEqual(self.assess()['status'], 'provisional')

    def test_cli_exit_codes_and_overwrite_guard(self):
        renderer_spec = importlib.util.spec_from_file_location('renderer', SCRIPT.with_name('render_dashboard.py'))
        renderer = importlib.util.module_from_spec(renderer_spec)
        renderer_spec.loader.exec_module(renderer)
        renderer.prepare(self.report)
        self.review['services'][0]['service_sha256'] = audit_check.service_digest(self.service)
        self.assess()
        self.write('report.json', self.report)
        command = [sys.executable, str(SCRIPT), '--report', str(self.base / 'report.json'),
                   '--evidence', str(self.base / 'audit-evidence.json'), '--output', str(self.base / 'check.json')]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
        self.service['status'] = 'observed'
        self.write('report.json', self.report)
        self.assertEqual(subprocess.run(command + ['--force'], capture_output=True).returncode, 2)


if __name__ == '__main__':
    unittest.main()
