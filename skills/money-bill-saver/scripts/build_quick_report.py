#!/usr/bin/env python3
"""Build the fixed private webpage from a small, sourced quick-1 decision file.

This is the fast, focused path. It does not inspect the mailbox, verify source
contents, reconcile invoice lines, or certify an independent review.
"""
import argparse
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo


def module(name):
    spec = importlib.util.spec_from_file_location("quick_report_" + name, Path(__file__).with_name(name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


renderer = module("render_dashboard")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def nonempty(value, field):
    require(isinstance(value, str) and bool(value.strip()), f"{field} needs text")
    return value


def public_account_url(value, field):
    """Keep quick action links on public HTTPS hosts and static account paths."""
    nonempty(value, field)
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{field} must be a public HTTPS homepage") from exc
    require(parsed.scheme == "https" and hostname and parsed.netloc.lower() == hostname.lower() and port is None and
            parsed.username is None and parsed.password is None and
            not parsed.query and not parsed.fragment and
            "\\" not in value and not any(char.isspace() for char in value),
            f"{field} must be a public HTTPS account URL without credentials, query or fragment")
    labels = hostname.split(".")
    require(len(hostname) <= 253 and len(labels) >= 2 and all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
        for label in labels) and re.fullmatch(r"[A-Za-z]{2,}|xn--[A-Za-z0-9-]{2,}", labels[-1]) and
        labels[-1].lower() not in {"local", "internal", "test", "invalid"},
        f"{field} needs a public domain name")
    static_segments = {"account", "accounts", "youraccount", "login", "signin", "sign-in",
                       "billing", "settings", "subscription",
                       "subscriptions", "manage-subscription", "plan", "plans", "manage-plan", "payment",
                       "payments", "invoices", "invoice", "receipts", "receipt", "profile", "manage",
                       "manage-account", "dashboard", "home", "user", "users", "me", "my", "membership",
                       "memberships", "portal", "console", "overview", "preferences", "purchases", "orders",
                       "payments-and-subscriptions", "support", "help"}
    path = parsed.path.strip("/")
    segments = path.split("/") if path else []
    require(len(segments) <= 4 and all(segment.lower() in static_segments for segment in segments),
            f"{field} must use a stable public account/billing path without private IDs")
    return f"https://{hostname.lower()}{parsed.path or '/'}"


def action_link(value, field):
    require(isinstance(value, dict) and set(value) <= {"url", "link_label"},
            f"{field} must contain only url and optional link_label")
    url = public_account_url(value.get("url"), field + ".url")
    label = value.get("link_label", "Likely account entry — confirm after sign-in")
    return {"url": url, "link_label": nonempty(label, field + ".link_label")}


def refs(value, sources, field, needed=False):
    require(isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value),
            f"{field} must be a list of source IDs")
    require(not needed or value, f"{field} needs a source ID")
    require(len(value) == len(set(value)), f"{field} repeats a source ID")
    for sid in value:
        require(sid in sources, f"{field} refers to an unknown source: {sid}")
    return value


def safe_local(root, relative):
    nonempty(relative, "source_index")
    path = Path(relative)
    require(not path.is_absolute() and ".." not in path.parts and "\\" not in relative,
            "source_index must be relative and cannot traverse parent directories")
    target = (root / path).resolve()
    require(target.is_relative_to(root.resolve()) and target.is_file(), "source_index must be inside the private bundle")
    return target


def source_lookup(data, bundle):
    rows = deepcopy(data.get("sources", []))
    if data.get("source_index"):
        saved = json.loads(safe_local(bundle, data["source_index"]).read_text(encoding="utf-8"))
        require(isinstance(saved, dict), "source_index must contain an object")
        if "messages" in saved:
            rows.extend(source for message in saved["messages"] for source in message["evidence_sources"])
        else:
            rows.extend(saved.get("sources", []))
    require(isinstance(rows, list), "sources must be a list")
    found = {}
    for source in rows:
        require(isinstance(source, dict), "Every source needs an object")
        sid = nonempty(source.get("id"), "source.id")
        require(sid not in found, f"Duplicate source ID: {sid}")
        found[sid] = source
    return found


def as_date(value, as_of, zone, field, future=False):
    renderer.validate_date(value)
    day = (value if len(value) == 10 else
           datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(zone).date().isoformat())
    require(future or day <= as_of, f"{field} is after the report date")
    return value, day


def billing_dates(values, sources, as_of, zone):
    require(isinstance(values, dict), "dates must be an object")
    result = {}
    defaults = {"last_invoice": "No invoice issue date established.",
                "last_charge": "No successful cash charge date established.",
                "next_renewal": "No current explicit renewal schedule established."}
    for field, missing_note in defaults.items():
        item = values.get(field)
        if item is None:
            result[field] = {"date": None, "status": "unknown", "note": missing_note, "sources": []}
            continue
        require(isinstance(item, dict), f"dates.{field} must be an object")
        source_refs = refs(item.get("source_refs"), sources, f"dates.{field}.source_refs", True)
        if field == "next_renewal" and item.get("disabled") is True:
            require("date" not in item, "A disabled renewal cannot have a renewal date")
            result[field] = {"date": None, "status": "not_scheduled",
                             "note": nonempty(item.get("note"), "disabled renewal note"), "sources": source_refs}
            continue
        require(item.get("disabled") is not True, "disabled is valid only for next_renewal")
        date_value, local_day = as_date(item.get("date"), as_of, zone, f"dates.{field}", field == "next_renewal")
        if field == "next_renewal":
            require(local_day >= as_of, "A past schedule cannot establish the next renewal")
        note = item.get("note") or {"last_invoice": "Invoice issue date stated in the cited source; this does not establish payment.",
                                   "last_charge": "Successful cash charge stated in the cited payment evidence.",
                                   "next_renewal": "Future renewal date explicitly stated in the cited source."}[field]
        result[field] = {"date": date_value, "status": "confirmed", "note": nonempty(note, field + " note"),
                         "sources": source_refs}
    return result


def cost_fields(cost, entity, sources):
    require(isinstance(cost, dict), "cost must be an object")
    include = cost.get("include_monthly", False)
    require(type(include) is bool, "cost.include_monthly must be a boolean")
    kind = cost.get("kind", "unknown")
    require(kind in {"unknown", "fixed_monthly", "fixed_term", "base_plus_usage", "prepaid", "variable", "invoice_total"},
            "Unknown cost kind")
    source_refs = refs(cost.get("source_refs", []), sources, "cost.source_refs", "amount" in cost or include)
    if "amount" in cost:
        amount = cost["amount"]
        require(isinstance(amount, str) and re.fullmatch(r"\d+(?:\.\d+)?", amount, flags=re.ASCII),
                "cost.amount must be a nonnegative decimal string")
        Decimal(amount)
        require(isinstance(cost.get("currency"), str) and re.fullmatch(r"[A-Z]{3}", cost["currency"]),
                "cost.currency must be an uppercase three-letter code")
    else:
        require("currency" not in cost, "Cost currency without amount")
    if include:
        require(entity["kind"] == "service" and entity["status"] == "observed", "Only observed current services enter monthly totals")
        require(kind in {"fixed_monthly", "fixed_term", "base_plus_usage"} and "amount" in cost,
                "Monthly inclusion requires a sourced recurring amount")
        months = cost.get("months", 1 if kind in {"fixed_monthly", "base_plus_usage"} else None)
        require(type(months) is int and months > 0, "cost.months must be a positive integer")
        basis = nonempty(cost.get("basis"), "cost.basis")
        monthly = {"service_id": entity["id"], "amount": cost["amount"], "currency": cost["currency"],
                   "months": months, "basis": basis, "sources": source_refs}
    else:
        monthly = None
    label = cost.get("label")
    if label is None:
        label = (f"{cost['currency']} {cost['amount']} / {monthly['months']} month(s)" if monthly else
                 f"{cost['currency']} {cost['amount']} observed" if "amount" in cost else "Amount unknown")
    note = cost.get("note") or cost.get("basis") or "Current recurring cost has not been established."
    output = {"kind": {"base_plus_usage": "monthly_base_plus_usage", "prepaid": "per_top_up"}.get(kind, kind),
              "label": nonempty(label, "cost.label"), "note": nonempty(note, "cost.note"), "include_monthly": False}
    if monthly and kind == "fixed_monthly" and monthly["months"] == 1:
        output.update(include_monthly=True, amount=cost["amount"], currency=cost["currency"])
    gaps = []
    if entity["kind"] == "service" and not monthly:
        gaps.append({"service_id": entity["id"], "note": cost.get("unknown_note") or "Current monthly cost is not established."})
    elif cost.get("unknown_note"):
        gaps.append({"service_id": entity["id"], "note": cost["unknown_note"]})
    return output, monthly, gaps


def compile_issue(issue, row, sources):
    if issue is None:
        row.update(review_group="none", needs_action=False,
                   issue={"title": "No specific issue established", "summary": row["status_note"]},
                   action={"summary": "No action proposed from the available evidence.", "steps": []})
        return
    require(isinstance(issue, dict), "issue must be an object")
    group = issue.get("group")
    require(group in {"refund", "other"}, "issue.group must be refund or other")
    issue_refs = refs(issue.get("source_refs"), sources, "issue.source_refs", True)
    row["source_refs"] = list(dict.fromkeys(row["source_refs"] + issue_refs))
    summary = nonempty(issue.get("summary"), "issue.summary")
    row.update(review_group=group, needs_action=True,
               issue={"title": nonempty(issue.get("title"), "issue.title"), "summary": summary},
               action={"summary": nonempty(issue.get("next"), "issue.next"), "steps": []})
    if group == "refund":
        row["refund_review"] = {"reason": summary,
                                "amount_label": nonempty(issue.get("amount_label"), "issue.amount_label"),
                                "eligibility": issue.get("eligibility", "unverified"),
                                "missing_evidence": issue.get("missing", [])}
        require(row["refund_review"]["eligibility"] in {"unverified", "policy_supported", "goodwill", "refund_pending"},
                "Invalid refund eligibility")
        require(isinstance(row["refund_review"]["missing_evidence"], list), "issue.missing must be a list")


def compile_row(entity, kind, sources, as_of, zone):
    require(isinstance(entity, dict), "Every service or case needs an object")
    sid = nonempty(entity.get("id"), "entity.id")
    name = nonempty(entity.get("name"), sid + ".name")
    vendor = nonempty(entity.get("vendor"), sid + ".vendor")
    require("account_ref" in entity, sid + ".account_ref must be explicit, null when unknown")
    account_ref = entity["account_ref"]
    require(account_ref is None or isinstance(account_ref, str) and account_ref.strip(), sid + ".account_ref is invalid")
    status = entity.get("status")
    require(status in {"observed", "uncertain", "user_reported", "historical"}, sid + ".status is invalid")
    source_refs = refs(entity.get("source_refs", []), sources, sid + ".source_refs", status == "observed")
    alias = entity.get("account_alias") or account_ref or "account unknown: " + sid
    note = nonempty(entity.get("status_note"), sid + ".status_note")
    row = {"id": sid, "name": name + " · " + alias, "category": entity.get("category", "Service" if kind == "service" else "Billing case"),
           "account_ref": account_ref, "vendor": vendor, "status": status,
           "status_label": entity.get("status_label") or {"observed": "Observed service evidence", "uncertain": "Current status uncertain",
                                                       "user_reported": "User reported", "historical": "Historical"}[status],
           "status_note": note, "source_refs": source_refs, "unknowns": entity.get("unknowns", []),
           "drafts": [], "review_signals": [], "priority": entity.get("priority", False)}
    require(isinstance(row["unknowns"], list) and all(isinstance(v, str) and v.strip() for v in row["unknowns"]),
            sid + ".unknowns must be a list of text")
    require(type(row["priority"]) is bool, sid + ".priority must be boolean")
    if entity.get("plan"):
        row["plan"] = nonempty(entity["plan"], sid + ".plan")
    row["billing_dates"] = billing_dates(entity.get("dates", {}), sources, as_of, zone)
    cost, monthly, gaps = cost_fields(entity.get("cost", {}), {**entity, "kind": kind}, sources)
    row["cost"] = cost
    compile_issue(entity.get("issue"), row, sources)
    if "action" in entity:
        row["action"].update(action_link(entity["action"], sid + ".action"))
        if entity.get("issue") is None:
            row["action"]["summary"] = "Use this likely official entry to check the current account status, if needed."
    for draft in entity.get("drafts", []):
        require(isinstance(draft, dict), "drafts must be objects")
        draft_refs = refs(draft.get("source_refs"), sources, "draft.source_refs", True)
        row["drafts"].append({"title": nonempty(draft.get("title"), "draft.title"),
                              "condition": nonempty(draft.get("condition"), "draft.condition"),
                              "text": nonempty(draft.get("text"), "draft.text"), "source_refs": draft_refs})
    used = list(dict.fromkeys(row["source_refs"] +
                              [ref for event in row["billing_dates"].values() for ref in event["sources"]] +
                              entity.get("cost", {}).get("source_refs", []) +
                              [ref for draft in row["drafts"] for ref in draft["source_refs"]]))
    row["evidence"] = []
    for source_id in used:
        source = sources[source_id]
        entry = {"id": source_id, "source_refs": [source_id], "label": source.get("label") or source_id,
                 "date": source.get("date"), "note": source.get("note") or "Cited source."}
        if source.get("url"):
            entry["url"] = source["url"]
        row["evidence"].append(entry)
    return row, monthly, gaps


def build(data, bundle):
    require(isinstance(data, dict) and data.get("schema_version") == "quick-1", "Expected schema_version quick-1")
    as_of = data.get("as_of")
    require(isinstance(as_of, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of), "as_of must be an ISO date")
    date.fromisoformat(as_of)
    scope = data.get("scope")
    require(isinstance(scope, dict), "scope must be an object")
    description = nonempty(scope.get("description"), "scope.description")
    try:
        zone = ZoneInfo(scope.get("timezone", "UTC"))
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError("scope.timezone must be a valid IANA timezone") from exc
    limitations = scope.get("limitations", [])
    require(isinstance(limitations, list) and all(isinstance(v, str) and v.strip() for v in limitations),
            "scope.limitations must be a list of text")
    sources = source_lookup(data, bundle)
    services = data.get("services", [])
    cases = data.get("cases", [])
    require(isinstance(services, list) and isinstance(cases, list), "services and cases must be lists")
    report = {"report_mode": "focused", "as_of": as_of,
              "title": data.get("title") or "Bills, subscriptions and open questions",
              "intro": data.get("intro") or description,
              "status_boundary": description, "coverage": {"summary": description, "notes": limitations},
              "footer_note": "Focused review of selected billing evidence. Unknowns are not zero.",
              "subscriptions": [], "other_cases": [], "appendix": [],
              "monthly_cost": {"as_of": as_of, "items": [], "unknowns": [],
                               "note": "Partial estimate from explicitly sourced current recurring prices. Usage and unknown costs are excluded."}}
    seen = set()
    for kind, inputs, target in (("service", services, "subscriptions"), ("case", cases, "other_cases")):
        for entity in inputs:
            require(kind != "case" or not entity.get("overlap"), "Functional overlap belongs on a service row")
            row, monthly, gaps = compile_row(entity, kind, sources, as_of, zone)
            require(row["id"] not in seen, "Duplicate service/case ID: " + row["id"])
            seen.add(row["id"])
            require(kind != "case" or row["needs_action"], "Non-actionable cases belong in appendix")
            report[target].append(row)
            if monthly:
                report["monthly_cost"]["items"].append(monthly)
            report["monthly_cost"]["unknowns"].extend(gaps)
    service_names = {entity["id"]: entity["name"] for entity in services}
    for entity, row in zip(services, report["subscriptions"]):
        overlaps = entity.get("overlap", [])
        require(isinstance(overlaps, list), row["id"] + ".overlap must be a list")
        for item in overlaps:
            require(isinstance(item, dict) and set(item) <=
                    {"peer_ids", "reason", "next_check", "tentative_keep_id", "source_refs"},
                    row["id"] + ".overlap entries have unsupported fields")
            peers = item.get("peer_ids")
            require(isinstance(peers, list) and peers and all(isinstance(peer, str) for peer in peers) and
                    len(peers) == len(set(peers)) and all(peer in service_names and peer != row["id"] for peer in peers),
                    row["id"] + ".overlap.peer_ids must name other listed services")
            reason = nonempty(item.get("reason"), row["id"] + ".overlap.reason")
            next_check = nonempty(item.get("next_check"), row["id"] + ".overlap.next_check")
            keep = item.get("tentative_keep_id")
            require(keep is None or keep in [row["id"], *peers],
                    row["id"] + ".overlap.tentative_keep_id must name a compared service")
            source_ids = refs(item.get("source_refs", []), sources,
                              row["id"] + ".overlap.source_refs")
            compared = [service_names[row["id"]], *(service_names[peer] for peer in peers)]
            title = (f"Tentatively keep {service_names[keep]}" if keep else
                     "Consider keeping only one: " + " / ".join(compared))
            if keep:
                reason += (f" Tentative keep-one option: retain {service_names[keep]} and consider dropping "
                           + ", ".join(service_names[sid] for sid in [row["id"], *peers] if sid != keep)
                           + " after checking use and dependencies.")
            evidence_note = ("Possible functional overlap in this focused review. Cited sources provide context, "
                             "not proof of overlap. Actual use, current paid status, required features and "
                             "cancellation effects have not been verified." if source_ids else
                             "Possible functional overlap from a tentative feature comparison. No source is cited "
                             "for this lead; actual use, current paid status, required features and cancellation "
                             "effects have not been verified.")
            row["review_signals"].append({"type": "functional_overlap", "title": title,
                                          "reason": reason, "evidence_note": evidence_note,
                                          "next_check": next_check, "related_service_ids": peers,
                                          "source_ids": source_ids})
    for item in data.get("appendix", []):
        require(isinstance(item, dict), "appendix entries must be objects")
        appendix_refs = refs(item.get("source_refs"), sources, "appendix.source_refs", True)
        report["appendix"].append({"name": nonempty(item.get("name"), "appendix.name"),
                                   "category": item.get("category") or "One-time / non-actionable",
                                   "note": nonempty(item.get("note"), "appendix.note"),
                                   "source_refs": appendix_refs})
    return renderer.prepare(report)


def run(input_path, output_dir, force=False):
    source, root = Path(input_path).resolve(), Path(output_dir).resolve()
    require(source.is_relative_to(root), "Keep quick.json and source_index inside the private output directory")
    data = json.loads(source.read_text(encoding="utf-8"))
    protected = {source}
    if data.get("source_index"):
        protected.add(safe_local(root, data["source_index"]))
    for filename in ("dashboard.json", "dashboard.html"):
        target = root / filename
        require(target.resolve() not in protected, "Refusing to overwrite quick input or source index")
        require(not target.is_symlink(), "Report output must not be a symbolic link")
        require(force or not target.exists(), "Output exists: " + filename + "; use --force")
    report = build(data, root)
    html = renderer.render(report)
    (root / "dashboard.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (root / "dashboard.html").write_text(html, encoding="utf-8")
    (root / "dashboard.json").chmod(0o600)
    (root / "dashboard.html").chmod(0o600)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        report = run(args.input, args.output_dir, args.force)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"report_mode": report["report_mode"], "services": len(report["subscriptions"]),
                      "refund_questions": report["computed"]["refund_count"],
                      "other_issues": report["computed"]["other_issue_count"],
                      "output": str((args.output_dir / "dashboard.html").resolve())}))


if __name__ == "__main__":
    main()
