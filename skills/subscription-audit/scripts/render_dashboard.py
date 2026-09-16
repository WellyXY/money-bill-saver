#!/usr/bin/env python3
"""Render a private, self-contained subscription review from sourced JSON."""
import argparse
import base64
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re


def validate_date(value):
    if not isinstance(value, str):
        raise ValueError('Billing dates must be ISO dates or timezone-qualified timestamps')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        date.fromisoformat(value)
    elif re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})', value):
        datetime.fromisoformat(value.replace('Z', '+00:00'))
    else:
        raise ValueError('Use an ISO date, or a timestamp with an explicit timezone')


def prepare_billing_dates(service):
    dates = service.setdefault('billing_dates', {})
    if not isinstance(dates, dict):
        raise ValueError(f"{service['id']}: billing_dates must be an object")
    for field in ('last_invoice', 'last_charge', 'next_renewal'):
        event = dates.setdefault(field, {'date': None, 'status': 'unknown', 'note': 'Not established in the reviewed sources.', 'sources': []})
        if not isinstance(event, dict):
            raise ValueError(f"{service['id']}: {field} must be an object")
        allowed = {'confirmed', 'unknown'} if field != 'next_renewal' else {'confirmed', 'estimated', 'unknown', 'not_scheduled'}
        state = event.get('status')
        if state not in allowed:
            raise ValueError(f"{service['id']}: invalid {field} status")
        sources = event.get('sources', [])
        if not isinstance(sources, list) or not all(isinstance(s, str) and s.strip() for s in sources):
            raise ValueError(f"{service['id']}: {field} sources must be nonempty strings")
        if not isinstance(event.get('note'), str) or not event['note'].strip():
            raise ValueError(f"{service['id']}: {field} needs an evidence note")
        if state in {'confirmed', 'estimated'}:
            validate_date(event.get('date'))
            if not sources:
                raise ValueError(f"{service['id']}: dated billing events require source references")
        elif event.get('date') is not None:
            raise ValueError(f"{service['id']}: unknown or unscheduled events cannot have an event date")
        if state == 'not_scheduled' and not sources:
            raise ValueError(f"{service['id']}: unscheduled renewal needs source evidence")
        if 'qualifier' in event and (not isinstance(event['qualifier'], str) or not event['qualifier'].strip() or not sources):
            raise ValueError(f"{service['id']}: date qualifiers require text and source evidence")
        related = event.get('related_date')
        if related is not None:
            if not isinstance(related, dict) or not isinstance(related.get('label'), str) or not related['label'].strip() or not sources:
                raise ValueError(f"{service['id']}: related dates require a label and source evidence")
            validate_date(related.get('date'))


def prepare(report):
    if not isinstance(report, dict):
        raise ValueError('The report must be an object')
    services = report.get('subscriptions')
    if not isinstance(services, list):
        raise ValueError('subscriptions must be an array')
    ids = set()
    totals = {}
    included = []
    for service in services:
        if not isinstance(service, dict):
            raise ValueError('Every subscription must be an object')
        sid = service.get('id')
        if not isinstance(sid, str) or not sid or sid in ids:
            raise ValueError('Every subscription needs a unique nonempty id')
        ids.add(sid)
        if not isinstance(service.get('name'), str) or not service['name'].strip():
            raise ValueError(f'{sid}: require a service name')
        if service.get('status') not in {'observed', 'uncertain', 'user_reported', 'historical'}:
            raise ValueError(f'{sid}: invalid status')
        prepare_billing_dates(service)
        cost = service.get('cost', {})
        if not isinstance(cost, dict):
            raise ValueError(f'{sid}: cost must be an object')
        if 'include_monthly' in cost and not isinstance(cost['include_monthly'], bool):
            raise ValueError(f'{sid}: include_monthly must be a boolean')
        if cost.get('include_monthly'):
            if service.get('status') != 'observed' or cost.get('kind') != 'fixed_monthly':
                raise ValueError(f'{sid}: monthly totals require observed fixed monthly evidence')
            if not service.get('evidence'):
                raise ValueError(f'{sid}: a counted monthly cost needs evidence')
            currency = cost.get('currency')
            if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha() or not currency.isupper():
                raise ValueError(f'{sid}: require a three-letter currency')
            try:
                amount = Decimal(str(cost['amount']))
            except (KeyError, InvalidOperation):
                raise ValueError(f'{sid}: require a decimal amount')
            if not amount.is_finite() or amount < 0:
                raise ValueError(f'{sid}: invalid amount')
            totals[currency] = totals.get(currency, Decimal('0')) + amount
            included.append(service['name'])
    other_cases = report.get('other_cases', [])
    if not isinstance(other_cases, list):
        raise ValueError('other_cases must be an array')
    for case in other_cases:
        if not isinstance(case, dict) or not isinstance(case.get('id'), str) or not case['id'] or case['id'] in ids:
            raise ValueError('Other cases must have unique nonempty ids across the report')
        ids.add(case['id'])
    # Keep financial review separate from general account/renewal questions.
    # Legacy reports default to the other-issues queue, never to a refund claim.
    for row, default_action in [(s, False) for s in services] + [(c, True) for c in other_cases]:
        row.setdefault('needs_action', default_action)
        if not isinstance(row['needs_action'], bool):
            raise ValueError(f"{row['id']}: needs_action must be a boolean")
        row.setdefault('review_group', 'other' if row['needs_action'] else 'none')
        group = row['review_group']
        if group not in {'refund', 'other', 'none'}:
            raise ValueError(f"{row['id']}: invalid review_group")
        if (group == 'none') == row['needs_action']:
            raise ValueError(f"{row['id']}: review_group conflicts with needs_action")
        if group == 'refund':
            review = row.get('refund_review')
            if not isinstance(review, dict) or not row.get('evidence'):
                raise ValueError(f"{row['id']}: refund review requires a basis and evidence")
            for field in ('reason', 'amount_label'):
                if not isinstance(review.get(field), str) or not review[field].strip():
                    raise ValueError(f"{row['id']}: refund review requires {field}")
            if review.get('eligibility') not in {'unverified', 'policy_supported', 'goodwill', 'refund_pending'}:
                raise ValueError(f"{row['id']}: invalid refund eligibility state")
            missing = review.get('missing_evidence', [])
            if not isinstance(missing, list) or not all(isinstance(item, str) for item in missing):
                raise ValueError(f"{row['id']}: missing_evidence must be an array of strings")
    groups = Counter(row['review_group'] for row in services + other_cases)
    statuses = Counter(s.get('status', 'uncertain') for s in services)
    report['computed'] = {
        'service_count': len(services),
        'observed_count': statuses['observed'],
        'uncertain_count': statuses['uncertain'] + statuses['user_reported'],
        'action_count': sum(bool(s.get('needs_action')) for s in services),
        'refund_count': groups['refund'],
        'other_issue_count': groups['other'],
        'known_monthly': {c: format(v, '.2f') for c, v in sorted(totals.items())},
        'monthly_includes': included,
    }
    return report


def render(report):
    report = prepare(report)
    template = Path(__file__).resolve().parents[1] / 'assets' / 'dashboard.html'
    serialized = json.dumps(report, ensure_ascii=False, allow_nan=False)
    # JSON lives in an inert script element; escape HTML delimiters and JS separators.
    serialized = serialized.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    font = template.parent / 'fonts' / 'Manrope-Variable.ttf'
    # Embed the licensed local font so opening a private report makes no font request.
    page = template.read_text(encoding='utf-8').replace('__FONT_DATA__', base64.b64encode(font.read_bytes()).decode('ascii'))
    return page.replace('__REPORT_DATA__', serialized)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()
    if args.output.exists() and not args.force:
        parser.error('Output exists; use --force to replace it')
    try:
        page = render(json.loads(args.input.read_text(encoding='utf-8')))
    except (ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding='utf-8')
    args.output.chmod(0o600)
    print(f'Wrote self-contained HTML: {args.output}')


if __name__ == '__main__':
    main()
