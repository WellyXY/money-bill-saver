#!/usr/bin/env python3
"""Prepare private evidence packets for an independent reviewer; never approve them.

Packets reference saved original evidence without copying mail into every row.
Their hashes identify affected entities; the report-wide packet still requires
review of discovery, unresolved candidates, monthly inputs and coverage changes.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def _sibling(name):
    spec = importlib.util.spec_from_file_location('review_' + name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = _sibling('check_audit')
renderer = _sibling('render_dashboard')
GENERATOR = 'money-bill-saver.prepare_review/1'


def prepare_packets(report, evidence_path, previous_review=None):
    """Return unreviewed packets without changing evidence or reviewer verdicts."""
    evidence_path = Path(evidence_path).resolve(strict=True)
    manifest = json.loads(evidence_path.read_text(encoding='utf-8'))
    # Renderer preparation can add defaults; do not mutate the caller's report.
    prepared = renderer.prepare(json.loads(json.dumps(report, allow_nan=False)))
    evidence_sha = audit.evidence_digest(evidence_path)
    report_sha = audit.report_digest(prepared)
    records = audit.entity_evidence_records(evidence_path)
    previous_review = previous_review or {}
    prior_rows = {row['service_id']: row for row in previous_review.get('services', [])
                  if isinstance(row, dict) and isinstance(row.get('service_id'), str)}
    packets = []
    for row in prepared['subscriptions'] + prepared.get('other_cases', []):
        sid = row['id']
        record = records.get(sid, {'sources': [], 'files': {}})
        row_sha, source_sha = audit.service_digest(row), audit.service_digest(record)
        prior = prior_rows.get(sid)
        packets.append({
            'schema_version': '1', 'status': 'unreviewed_packet', 'service_id': sid,
            'service_sha256': row_sha, 'entity_evidence_sha256': source_sha,
            'evidence_root': str(evidence_path.parent), 'row': row,
            'sources': record['sources'], 'evidence_files': record['files'],
            'author_reviewed_source_ids': [source['id'] for source in record['sources']
                                           if source.get('disposition') == 'reviewed'],
            'changes_since_previous_review': {
                'previous_row_found': prior is not None,
                'row_changed': prior is None or prior.get('service_sha256') != row_sha,
                'material_evidence_changed': prior is None or prior.get('entity_evidence_sha256') != source_sha,
            },
        })
    candidate_ids = set()
    result_occurrences = 0
    for search in manifest['searches']:
        # evidence_digest already checked containment and exact bytes.
        raw = audit._unwrap(json.loads((evidence_path.parent / search['result_file']).read_text(encoding='utf-8')))
        for entry in raw.get('emails', raw.get('ids', [])):
            mid = entry.get('id') if isinstance(entry, dict) else entry
            if isinstance(mid, str):
                candidate_ids.add(audit._message_id(mid))
                result_occurrences += 1
    sources = manifest['sources']
    summary = {
        'schema_version': '1', 'status': 'unreviewed_packet',
        'notice': 'No reviewer verdict or source disposition is created by this helper. Independently review originals and record final bindings; unchanged packet hashes do not approve themselves.',
        'evidence_manifest': str(evidence_path),
        'evidence_sha256': evidence_sha, 'report_sha256': report_sha,
        'scope': manifest['scope'], 'searches': manifest['searches'],
        'report_context': {key: value for key, value in prepared.items()
                           if key not in {'subscriptions', 'other_cases', 'computed'}},
        'triage': {
            'unique_returned_messages': len(candidate_ids),
            'result_occurrences': result_occurrences,
            'disposition_counts': {state: sum(source.get('disposition') == state for source in sources)
                                   for state in ('reviewed', 'irrelevant', 'unread', 'inaccessible')},
            'unassigned_candidates': [source for source in sources if not source.get('service_ids')
                                      and source.get('disposition') != 'irrelevant'],
            'unresolved_sources': [source for source in sources if source.get('disposition') in {'unread', 'inaccessible'}],
            'irrelevant_sources': [source for source in sources if source.get('disposition') == 'irrelevant'],
        },
        'gate': audit.assess(prepared, evidence_path),
        'changes_since_previous_review': {
            'report_changed': previous_review.get('report_sha256') != report_sha,
            'global_evidence_changed': previous_review.get('evidence_sha256') != evidence_sha,
        },
        'entities': [{'service_id': packet['service_id'],
                      'service_sha256': packet['service_sha256'],
                      'entity_evidence_sha256': packet['entity_evidence_sha256'],
                      'changes_since_previous_review': packet['changes_since_previous_review']}
                     for packet in packets],
    }
    return {'global': summary, 'entities': packets}


def _protected_inputs(packets, extra_inputs):
    """Include originals and derivatives, even those excluded from entity packets."""
    manifest_path = Path(packets['global']['evidence_manifest']).resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    base = manifest_path.parent
    protected = {manifest_path, *(Path(path).resolve() for path in extra_inputs)}
    if manifest.get('independent_review_file'):
        protected.add((base / manifest['independent_review_file']).resolve())
    for collection, field in (('sources', 'file'), ('searches', 'result_file')):
        for row in manifest[collection]:
            if not row.get(field):
                continue
            path = (base / row[field]).resolve(strict=True)
            protected.add(path)
            if collection == 'sources' and row.get('kind') == 'message':
                message = audit._unwrap(json.loads(path.read_text(encoding='utf-8')))
                protected.update(base / name for name in audit._bound_message_files(message, path, base, row['id']))
    return protected


def write_packets(packets, output_dir, force=False, protected_inputs=()):
    """Preflight every target before writing; force only replaces our own packets."""
    output = Path(output_dir)
    if output.is_symlink():
        raise OSError('Output directory must not be a symlink')
    if output.exists() and not force:
        raise OSError('Output directory exists; pass --force to replace generated packet files')
    entries, generated = [], []
    for packet in packets['entities']:
        # IDs are user data, never filesystem paths.
        name = 'entity-' + hashlib.sha256(packet['service_id'].encode()).hexdigest() + '.json'
        entries.append({'service_id': packet['service_id'], 'file': name})
        generated.append((output / name, dict(packet, generated_by=GENERATOR)))
    generated.append((output / 'global-review.json', dict(packets['global'], packet_files=entries, generated_by=GENERATOR)))
    protected = _protected_inputs(packets, protected_inputs)
    identities = {(path.stat().st_dev, path.stat().st_ino) for path in protected if path.exists()}
    serialized = []
    for target, content in generated:
        if target.is_symlink():
            raise OSError('Refusing to overwrite a packet symlink')
        if target.resolve() in protected or (target.exists()
                and (target.stat().st_dev, target.stat().st_ino) in identities):
            raise OSError(f'Refusing to overwrite an input or original evidence file: {target}')
        if target.exists():
            if not target.is_file():
                raise OSError(f'Packet target is not a file: {target}')
            try:
                previous = json.loads(target.read_text(encoding='utf-8'))
            except (OSError, ValueError, UnicodeError) as exc:
                raise OSError(f'Existing target is not a generated review packet: {target}') from exc
            if (not isinstance(previous, dict) or previous.get('generated_by') != GENERATOR
                    or previous.get('schema_version') != '1' or previous.get('status') != 'unreviewed_packet'
                    or previous.get('service_id') != content.get('service_id')):
                raise OSError(f'Existing target is not a matching generated review packet: {target}')
        serialized.append((target, json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + '\n'))
    # No mutation, including permissions or creation of an earlier packet, occurs
    # until every target has passed collision and recognizable-output checks.
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.chmod(0o700)
    for target, content in serialized:
        target.write_text(content, encoding='utf-8')
        target.chmod(0o600)
    return output / 'global-review.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--previous-review', type=Path, help='Optional prior independent review for change indicators only')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding='utf-8'))
        previous = json.loads(args.previous_review.read_text(encoding='utf-8')) if args.previous_review else None
        packets = prepare_packets(report, args.evidence, previous)
        inputs = [args.report] + ([args.previous_review] if args.previous_review else [])
        target = write_packets(packets, args.output_dir, args.force, protected_inputs=inputs)
        print(f'Wrote {len(packets["entities"])} unreviewed entity packets and {target}')
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
