#!/usr/bin/env python3
"""Validate v0.1 facts and reconcile documented invoice amounts, using only stdlib.

No network, merchant interpretation, payment detection, or prose generation.
Arithmetic reconciliation does not establish correct pricing or successful payment.
Totals exclude incomplete, mismatched, conflicting, identity-unknown, and mixed
usage-basis records; exclusion reasons and counts are explicit. Sources are never
dereferenced. Existing output requires --force; input is never overwritten.
"""

import argparse
from collections import Counter
from copy import deepcopy
from datetime import date
from decimal import Decimal, localcontext
import json
from pathlib import Path
import re
import sys


VERSION = "0.1"
SOURCE_TYPES = {"pdf", "email", "usage", "policy", "user_statement", "receipt", "other"}
KINDS = {"base", "usage_gross", "usage_overage", "seat", "tax", "discount",
         "included_usage", "credit_applied", "carry_forward", "other"}
MONEY = re.compile(r"[+-]?\d+(?:\.\d+)?", re.ASCII)
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)


class FactsError(ValueError):
    """Input fails the facts contract."""


def require(condition, path, message):
    if not condition:
        raise FactsError(f"{path}: {message}")


def nonempty(value, path, nullable=False):
    if nullable and value is None:
        return
    require(isinstance(value, str) and bool(value.strip()), path, "expected nonempty string")


def check_date(value, path):
    if value is None:
        return
    require(isinstance(value, str) and ISO_DATE.fullmatch(value), path, "expected ISO date or null")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise FactsError(f"{path}: invalid calendar date") from exc


def check_period(value, path):
    require(isinstance(value, dict), path, "expected object")
    for key in ("start", "end"):
        require(key in value, path, f"missing {key}")
        check_date(value[key], f"{path}.{key}")
    if value["start"] is not None and value["end"] is not None:
        require(value["end"] > value["start"], path, "end must follow start")


def check_money(value, path):
    require(value is None or (isinstance(value, str) and MONEY.fullmatch(value)),
            path, "expected decimal string or null (no floats, exponents or separators)")


def check_refs(value, path, sources):
    require(isinstance(value, list) and bool(value), path, "expected nonempty source list")
    for index, ref in enumerate(value):
        nonempty(ref, f"{path}[{index}]")
        require(ref in sources, path, f"unknown source reference {ref!r}")


def validate(data):
    require(isinstance(data, dict), "$", "expected object")
    for key in ("schema_version", "scope", "sources", "invoices"):
        require(key in data, "$", f"missing {key}")
    require(data["schema_version"] == VERSION, "schema_version", "supported version is 0.1")
    scope = data["scope"]
    require(isinstance(scope, dict), "scope", "expected object")
    for key in ("start", "end"):
        if key in scope:
            check_date(scope[key], f"scope.{key}")
    if scope.get("start") is not None and scope.get("end") is not None:
        require(scope["end"] > scope["start"], "scope", "end must follow start")
    require(isinstance(data["sources"], list), "sources", "expected array")
    source_ids = set()
    for index, source in enumerate(data["sources"]):
        path = f"sources[{index}]"
        require(isinstance(source, dict), path, "expected object")
        for key in ("id", "type", "locator"):
            nonempty(source.get(key), f"{path}.{key}")
        require(source["id"] not in source_ids, path, "duplicate source id")
        require(source["type"] in SOURCE_TYPES, path, "unknown source type")
        source_ids.add(source["id"])
    require(isinstance(data["invoices"], list), "invoices", "expected array")
    record_ids = set()
    fields = ("record_id", "vendor", "account_ref", "invoice_ref", "subscription_ref",
              "issued_on", "currency", "amount_due", "line_items_complete", "source_refs", "line_items")
    for index, inv in enumerate(data["invoices"]):
        path = f"invoices[{index}]"
        require(isinstance(inv, dict), path, "expected object")
        for key in fields:
            require(key in inv, path, f"missing {key}")
        for key in ("record_id", "vendor"):
            nonempty(inv[key], f"{path}.{key}")
        require(inv["record_id"] not in record_ids, path, "duplicate record id")
        record_ids.add(inv["record_id"])
        for key in ("account_ref", "invoice_ref", "subscription_ref"):
            nonempty(inv[key], f"{path}.{key}", nullable=True)
        check_date(inv["issued_on"], f"{path}.issued_on")
        require(isinstance(inv["currency"], str) and re.fullmatch(r"[A-Z]{3}", inv["currency"]),
                f"{path}.currency", "expected three uppercase letters")
        check_money(inv["amount_due"], f"{path}.amount_due")
        require(type(inv["line_items_complete"]) is bool, path, "line_items_complete must be boolean")
        check_refs(inv["source_refs"], f"{path}.source_refs", source_ids)
        require(isinstance(inv["line_items"], list), f"{path}.line_items", "expected array")
        for n, line in enumerate(inv["line_items"]):
            lp = f"{path}.line_items[{n}]"
            require(isinstance(line, dict), lp, "expected object")
            nonempty(line.get("label"), f"{lp}.label")
            require(isinstance(line.get("kind"), str) and line["kind"] in KINDS, lp, "unknown line kind")
            require("amount" in line, lp, "missing amount")
            check_money(line["amount"], f"{lp}.amount")
            if "period" in line:
                check_period(line["period"], f"{lp}.period")
            if "source_refs" in line:
                check_refs(line["source_refs"], f"{lp}.source_refs", source_ids)
        if "subscription" in inv:
            sub = inv["subscription"]
            require(isinstance(sub, dict), f"{path}.subscription", "expected object")
            options = {
                "cycle": {"monthly", "quarterly", "annual", "usage", "one_time", "unknown"},
                "activity": {"active", "inactive_confirmed", "unknown"},
                "dependency": {"critical", "noncritical_confirmed", "unknown"},
            }
            for key, allowed in options.items():
                if key in sub:
                    require(isinstance(sub[key], str) and sub[key] in allowed,
                            f"{path}.subscription.{key}", "unknown value")
            if "recurring" in sub:
                require(sub["recurring"] is None or type(sub["recurring"]) is bool,
                        f"{path}.subscription.recurring", "expected boolean or null")
            if "renews_on" in sub:
                check_date(sub["renews_on"], f"{path}.subscription.renews_on")
            for key in ("plan", "owner"):
                if key in sub:
                    nonempty(sub[key], f"{path}.subscription.{key}", nullable=True)


def canonical_money(value):
    if value is None:
        return None
    number = Decimal(value)
    if number == 0:
        return "0"
    text = format(number, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def line_key(line):
    period = line.get("period", {})
    return (line["label"], line["kind"], canonical_money(line["amount"]),
            period.get("start"), period.get("end"))


def accounting_key(inv):
    # Source ordering, printed decimal precision and line order do not alter amounts.
    return (inv["currency"], canonical_money(inv["amount_due"]), inv["line_items_complete"],
            frozenset(Counter(line_key(line) for line in inv["line_items"]).items()))


def exact_sum(values):
    numbers = [Decimal(value) for value in values]
    if not numbers:
        return None
    # Enough precision for every supplied digit, the full decimal span, and carries.
    integers = max(max(number.adjusted() + 1, 1) for number in numbers)
    fractions = max(max(-number.as_tuple().exponent, 0) for number in numbers)
    with localcontext() as context:
        context.prec = max(64, integers + fractions + len(str(len(numbers))) + 4)
        return sum(numbers, Decimal(0))


def assess(inv):
    warnings = []
    known = [line["amount"] for line in inv["line_items"] if line["amount"] is not None]
    known_sum = exact_sum(known)
    due = inv["amount_due"]
    delta = exact_sum([due, format(known_sum.copy_negate(), "f")]) if due is not None and known_sum is not None else None
    if not inv["line_items_complete"]:
        warnings.append("incomplete_line_items")
    if len(known) != len(inv["line_items"]):
        warnings.append("unknown_line_amount")
    if not inv["line_items"]:
        warnings.append("no_line_items")
    if due is None:
        warnings.append("unknown_amount_due")
    kinds = {line["kind"] for line in inv["line_items"]}
    if {"usage_overage", "included_usage"} <= kinds:
        warnings.append("possible_included_usage_double_credit")
    if {"usage_gross", "usage_overage"} <= kinds:
        warnings.append("mixed_usage_basis")
    if inv["account_ref"] is None or inv["invoice_ref"] is None:
        warnings.append("invoice_identity_unknown")
    sub = inv.get("subscription", {})
    confirmed_one_time = sub.get("cycle") == "one_time" and sub.get("recurring") is False
    if inv["subscription_ref"] is None and not confirmed_one_time:
        warnings.append("subscription_identity_unknown")
    incomplete = any(w in warnings for w in ("incomplete_line_items", "unknown_line_amount", "no_line_items", "unknown_amount_due"))
    status = "incomplete" if incomplete else ("reconciled" if delta == 0 else "mismatch")
    return {"status": status, "known_sum": format(known_sum, "f") if known_sum is not None else None,
            "amount_due": due, "delta": format(delta, "f") if delta is not None else None,
            "delta_meaning": "unexplained_residual" if incomplete else "arithmetic_difference",
            "known_line_count": len(known), "warnings": warnings}


def all_source_refs(group):
    refs = {ref for inv in group for ref in inv["source_refs"]}
    refs.update(ref for inv in group for line in inv["line_items"] for ref in line.get("source_refs", []))
    return sorted(refs)


def merge_sources(group):
    merged = deepcopy(group[0])
    merged["source_refs"] = all_source_refs(group)
    # Preserve each original line occurrence and its evidence, including service periods.
    by_key = {}
    for inv in group:
        occurrences = Counter()
        for line in inv["line_items"]:
            key = line_key(line)
            occurrence = occurrences[key]
            occurrences[key] += 1
            by_key.setdefault((key, occurrence), set()).update(line.get("source_refs", inv["source_refs"]))
    occurrences = Counter()
    for line in merged["line_items"]:
        key = line_key(line)
        occurrence = occurrences[key]
        occurrences[key] += 1
        line["source_refs"] = sorted(by_key[(key, occurrence)])
    for key in ("issued_on", "subscription_ref"):
        known = {inv[key] for inv in group if inv[key] is not None}
        if len(known) == 1:
            merged[key] = next(iter(known))
    return merged


def check_facts(data):
    validate(data)
    groups = {}
    for inv in data["invoices"]:
        identity = (inv["vendor"], inv["account_ref"], inv["invoice_ref"])
        key = ("known",) + identity if None not in identity else ("unknown", inv["record_id"])
        groups.setdefault(key, []).append(inv)
    results = []
    due_values = {}
    exclusions = Counter()
    for group in groups.values():
        first = group[0]
        result = {key: first[key] for key in ("vendor", "account_ref", "invoice_ref", "currency")}
        result["record_ids"] = [inv["record_id"] for inv in group]
        result["source_refs"] = all_source_refs(group)
        conflicting = len({accounting_key(inv) for inv in group}) > 1
        for key in ("issued_on", "subscription_ref"):
            conflicting |= len({inv[key] for inv in group if inv[key] is not None}) > 1
        if conflicting:
            result.update(status="identity_conflict", known_sum=None, amount_due=None, delta=None,
                          delta_meaning="unresolved_observations", warnings=["inconsistent_invoice_observations"])
            result["observations"] = [{"invoice": deepcopy(inv), "check": assess(inv)} for inv in group]
            reasons = ["identity_conflict"]
        else:
            merged = merge_sources(group)
            result.update(assess(merged))
            for key in ("subscription_ref", "issued_on", "line_items_complete", "line_items"):
                result[key] = merged[key]
            if any("subscription" in inv for inv in group):
                result["subscription_observations"] = [{"record_id": inv["record_id"], "source_refs": deepcopy(inv["source_refs"]), "subscription": deepcopy(inv["subscription"])} for inv in group if "subscription" in inv]
            reasons = [] if result["status"] == "reconciled" else [result["status"]]
            reasons.extend(w for w in result["warnings"] if w in {"invoice_identity_unknown", "possible_included_usage_double_credit", "mixed_usage_basis"})
        result["included_in_documented_due"] = not reasons
        result["excluded_reasons"] = reasons
        exclusions.update(reasons)
        if not reasons:
            due_values.setdefault(result["currency"], []).append(result["amount_due"])
        results.append(result)
    return {
        "schema_version": VERSION,
        "scope": deepcopy(data["scope"]),
        "sources": deepcopy(data["sources"]),
        "invoices": results,
        "documented_due": [{"currency": currency, "amount": format(exact_sum(values), "f"),
                            "invoice_count": len(values)} for currency, values in sorted(due_values.items())],
        "counts": {"input_observations": len(data["invoices"]), "unique_records": len(results),
                   "included_records": sum(item["included_in_documented_due"] for item in results),
                   "excluded_records": sum(not item["included_in_documented_due"] for item in results),
                   "status": dict(sorted(Counter(item["status"] for item in results).items())),
                   "exclusion_reasons": dict(sorted(exclusions.items()))},
        "meaning": "Documented amount due only; not proof of payment, correct pricing, refunds, or savings. Unknown identity and mixed usage basis are excluded even when arithmetic reconciles.",
    }


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "JSON", f"duplicate object key {key!r}")
        result[key] = value
    return result


def reject_constant(value):
    raise FactsError(f"JSON: non-finite number {value} is not allowed")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Local facts.json conforming to v0.1")
    parser.add_argument("--output", required=True, type=Path, help="Local checks.json; existing files are preserved")
    parser.add_argument("--force", action="store_true", help="Explicitly replace an existing output file")
    args = parser.parse_args(argv)
    try:
        require(args.input.resolve() != args.output.resolve(), "output", "must differ from input")
        if args.input.exists() and args.output.exists():
            require(not args.input.samefile(args.output), "output", "must not be a hard link to input")
        with args.input.open(encoding="utf-8") as stream:
            data = json.load(stream, object_pairs_hook=unique_object, parse_constant=reject_constant)
        result = check_facts(data)
        with args.output.open("w" if args.force else "x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    except (FactsError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"check_facts: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
