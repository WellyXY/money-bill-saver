#!/usr/bin/env python3
"""Build a contract-valid dashboard.json (and evidence manifest) from a compact plan.

The plan holds one entry per reviewed service or case. This helper expands the
repetitive contract shape around it: the three billing-date events, review group
and refund basis, screening-signal fields, the monthly baseline, and the
service_ids on every evidence source. It then validates the result with the real
renderer so a field mistake surfaces here instead of at render time.

It does not read evidence, decide status, or invent amounts. Every fact in the
output comes from the plan.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import re
import sys


DATE_EVENTS = ('last_invoice', 'last_charge', 'next_renewal')
UNKNOWN_NOTE = 'Not established in the reviewed sources.'
EXTERNAL = re.compile(r'^(?:https?|mailto):', re.I)

ROW_KEYS = {'id', 'name', 'initials', 'category', 'plan', 'status', 'status_label', 'status_note',
            'cost', 'monthly', 'cost_unknown', 'dates', 'renewal', 'needs_action', 'review_group',
            'refund', 'signals', 'priority', 'issue', 'action', 'evidence', 'unknowns', 'drafts',
            'sources'}
SIGNAL_KEYS = {'type', 'title', 'reason', 'evidence_note', 'next_check',
               'related_service_ids', 'source_ids'}
PLAN_KEYS = {'report', 'monthly_cost', 'evidence', 'services', 'cases', 'extra_source_ids'}


class BuildError(ValueError):
    """A plan that cannot be turned into a valid report."""


def _load(path):
    plan = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(plan, dict):
        raise BuildError('The plan must be a JSON object')
    unknown = set(plan) - PLAN_KEYS
    if unknown:
        raise BuildError(f'Unsupported top-level keys: {", ".join(sorted(unknown))}')
    return plan


def _initials(name):
    words = [w for w in re.split(r'[\s/_-]+', name.strip()) if w]
    letters = ''.join(w[0] for w in words[:2])
    return (letters or name.strip()[:2]).upper()


def _billing_dates(row_id, dates):
    if not isinstance(dates, dict):
        raise BuildError(f'{row_id}: dates must be an object')
    unknown = set(dates) - set(DATE_EVENTS)
    if unknown:
        raise BuildError(f'{row_id}: unsupported date events: {", ".join(sorted(unknown))}')
    built = {}
    for field in DATE_EVENTS:
        event = dates.get(field)
        if event is None:
            built[field] = {'date': None, 'status': 'unknown', 'note': UNKNOWN_NOTE, 'sources': []}
            continue
        if not isinstance(event, dict):
            raise BuildError(f'{row_id}: {field} must be an object')
        event = dict(event)
        # A date without an explicit status is a confirmed event; the plan marks
        # estimates and unscheduled renewals itself. Nothing is inferred from prose.
        event.setdefault('status', 'confirmed' if event.get('date') else 'unknown')
        event.setdefault('note', UNKNOWN_NOTE if event['status'] == 'unknown' else '')
        event.setdefault('sources', [])
        event.setdefault('date', None)
        built[field] = event
    return built


def _signals(row_id, signals):
    if not isinstance(signals, list):
        raise BuildError(f'{row_id}: signals must be an array')
    built = []
    for signal in signals:
        if not isinstance(signal, dict):
            raise BuildError(f'{row_id}: every signal must be an object')
        unknown = set(signal) - SIGNAL_KEYS
        if unknown:
            raise BuildError(f'{row_id}: unsupported signal keys: {", ".join(sorted(unknown))}')
        built.append({**{'related_service_ids': [], 'source_ids': []}, **signal})
    return built


def _cost(row_id, row, counted_allowed):
    cost = row.get('cost', {})
    if not isinstance(cost, dict):
        raise BuildError(f'{row_id}: cost must be an object')
    cost = dict(cost)
    if 'include_monthly' not in cost:
        # Opt in only where the renderer's own conditions already hold.
        cost['include_monthly'] = bool(
            counted_allowed and row.get('status') == 'observed'
            and cost.get('kind') == 'fixed_monthly' and cost.get('amount') is not None
            and cost.get('currency') and row.get('evidence'))
    return cost


def _row(row, counted_allowed, default_action):
    if not isinstance(row, dict):
        raise BuildError('Every service or case must be an object')
    row_id = row.get('id')
    if not isinstance(row_id, str) or not row_id.strip():
        raise BuildError('Every service or case needs a nonempty id')
    unknown = set(row) - ROW_KEYS
    if unknown:
        raise BuildError(f'{row_id}: unsupported keys: {", ".join(sorted(unknown))}')
    if not isinstance(row.get('name'), str) or not row['name'].strip():
        raise BuildError(f'{row_id}: needs a name')

    refund = row.get('refund')
    if refund is not None and not isinstance(refund, dict):
        raise BuildError(f'{row_id}: refund must be an object')
    if refund is not None:
        group = 'refund'
    elif isinstance(row.get('review_group'), str):
        group = row['review_group']
    elif isinstance(row.get('needs_action'), bool):
        group = 'other' if row['needs_action'] else 'none'
    else:
        group = 'other' if default_action else 'none'
    needs_action = row.get('needs_action', group != 'none')
    if needs_action != (group != 'none'):
        raise BuildError(f'{row_id}: needs_action contradicts the {group} review group')
    if group == 'refund' and refund is None:
        raise BuildError(f'{row_id}: a refund review group needs a refund basis')

    built = {
        'id': row_id,
        'name': row['name'],
        'initials': row.get('initials') or _initials(row['name']),
        'category': row.get('category', ''),
        'plan': row.get('plan'),
        'status': row.get('status'),
        'status_label': row.get('status_label', ''),
        'status_note': row.get('status_note', ''),
        'cost': _cost(row_id, row, counted_allowed),
        'billing_dates': _billing_dates(row_id, row.get('dates', {})),
        'needs_action': needs_action,
        'review_group': group,
        'review_signals': _signals(row_id, row.get('signals', [])),
        'issue': row.get('issue', {}),
        'action': row.get('action', {}),
        'evidence': row.get('evidence', []),
        'unknowns': row.get('unknowns', []),
        'drafts': row.get('drafts', []),
    }
    for optional in ('renewal', 'priority'):
        if optional in row:
            built[optional] = row[optional]
    if refund is not None:
        built['refund_review'] = {'missing_evidence': [], **refund}
    return built


def _monthly_cost(plan, rows, as_of):
    """Derive baseline items from each row so one amount is never stated twice."""
    items, unknowns = [], []
    for row in rows:
        entry = row.get('monthly')
        if entry is not None:
            if not isinstance(entry, dict):
                raise BuildError(f"{row['id']}: monthly must be an object")
            items.append({'service_id': row['id'], **entry})
        gap = row.get('cost_unknown')
        for note in ([gap] if isinstance(gap, str) else gap or []):
            unknowns.append({'service_id': row['id'], 'note': note})
    summary = plan.get('monthly_cost')
    if summary is None and not items and not unknowns:
        return None
    summary = dict(summary or {})
    if summary.pop('items', None) is not None or summary.pop('unknowns', None) is not None:
        raise BuildError('monthly_cost items and unknowns are derived from each row, not supplied')
    if not isinstance(summary.get('note'), str) or not summary['note'].strip():
        raise BuildError('monthly_cost needs a coverage note stating what the baseline excludes')
    if as_of is not None:
        summary.setdefault('as_of', as_of)
    return {**summary, 'items': items, 'unknowns': unknowns}


def _evidence(plan, report):
    """Attribute every declared source to the rows that cite it."""
    block = plan.get('evidence')
    if block is None:
        return None
    if not isinstance(block, dict):
        raise BuildError('evidence must be an object')
    searches = copy.deepcopy(block.get('searches', []))
    sources = copy.deepcopy(block.get('sources', []))
    if not isinstance(searches, list) or not isinstance(sources, list):
        raise BuildError('evidence searches and sources must be arrays')
    declared = {}
    for entry in searches + sources:
        if not isinstance(entry, dict) or not isinstance(entry.get('id'), str) or not entry['id'].strip():
            raise BuildError('Every evidence search and source needs a nonempty id')
        if entry['id'] in declared:
            raise BuildError(f"Duplicate evidence id {entry['id']}")
        declared[entry['id']] = entry
        entry.setdefault('service_ids', [])

    rows = plan.get('services', []) + plan.get('cases', [])
    cited = set()
    for row, built in zip(rows, report['subscriptions'] + report.get('other_cases', [])):
        refs = row.get('sources', [])
        if not isinstance(refs, list) or not all(isinstance(r, str) and r.strip() for r in refs):
            raise BuildError(f"{built['id']}: sources must be an array of evidence ids")
        for ref in refs:
            if ref not in declared:
                raise BuildError(f"{built['id']}: cites undeclared evidence id {ref}")
            cited.add(ref)
            if built['id'] not in declared[ref]['service_ids']:
                declared[ref]['service_ids'].append(built['id'])

    # Catch a report row that points at an evidence id the manifest never declares.
    # The coverage gate checks the manifest, never these display references.
    known = set(declared) | set(plan.get('extra_source_ids', []))
    for built in report['subscriptions'] + report.get('other_cases', []):
        referenced = [r for event in built['billing_dates'].values() for r in event['sources']]
        referenced += [r for signal in built['review_signals'] for r in signal['source_ids']]
        for item in report.get('monthly_cost', {}).get('items', []):
            if item['service_id'] == built['id']:
                referenced += item.get('sources', [])
        for ref in referenced:
            if ref not in known and not EXTERNAL.match(ref):
                raise BuildError(f"{built['id']}: references evidence id {ref}, which the manifest does not declare")

    orphans = [sid for sid, entry in declared.items() if not entry['service_ids']]
    if orphans:
        raise BuildError('Evidence is attributed to no row; add it to a row\'s sources or give it '
                         f'explicit service_ids: {", ".join(sorted(orphans))}')
    manifest = {'scope': block.get('scope'), 'searches': searches, 'sources': sources}
    if 'independent_review_file' in block:
        manifest['independent_review_file'] = block['independent_review_file']
    return manifest


def build(plan):
    services = plan.get('services', [])
    cases = plan.get('cases', [])
    if not isinstance(services, list) or not isinstance(cases, list):
        raise BuildError('services and cases must be arrays')
    report = dict(plan.get('report') or {})
    if 'subscriptions' in report or 'other_cases' in report:
        raise BuildError('Put rows in the plan\'s services and cases arrays, not in report')
    report['subscriptions'] = [_row(row, True, False) for row in services]
    report['other_cases'] = [_row(row, False, True) for row in cases]
    for row in cases:
        if row.get('monthly') is not None:
            raise BuildError(f"{row['id']}: only subscription rows contribute to the monthly baseline")
    monthly = _monthly_cost(plan, services, report.get('as_of'))
    if monthly is not None:
        report['monthly_cost'] = monthly
    manifest = _evidence(plan, report)
    # Validate against the renderer's own rules, on a copy so no computed field leaks out.
    spec = importlib.util.spec_from_file_location('audit_renderer', Path(__file__).with_name('render_dashboard.py'))
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    try:
        renderer.prepare(copy.deepcopy(report))
    except (ValueError, KeyError, TypeError) as exc:
        raise BuildError(f'The built report does not satisfy the dashboard contract: {exc}')
    return report, manifest


def build_files(input_path, output_dir, force=False):
    plan = _load(input_path)
    report, manifest = build(plan)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = {'dashboard.json': report}
    if manifest is not None:
        written['audit-evidence.json'] = manifest
    for name, data in written.items():
        target = out / name
        if target.exists() and not force:
            raise BuildError(f'{target} exists; pass --force to replace it')
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        target.chmod(0o600)
    return {'services': len(report['subscriptions']),
            'cases': len(report['other_cases']),
            'monthly_items': len(report.get('monthly_cost', {}).get('items', [])),
            'monthly_unknowns': len(report.get('monthly_cost', {}).get('unknowns', [])),
            'searches': len(manifest['searches']) if manifest else 0,
            'sources': len(manifest['sources']) if manifest else 0,
            'files': sorted(written)}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', required=True, help='Compact report plan JSON')
    parser.add_argument('--output-dir', required=True, help='Private working directory for the outputs')
    parser.add_argument('--force', action='store_true', help='Replace existing outputs')
    args = parser.parse_args()
    try:
        summary = build_files(args.input, args.output_dir, args.force)
    except (BuildError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    # Counts only; report contents stay in the private working directory.
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
