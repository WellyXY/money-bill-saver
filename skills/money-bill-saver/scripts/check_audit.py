#!/usr/bin/env python3
"""Check declared audit coverage, and an optional review bound to the final rows.

Evidence coverage is the always-required gate. Independent review is opt-in: it
runs when the manifest declares an ``independent_review_file`` or when the caller
passes ``require_independent_review``. This is a completion gate, not a payment
classifier or a guarantee of truth.
"""
import argparse
from datetime import date, datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys


def service_digest(service):
    """Hash the complete, prepared service row. No fields are silently excluded."""
    encoded = json.dumps(service, sort_keys=True, ensure_ascii=False,
                         separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def report_digest(prepared_report):
    """Bind every substantive report field; only renderer-computed data is omitted."""
    substantive = {key: value for key, value in prepared_report.items() if key != 'computed'}
    return service_digest(substantive)


def evidence_digest(evidence_path):
    """Bind scope, search/source metadata and file bytes; exclude review contents."""
    path = Path(evidence_path).resolve(strict=True)
    manifest = json.loads(path.read_text(encoding='utf-8'))
    base = path.parent
    metadata = {key: manifest[key] for key in ('scope', 'searches', 'sources')}
    files = {}
    # Use exactly the same collection-specific field that assess reads. A stray
    # source-style "file" field on a search must never hide its result_file bytes.
    for collection, field in (('sources', 'file'), ('searches', 'result_file')):
        for row in manifest[collection]:
            name = row.get(field)
            if name is None:
                continue
            if not isinstance(name, str) or not name or Path(name).is_absolute():
                raise ValueError('Evidence digest requires relative file paths')
            target = (base / name).resolve(strict=True)
            if not target.is_relative_to(base) or not target.is_file():
                raise ValueError('Evidence digest cannot read outside the manifest directory')
            data = target.read_bytes()
            if not data:
                raise ValueError('Evidence digest cannot include empty files')
            files[name] = hashlib.sha256(data).hexdigest()
    canonical = json.dumps({'metadata': metadata, 'files': files}, sort_keys=True,
                           ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _message_id(value):
    return value.removeprefix('gmail:') if isinstance(value, str) else value


def _unwrap(value):
    return value.get('structuredContent', value) if isinstance(value, dict) else value


def _meaningful_parts(part):
    """Return attachment identifiers, including externally stored text bodies."""
    if not isinstance(part, dict):
        return []
    body = part.get('body') or {}
    mime = part.get('mime_type', part.get('mimeType', ''))
    headers = {str(h.get('name', '')).lower(): str(h.get('value', ''))
               for h in part.get('headers', []) if isinstance(h, dict)}
    inline_image = mime.startswith('image/') and (
        'inline' in headers.get('content-disposition', '').lower()
        or 'content-id' in headers)
    attachment_id = body.get('attachment_id', body.get('attachmentId'))
    filename = part.get('filename')
    result = []
    if not inline_image and (attachment_id or filename):
        result.append({'attachment_id': attachment_id,
                       'part_id': part.get('part_id', part.get('partId', '')),
                       'filename': filename or mime or 'message body'})
    for child in part.get('parts') or []:
        result.extend(_meaningful_parts(child))
    return result


def _has_message_content(part):
    if not isinstance(part, dict):
        return False
    body = part.get('body') or {}
    if any(_text(body.get(key)) for key in ('content', 'base64_url_content', 'data', 'attachment_id', 'attachmentId')):
        return True
    return any(_has_message_content(child) for child in part.get('parts') or [])


def _missing_text_parts(part):
    """Find omitted text bodies even when another MIME alternative has content."""
    if not isinstance(part, dict):
        return []
    body = part.get('body') or {}
    mime = part.get('mime_type', part.get('mimeType', ''))
    size = body.get('size')
    available = any(isinstance(body.get(key), str) and len(body[key]) > 0
                    for key in ('content', 'base64_url_content', 'data', 'attachment_id', 'attachmentId'))
    missing = []
    if mime.startswith('text/') and isinstance(size, (int, float)) and size > 0 and not available:
        missing.append(f"{mime} part {part.get('part_id', part.get('partId', 'root'))} declares {size} bytes but has no body or attachment reference")
    for child in part.get('parts') or []:
        missing.extend(_missing_text_parts(child))
    return missing


def _assess(report, evidence_path=None, require_independent_review=False):
    """Return checked/provisional; malformed evidence never marks a report checked."""
    issues = []
    review_state = 'not_requested'

    counts = {'services': 0, 'other_cases': 0, 'entities': 0, 'searches': 0, 'search_results': 0,
              'sources': 0, 'reviewed_sources': 0, 'independently_reviewed_services': 0,
              'independently_reviewed_entities': 0}
    scope = None

    def add(code, message, service_id=None):
        item = {'code': code, 'message': message}
        if service_id is not None:
            item['service_id'] = service_id
        if item not in issues:
            issues.append(item)

    def finish():
        checked = not issues
        if checked and review_state == 'passed':
            summary = ('Declared evidence coverage and independent service review passed; '
                       'account completeness and factual accuracy are not guaranteed.')
        elif checked:
            summary = ('Declared evidence coverage passed; no independent review was run, and '
                       'account completeness and factual accuracy are not guaranteed.')
        elif review_state == 'not_requested':
            summary = 'Provisional: evidence coverage is incomplete.'
        else:
            summary = 'Provisional: evidence coverage or independent review is incomplete.'
        return {'status': 'checked' if checked else 'provisional',
                'summary': summary, 'independent_review': review_state,
                'issues': issues, 'counts': counts, 'scope': scope}

    services = report.get('subscriptions') if isinstance(report, dict) else None
    if not isinstance(services, list) or any(not isinstance(s, dict) or not _text(s.get('id')) for s in services):
        add('invalid_report', 'Report subscriptions must contain service objects with nonempty IDs.')
        return finish()
    other_cases = report.get('other_cases', [])
    if not isinstance(other_cases, list) or any(not isinstance(s, dict) or not _text(s.get('id')) for s in other_cases):
        add('invalid_report', 'Other cases must contain objects with nonempty IDs.')
        return finish()
    entities = services + other_cases
    by_service = {s['id']: s for s in entities}
    subscription_ids = {s['id'] for s in services}
    counts['services'] = len(services)
    counts['other_cases'] = len(other_cases)
    counts['entities'] = len(entities)
    if len(by_service) != len(entities):
        add('duplicate_service', 'Report contains duplicate IDs across services and other cases.')
    if evidence_path is None:
        add('missing_evidence_manifest', 'No audit-evidence.json was supplied.')
        return finish()
    try:
        manifest_path = Path(evidence_path).resolve(strict=True)
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if not isinstance(manifest, dict):
            raise ValueError('Manifest must be an object')
    except (OSError, ValueError, TypeError) as exc:
        add('invalid_evidence_manifest', str(exc))
        return finish()
    base = manifest_path.parent

    def local_file(value, context, parse=False):
        try:
            if not _text(value) or Path(value).is_absolute():
                raise ValueError('Use a relative file path below the manifest directory')
            path = (base / value).resolve(strict=True)
            if not path.is_relative_to(base) or not path.is_file():
                raise ValueError('File must remain below the manifest directory, including symlinks')
            if path.stat().st_size == 0:
                raise ValueError('File is empty')
            return json.loads(path.read_text(encoding='utf-8')) if parse else path
        except (OSError, ValueError, TypeError) as exc:
            add('inaccessible_evidence_file', f'{context}: {exc}')
            return None

    scope = manifest.get('scope')
    if not isinstance(scope, dict) or scope.get('mode') not in {'mailbox', 'files'} or not _text(scope.get('description')):
        add('invalid_scope', 'Scope needs mode mailbox/files and a specific description.')
        scope = None
    else:
        try:
            value = scope.get('as_of')
            if not isinstance(value, str):
                raise ValueError()
            if len(value) == 10:
                date.fromisoformat(value)
            elif datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo is None:
                raise ValueError()
        except (ValueError, TypeError):
            add('invalid_scope_date', 'Scope as_of must be an ISO date or a timestamp with timezone.')

    def service_refs(row, context):
        refs = row.get('service_ids')
        if not isinstance(refs, list) or not refs or any(not _text(s) or s not in by_service for s in refs) or len(set(refs)) != len(refs):
            add('invalid_service_references', f'{context}: service_ids must list known, distinct services.')
            return []
        return refs

    sources = manifest.get('sources')
    if not isinstance(sources, list):
        add('invalid_sources', 'sources must be an array.')
        sources = []
    source_map, source_refs, messages, expected_review = {}, {}, {}, {sid: set() for sid in by_service}
    for source in sources:
        if not isinstance(source, dict) or not _text(source.get('id')):
            add('invalid_source', 'Every source needs an ID.')
            continue
        sid = source['id']
        if sid in source_map:
            add('duplicate_source', f'Duplicate source {sid}.')
            continue
        source_map[sid] = source
        if 'result_file' in source:
            add('ambiguous_source_file', f'{sid}: sources use file, not the search-only result_file field.')
        refs = service_refs(source, sid)
        source_refs[sid] = refs
        kind, disposition = source.get('kind'), source.get('disposition')
        if kind not in {'message', 'attachment', 'account_page', 'document'}:
            add('invalid_source_kind', f'{sid}: unsupported source kind.')
        if disposition not in {'reviewed', 'irrelevant', 'unread', 'inaccessible'}:
            add('invalid_source_disposition', f'{sid}: unsupported source disposition.')
        if not _text(source.get('note')):
            add('missing_source_reason', f'{sid}: record what was reviewed or why it was excluded.')
        if kind == 'message':
            key = _message_id(sid)
            if key in messages:
                add('duplicate_message', f'Duplicate aliases for message {key}.')
            messages[key] = source
        if disposition in {'unread', 'inaccessible'}:
            add('unreviewed_source', f'{sid}: source is {disposition}.')
        if disposition == 'reviewed':
            counts['reviewed_sources'] += 1
            for ref in refs:
                expected_review[ref].add(sid)
            path = local_file(source.get('file'), sid)
            if kind == 'message' and path is not None:
                try:
                    message = _unwrap(json.loads(path.read_text(encoding='utf-8')))
                    payload = message.get('payload') if isinstance(message, dict) else None
                    if not isinstance(payload, dict):
                        raise ValueError('Reviewed messages require a saved full Gmail MIME payload')
                    if not _has_message_content(payload):
                        raise ValueError('Saved message has no full body or attachment content; metadata/snippet alone is insufficient')
                    for missing in _missing_text_parts(payload):
                        add('message_body_unverified', f'{sid}: {missing}.')
                    if message.get('id') and _message_id(message['id']) != _message_id(sid):
                        add('message_id_mismatch', f'{sid}: saved message ID does not match source ID.')
                    source['_audit_required_parts'] = _meaningful_parts(payload)
                except (OSError, ValueError, TypeError) as exc:
                    add('message_body_unverified', f'{sid}: {exc}')
        elif source.get('file') is not None:
            local_file(source['file'], sid)
    counts['sources'] = len(source_map)

    for sid, source in source_map.items():
        if source.get('kind') == 'attachment':
            parent = source.get('parent_id')
            if parent not in source_map or source_map[parent].get('kind') != 'message':
                add('invalid_attachment_parent', f'{sid}: parent_id must reference its saved message source.')
            elif not set(source_refs.get(parent, [])).issubset(source_refs[sid]):
                add('attachment_service_mismatch', f'{sid}: attachment must cover its parent service references.')
        for part in source.pop('_audit_required_parts', []):
            matches = [a for a in source_map.values() if a.get('kind') == 'attachment' and a.get('parent_id') == sid
                       and ((part['attachment_id'] and a.get('attachment_id') == part['attachment_id'])
                            or (not part['attachment_id'] and a.get('part_id') == part['part_id']))]
            if not matches:
                add('untriaged_attachment', f"{sid}: attachment {part['filename']} must be saved and reviewed, or explicitly triaged with a reason.")

    searches = manifest.get('searches')
    if not isinstance(searches, list):
        add('invalid_searches', 'searches must be an array, including an empty array in files mode.')
        searches = []
    pages, search_ids, discovery = {}, set(), set()
    for search in searches:
        if not isinstance(search, dict) or not _text(search.get('id')):
            add('invalid_search', 'Every search needs an ID.')
            continue
        sid = search['id']
        if 'file' in search:
            add('ambiguous_search_file', f'{sid}: searches use result_file, not the source-only file field.')
        if sid in search_ids:
            add('duplicate_search', f'Duplicate search {sid}.')
        search_ids.add(sid)
        refs = service_refs(search, sid)
        kind, query = search.get('kind'), search.get('query')
        if kind not in {'merchant_discovery', 'billing', 'lifecycle'} or not _text(query):
            add('invalid_search', f'{sid}: valid kind and exact query are required.')
            continue
        if kind == 'merchant_discovery':
            # Ignore sender/address tokens; catch obvious keyword-only restrictions.
            terms = re.sub(r'\b(?:from|to):[^\s()]+', '', query, flags=re.I)
            if re.search(r'\b(?:invoices?|receipts?|payments?|paid|charges?|billing)\b', terms, re.I):
                add('narrow_merchant_discovery', f'{sid}: merchant discovery is narrowed by English billing keywords.')
            else:
                discovery.update(refs)
        raw = local_file(search.get('result_file'), sid, parse=True)
        if isinstance(raw, dict) and raw.get('isError'):
            add('failed_search', f'{sid}: saved tool result reports an error.')
        raw = _unwrap(raw)
        if not isinstance(raw, dict):
            add('invalid_search_result', f'{sid}: search result must be an object.')
            continue
        results = raw.get('emails', raw.get('ids'))
        if not isinstance(results, list):
            add('invalid_search_result', f'{sid}: raw result must contain emails[] or ids[].')
            continue
        token = search.get('request_page_token')
        next_token = raw.get('next_page_token', raw.get('nextPageToken'))
        if (token is not None and not _text(token)) or (next_token is not None and not _text(next_token)):
            add('invalid_page_token', f'{sid}: page tokens must be nonempty strings or null.')
            continue
        key = (query, token)
        if key in pages:
            add('duplicate_search_page', f'{sid}: same query and page token recorded more than once.')
        pages[key] = (next_token, set(refs))
        counts['search_results'] += len(results)
        for entry in results:
            mid = entry.get('id') if isinstance(entry, dict) else entry
            if not _text(mid):
                add('invalid_result_id', f'{sid}: every result requires a message ID.')
                continue
            source = messages.get(_message_id(mid))
            if source is None:
                add('untriaged_search_result', f'{sid}: message {mid} has no source disposition and reason.')
            elif not set(refs).issubset(source_refs[source['id']]):
                add('result_service_mismatch', f'{sid}: message {mid} does not cover all searched service references.')
    counts['searches'] = len(search_ids)
    for (query, token), (next_token, refs) in pages.items():
        if next_token is not None and (query, next_token) not in pages:
            add('incomplete_pagination', f'Search has an unread next page: {query}')
        elif next_token is not None and not refs.issubset(pages[(query, next_token)][1]):
            add('pagination_service_mismatch', f'Next page drops service coverage: {query}')
        if token is not None and not any(q == query and nxt == token for (q, _), (nxt, _) in pages.items()):
            add('orphan_search_page', f'Continuation has no saved preceding page: {query}')
    for query in {q for q, _ in pages}:
        seen, token = set(), None
        if (query, None) not in pages:
            add('missing_first_page', f'Search lacks its first page: {query}')
            continue
        while (query, token) in pages:
            if token in seen:
                add('pagination_cycle', f'Pagination did not terminate: {query}')
                break
            seen.add(token)
            token = pages[(query, token)][0]
            if token is None:
                break
        if {t for q, t in pages if q == query} - seen:
            add('disconnected_search_page', f'Saved pages are not reachable from the first page: {query}')
    if scope and scope['mode'] == 'mailbox':
        for sid in by_service.keys() - discovery:
            add('missing_merchant_discovery', 'No broad merchant discovery search is recorded.', sid)
    if scope and scope['mode'] == 'files' and not source_map:
        add('empty_file_scope', 'Files-only review must declare the supplied sources.')

    declared_review = manifest.get('independent_review_file')
    if declared_review is None and not require_independent_review:
        # Independent review is user-triggered. Evidence coverage alone decides the gate.
        return finish()
    review_state = 'incomplete'
    before_review = len(issues)
    review = local_file(declared_review, 'independent_review_file', parse=True)
    if not isinstance(review, dict) or not _text(review.get('reviewer')) or not isinstance(review.get('services'), list) or not isinstance(review.get('issues'), list):
        add('missing_independent_review', 'Independent review needs reviewer, services[], and issues[].')
        return finish()
    try:
        if review.get('evidence_sha256') != evidence_digest(manifest_path):
            add('stale_evidence_review', 'Evidence metadata or source/search file bytes changed after independent review, or its evidence digest is missing.')
    except (OSError, ValueError, TypeError, KeyError) as exc:
        add('invalid_evidence_digest', f'Evidence could not be bound to independent review: {exc}')
    try:
        if review.get('report_sha256') != report_digest(report):
            add('stale_report_review', 'Substantive report data changed after independent review, or its report digest is missing.')
    except (ValueError, TypeError):
        add('invalid_report_digest', 'Substantive report data cannot be represented as canonical JSON.')
    reviewed = set()
    for row in review['services']:
        if not isinstance(row, dict) or not _text(row.get('service_id')) or row['service_id'] not in by_service:
            add('invalid_independent_service', 'Review must reference a known service.')
            continue
        sid = row['service_id']
        if sid in reviewed:
            add('duplicate_independent_service', 'Service appears twice in independent review.', sid)
        reviewed.add(sid)
        if row.get('verdict') != 'pass':
            add('independent_needs_review', row.get('note') or 'Independent review did not pass.', sid)
        if not _text(row.get('note')):
            add('missing_independent_note', 'Independent review needs a service-specific rationale.', sid)
        try:
            if row.get('service_sha256') != service_digest(by_service[sid]):
                add('stale_independent_review', 'Service row changed after independent review.', sid)
        except (ValueError, TypeError):
            add('invalid_service_digest', 'Service cannot be represented as canonical JSON.', sid)
        refs = row.get('reviewed_source_ids')
        if not isinstance(refs, list) or any(not _text(ref) for ref in refs):
            add('invalid_review_sources', 'reviewed_source_ids must be an array of source IDs.', sid)
        else:
            if not expected_review[sid].issubset(set(refs)):
                add('incomplete_independent_sources', 'Independent review did not cover all reviewed relevant sources.', sid)
            if any(ref not in source_map or sid not in source_refs[ref] for ref in refs):
                add('unknown_independent_source', 'Independent review cites an undeclared or unrelated source.', sid)
        counts['independently_reviewed_entities'] += 1
        if sid in subscription_ids:
            counts['independently_reviewed_services'] += 1
    for sid in by_service.keys() - reviewed:
        add('missing_independent_service', 'Service has no independent review.', sid)
    for issue in review['issues']:
        if not isinstance(issue, dict) or not _text(issue.get('message')):
            add('invalid_independent_issue', 'Independent issue needs a message.')
        elif issue.get('blocking', True) is not False:
            add('independent_blocking_issue', issue['message'], issue.get('service_id'))
    if len(issues) == before_review:
        review_state = 'passed'
    return finish()


def assess(report, evidence_path=None, require_independent_review=False):
    """Treat malformed manifests as provisional instead of crashing callers."""
    try:
        return _assess(report, evidence_path, require_independent_review)
    except (TypeError, ValueError, KeyError, AttributeError, UnicodeError, RecursionError) as exc:
        return {'status': 'provisional',
                'summary': 'Provisional: the evidence manifest could not be validated.',
                'independent_review': 'unknown',
                'issues': [{'code': 'invalid_evidence_manifest', 'message': str(exc)}],
                'counts': {}, 'scope': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, help='Report JSON; renderer defaults are applied before checking')
    parser.add_argument('--evidence', help='audit-evidence.json path')
    parser.add_argument('--output', required=True, help='Write audit-check.json here')
    parser.add_argument('--force', action='store_true', help='Replace an existing check output')
    parser.add_argument('--require-independent-review', action='store_true',
                        help='Require an independent review even when the manifest declares none')
    args = parser.parse_args()
    try:
        output = Path(args.output)
        if output.exists() and not args.force:
            raise OSError('Output exists; pass --force to replace it')
        report = json.loads(Path(args.report).read_text(encoding='utf-8'))
        spec = importlib.util.spec_from_file_location('audit_renderer', Path(__file__).with_name('render_dashboard.py'))
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        report = renderer.prepare(report)
        result = assess(report, args.evidence, args.require_independent_review)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(result['summary'])
        return 0 if result['status'] == 'checked' else 2
    except (OSError, ValueError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
