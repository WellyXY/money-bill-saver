#!/usr/bin/env python3
"""Build a private report from audit-1 observations and explicit human/agent decisions.

No network, mail reading, usage inference, policy inference or review certification.
Run the existing final renderer with --require-checked after independent review.
"""
import argparse
from copy import deepcopy
from datetime import date, datetime, time, timezone
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo


VERSION = "audit-1"
EVENT_TYPES = {
    "payment_succeeded", "payment_failed", "refund_received", "credit_granted",
    "credit_used", "fee_waived", "benefit_restored", "service_extended",
    "subscription_cancelled", "subscription_reactivated", "renewal_scheduled",
    "renewal_disabled", "service_period", "trial_started", "trial_ended",
    "plan_changed", "usage_observed", "user_statement",
}
LIFECYCLE = {"subscription_cancelled", "subscription_reactivated", "plan_changed",
             "renewal_scheduled", "renewal_disabled", "trial_started", "trial_ended"}
OUTCOMES = {"refund_received": "cash_refund", "credit_granted": "credit_granted",
            "credit_used": "credit_used", "fee_waived": "liability_waived",
            "benefit_restored": "benefit_restored", "service_extended": "service_extended",
            "renewal_disabled": "renewal_disabled", "plan_changed": "plan_changed"}


def module(name):
    spec = importlib.util.spec_from_file_location("audit_build_" + name, Path(__file__).with_name(name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


facts_tool = module("check_facts")
renderer = module("render_dashboard")
gate = module("check_audit")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value, field):
    require(isinstance(value, str) and bool(value.strip()), f"{field}: expected nonempty text")
    return value


def strings(value, field, nonempty=False):
    require(isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value),
            f"{field}: expected an array of nonempty strings")
    require(not nonempty or value, f"{field}: at least one reference is required")
    require(len(value) == len(set(value)), f"{field}: duplicate values")
    return value


def index(rows, field="id"):
    require(isinstance(rows, list), "Expected an array of records")
    result = {}
    for row in rows:
        require(isinstance(row, dict), "Expected a record object")
        key = text(row.get(field), field)
        require(key not in result, f"Duplicate {field}: {key}")
        result[key] = row
    return result


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=facts_tool.unique_object,
                      parse_constant=facts_tool.reject_constant)


def local_file(root, base, name, must_exist=True):
    text(name, "local file")
    relative = Path(name)
    require(not relative.is_absolute() and ".." not in relative.parts and "\\" not in name,
            "File references must be relative, without parent traversal")
    target = (base / relative).resolve()
    require(target.is_relative_to(root), "File reference escapes the private bundle")
    require(not must_exist or target.is_file(), f"Local file is missing: {name}")
    return target


def moment(value):
    renderer.validate_date(value)
    if len(value) == 10:
        return datetime.combine(date.fromisoformat(value), time.min, timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def local_day(value, zone):
    return value if len(value) == 10 else moment(value).astimezone(zone).date().isoformat()


def latest_records(rows, field, zone):
    """Keep same-day date-only evidence unorderable against clock times."""
    day = max(local_day(row[field], zone) for row in rows)
    candidates = [row for row in rows if local_day(row[field], zone) == day]
    if any(len(row[field]) == 10 for row in candidates):
        return candidates, day
    latest = max(moment(row[field]) for row in candidates)
    candidates = [row for row in candidates if moment(row[field]) == latest]
    return candidates, candidates[0][field]


def money(amount, currency):
    require(isinstance(amount, str) and re.fullmatch(r"\d+(?:\.\d+)?", amount, flags=re.ASCII),
            "Amounts must be nonnegative decimal strings")
    require(isinstance(currency, str) and re.fullmatch(r"[A-Z]{3}", currency),
            "Currency must be a three-letter uppercase code")
    return Decimal(amount)


def collect(data, root, input_dir):
    """Import inventories, preserving every disposition and local original path."""
    sources, searches, inputs = [], [], set()

    def add_source(row, base, default_ids=None):
        row = deepcopy(row)
        if row.get("file"):
            target = local_file(root, base, row["file"])
            inputs.add(target)
            row["file"] = target.relative_to(root).as_posix()
        if default_ids is not None and not row.get("service_ids"):
            row["service_ids"] = deepcopy(default_ids)
        row.setdefault("service_ids", [])
        row.setdefault("disposition", "unread")
        row.setdefault("note", "Saved source; reading has not been recorded.")
        sources.append(row)

    def add_search(row, base):
        row = deepcopy(row)
        target = local_file(root, base, row.get("result_file"))
        inputs.add(target)
        row["result_file"] = target.relative_to(root).as_posix()
        searches.append(row)

    for spec in data.get("imports", []):
        require(isinstance(spec, dict), "imports entries must be objects")
        path = local_file(root, input_dir, spec.get("file"))
        inputs.add(path)
        saved = load_json(path)
        if "messages" in saved:
            imported = [source for message in saved["messages"] for source in message["evidence_sources"]]
        else:
            imported = saved.get("sources", [])
        for row in imported:
            add_source(row, path.parent, spec.get("service_ids"))
        for row in saved.get("searches", []):
            add_search(row, path.parent)
    for row in data.get("sources", []):
        add_source(row, input_dir)
    for row in data.get("searches", []):
        add_search(row, input_dir)
    by_id = index(sources)
    index(searches)
    for change in index(data.get("source_updates", [])).values():
        require(isinstance(change, dict) and change.get("id") in by_id, "Source update has an unknown ID")
        require(set(change) <= {"id", "disposition", "note", "service_ids", "label", "date", "type", "url"},
                "Source updates cannot replace original files or attachment identities")
        if "disposition" in change:
            text(change.get("note"), "Source disposition change note")
        by_id[change["id"]].update(deepcopy(change))
    for source in sources:
        strings(source["service_ids"], "source.service_ids")
        text(source.get("note"), "source.note")
    return by_id, searches, inputs


def build(data, bundle_root, input_dir=None):
    """Return generated artifacts; callers write the manifest before running its gate."""
    root = Path(bundle_root).resolve()
    input_dir = Path(input_dir or root).resolve()
    require(isinstance(data, dict) and data.get("schema_version") == VERSION, "Expected schema_version audit-1")
    scope = deepcopy(data.get("scope"))
    require(isinstance(scope, dict) and scope.get("mode") in {"mailbox", "files"}, "scope.mode must be mailbox or files")
    text(scope.get("description"), "scope.description")
    scope["workflow_version"] = VERSION
    scope.setdefault("audit_kind", "inventory")
    require(scope["audit_kind"] in {"inventory", "targeted"}, "scope.audit_kind must be inventory or targeted")
    as_of = scope.get("as_of")
    require(isinstance(as_of, str) and len(as_of) == 10, "scope.as_of must be an ISO date")
    moment(as_of)
    zone = ZoneInfo(scope.get("timezone", "UTC"))
    entities = index(data.get("entities"))
    sources, searches, input_files = collect(data, root, input_dir)
    invoices = index(deepcopy(data.get("invoices", [])), "record_id")
    events = index(deepcopy(data.get("events", [])))
    material_refs = set()

    def refs(values, entity_id, field, nonempty=True):
        strings(values, field, nonempty)
        for ref in values:
            require(ref in sources, f"{field}: unknown source reference {ref}")
            material_refs.add(ref)
            associations = sources[ref].setdefault("service_ids", [])
            if entity_id not in associations:
                associations.append(entity_id)
        return deepcopy(values)

    for sid, entity in entities.items():
        require(entity.get("kind") in {"service", "case"}, f"{sid}: kind must be service or case")
        for field in ("name", "vendor"):
            text(entity.get(field), f"{sid}.{field}")
        require("account_ref" in entity, f"{sid}: account_ref is required (null if unknown)")
        if entity["account_ref"] is not None:
            text(entity["account_ref"], f"{sid}.account_ref")
        decision = entity.get("decision")
        require(isinstance(decision, dict), f"{sid}: an explicit decision is required")
        refs(decision.get("source_refs", []), sid, f"{sid}.decision.source_refs", False)
        for field in ("status_label", "status_note"):
            text(decision.get(field), f"{sid}.decision.{field}")
        require(decision.get("status") in {"observed", "uncertain", "user_reported", "historical"}, f"{sid}: invalid status")
        require(decision["status"] != "observed" or decision.get("source_refs"), f"{sid}: observed status requires source references")
        for collection in ("drafts", "review_signals"):
            require(isinstance(decision.get(collection, []), list) and all(isinstance(row, dict) for row in decision.get(collection, [])),
                    f"{sid}: {collection} must be an array of objects")
    for invoice in invoices.values():
        sid = invoice.pop("entity_id", None)
        require(sid in entities, "Invoice has an unknown entity_id")
        invoice["_entity_id"] = sid
        entity = entities[sid]
        for field in ("vendor", "account_ref"):
            require(field not in invoice, f"Invoice {field} comes from the entity; do not duplicate it")
            invoice[field] = entity[field]
        invoice.setdefault("subscription_ref", entity.get("subscription_ref"))
        refs(invoice.get("source_refs"), sid, "invoice.source_refs")
        for line in invoice.get("line_items", []):
            if "source_refs" in line:
                refs(line["source_refs"], sid, "line.source_refs")
    for event in events.values():
        sid = event.get("entity_id")
        require(sid in entities, "Event has an unknown entity_id")
        require(event.get("type") in EVENT_TYPES, "Unknown event type")
        require("occurred_on" in event, "Event occurred_on is required; use null when unknown")
        if event["occurred_on"] is not None:
            moment(event["occurred_on"])
            require(local_day(event["occurred_on"], zone) <= as_of, "Event occurrence is after the report date")
        if event["occurred_on"] is None or "observed_on" in event:
            moment(event.get("observed_on"))
            require(local_day(event["observed_on"], zone) <= as_of, "Event observation is after the report date")
        text(event.get("note"), "event.note")
        refs(event.get("source_refs"), sid, "event.source_refs")
        if "amount" in event or "currency" in event:
            value = money(event.get("amount"), event.get("currency"))
            require(event["type"] != "payment_succeeded" or value > 0, "Zero balance or credit settlement is not a successful cash payment")
        if event["type"] == "renewal_scheduled":
            moment(event.get("renews_on"))
            observed = event["occurred_on"] or event["observed_on"]
            require((local_day(event["renews_on"], zone) >= local_day(observed, zone)) if len(observed) == 10 or len(event["renews_on"]) == 10
                    else moment(event["renews_on"]) >= moment(observed), "Renewal predates its observation")
        if event["type"] == "service_period":
            facts_tool.check_period(event.get("period"), "event.period")
        if event.get("invoice_record_id"):
            inv = invoices.get(event["invoice_record_id"])
            require(inv is not None and inv["_entity_id"] == sid, "Event invoice must belong to the same entity")

    report = {"as_of": as_of, "title": data.get("title", "Bills, subscriptions and open questions"),
              "intro": data.get("intro", scope["description"]), "status_boundary": scope["description"],
              "subscriptions": [], "other_cases": [], "coverage": {"summary": scope["description"],
              "notes": deepcopy(scope.get("limitations", []))}, "appendix": [],
              "footer_note": "Private report based on the declared sources. Unknowns are not zero.",
              "monthly_cost": {"as_of": as_of, "items": [], "unknowns": [],
                "note": "Partial monthly estimate of explicitly supported ongoing costs. Separate from actual cash charges; unknown costs and usage are excluded."}}
    case_rows, outcomes = [], []
    for sid, entity in entities.items():
        decision = entity["decision"]
        entity_events = [e for e in events.values() if e["entity_id"] == sid]
        entity_invoices = [i for i in invoices.values() if i["_entity_id"] == sid]
        lifecycle = [e for e in entity_events if e["type"] in LIFECYCLE]
        if lifecycle:
            dated = [e for e in lifecycle if e["occurred_on"]]
            latest_rows = latest_records(dated, "occurred_on", zone)[0] if dated else []
            latest_rows += [e for e in lifecycle if e["occurred_on"] is None]
            latest_refs = {ref for e in latest_rows for ref in e["source_refs"]}
            require(latest_refs <= set(decision.get("source_refs", [])), f"{sid}: decision must cite the latest lifecycle evidence")
        alias = entity.get("account_alias") or entity["account_ref"] or "account unknown: " + sid
        text(alias, "account alias")
        row = {"id": sid, "name": entity["name"] + " · " + alias, "category": entity.get("category", "Service" if entity["kind"] == "service" else "Billing case"),
               "account_ref": entity["account_ref"], "vendor": entity["vendor"],
               "status": decision["status"], "status_label": decision["status_label"], "status_note": decision["status_note"],
               "source_refs": deepcopy(decision.get("source_refs", [])),
               "unknowns": deepcopy(decision.get("unknowns", [])), "drafts": [], "review_signals": [],
               "review_group": decision.get("review_group", "none"), "priority": decision.get("priority", False)}
        if entity.get("plan"):
            row["plan"] = entity["plan"]
        strings(row["unknowns"], "decision.unknowns")
        row["needs_action"] = row["review_group"] != "none"
        row["issue"] = deepcopy(decision.get("issue", {"title": "No specific issue established", "summary": "Review the remaining evidence gaps."}))
        row["action"] = deepcopy(decision.get("action", {"summary": "Review the stated unknowns before taking action.", "steps": []}))
        require(isinstance(row["issue"], dict) and isinstance(row["action"], dict), "Issue and action must be objects")
        text(row["action"].get("summary"), "action.summary")
        strings(row["action"].setdefault("steps", []), "action.steps")
        if row["review_group"] == "refund":
            row["refund_review"] = deepcopy(decision.get("refund_review"))
            require(isinstance(row["refund_review"], dict), "Refund decision needs an explicit rationale")
            refs(row["refund_review"].pop("source_refs", []), sid, "refund_review.source_refs")
        for draft in decision.get("drafts", []):
            draft = deepcopy(draft)
            for field in ("title", "condition", "text"):
                text(draft.get(field), "draft." + field)
            refs(draft.get("source_refs"), sid, "draft.source_refs")
            row["drafts"].append(draft)
        for signal in decision.get("review_signals", []):
            signal = deepcopy(signal)
            refs(signal.get("source_ids"), sid, "review_signal.source_ids")
            row["review_signals"].append(signal)

        row["billing_dates"] = billing_dates(entity_invoices, entity_events, as_of, zone)
        cost = deepcopy(entity.get("cost", {}))
        if cost.get("invoice_record_id"):
            invoice = invoices.get(cost["invoice_record_id"])
            require(invoice is not None and invoice["_entity_id"] == sid, "Cost invoice must belong to the same entity")
            require(not any(k in cost for k in ("amount", "currency")), "Invoice-derived cost must not duplicate amount/currency")
            cost.update(amount=invoice["amount_due"], currency=invoice["currency"])
            cost["source_refs"] = list(dict.fromkeys(invoice["source_refs"] + cost.get("source_refs", [])))
        include = cost.get("include_monthly", False)
        require(type(include) is bool, "cost.include_monthly must be a boolean")
        if "amount" in cost:
            money(cost["amount"], cost.get("currency"))
            refs(cost.get("source_refs"), sid, "cost.source_refs")
        require(not include or entity["kind"] == "service", "Cases cannot enter the monthly service baseline")
        if include:
            require(cost.get("kind") in {"fixed_monthly", "fixed_term", "base_plus_usage"}, "Top-ups and usage totals cannot become monthly fees")
            text(cost.get("basis"), "cost.basis")
            require(type(cost.get("months")) is int and cost["months"] > 0, "Cost months must be a positive integer")
            refs(cost.get("source_refs"), sid, "cost.source_refs")
            report["monthly_cost"]["items"].append({"service_id": sid, "amount": cost.get("amount"), "currency": cost.get("currency"),
                "months": cost["months"], "basis": cost["basis"], "sources": deepcopy(cost["source_refs"])})
        elif entity["kind"] == "service":
            report["monthly_cost"]["unknowns"].append({"service_id": sid, "note": cost.get("note", "Current monthly cost is not established.")})
        if include and cost.get("unknown_note"):
            report["monthly_cost"]["unknowns"].append({"service_id": sid, "note": cost["unknown_note"]})
        kind = cost.get("kind", "unknown")
        row["cost"] = {"kind": {"base_plus_usage": "monthly_base_plus_usage", "prepaid": "per_top_up"}.get(kind, kind),
            "label": cost.get("label", f"{cost['currency']} {cost['amount']} / {cost['months']} month(s)" if include else
                              f"{cost['currency']} {cost['amount']} observed" if "amount" in cost else "Amount unknown"),
            "note": cost.get("note", cost.get("basis", "Unknown does not mean zero.")), "include_monthly": False}
        # The old fixed-monthly subtotal is a subset of the same sourced baseline.
        if include and kind == "fixed_monthly" and cost["months"] == 1:
            row["cost"].update(include_monthly=True, amount=cost["amount"], currency=cost["currency"])
        timeline = [{"id": i["record_id"], "date": i["issued_on"], "label": "Invoice " + str(i["invoice_ref"] or i["record_id"]),
                     "source_refs": deepcopy(i["source_refs"]), "note": "Source references: " + ", ".join(i["source_refs"])} for i in entity_invoices]
        timeline += [{"id": e["id"], "date": e["occurred_on"], "label": e["type"].replace("_", " ").capitalize(),
                      "source_refs": deepcopy(e["source_refs"]),
                      "note": e["note"] + (" Observed on " + e["observed_on"] + "; event date unknown." if e["occurred_on"] is None else "") + " Sources: " + ", ".join(e["source_refs"])} for e in entity_events]
        for item in timeline:
            link = next((sources[ref]["url"] for ref in item["source_refs"] if sources[ref].get("url")), None)
            if link:
                item["url"] = link
        row["evidence"] = sorted(timeline, key=lambda e: moment(e["date"]) if e["date"] else datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        report["subscriptions" if entity["kind"] == "service" else "other_cases"].append(row)
        if entity["kind"] == "case" and row["review_group"] == "none":
            report["appendix"].append({"name": row["name"], "category": row["category"],
                                      "note": row["status_note"]})
        if entity["kind"] == "case" or row["needs_action"] or row["drafts"] or any("outcome_status" in e for e in entity_events):
            case_rows.append({"case_id": sid, "vendor": entity["vendor"], "account_ref": entity["account_ref"],
                              "invoice_record_ids": [i["record_id"] for i in entity_invoices],
                              "events": deepcopy(entity_events), "decision": deepcopy(decision)})
        for event in entity_events:
            if "outcome_status" in event:
                require(event["type"] in OUTCOMES, "This event type is not a supported outcome")
                require(event["outcome_status"] in {"reported", "accepted_pending_verification", "verified", "rejected"}, "Invalid outcome status")
                require(type(event.get("pre_existing")) is bool, "Outcomes must declare pre_existing")
                outcomes.append({**deepcopy(event), "case_id": sid, "type": OUTCOMES[event["type"]], "status": event["outcome_status"]})

    # Keep attachments tied to every relevant parent without assigning all search hits to all services.
    for _ in range(len(sources)):
        changed = False
        for source in sources.values():
            if source.get("parent_id"):
                require(source["parent_id"] in sources, "Attachment parent reference is unknown")
                parent = sources[source["parent_id"]]
                both = sorted(set(parent["service_ids"] + source["service_ids"]))
                if parent["service_ids"] != both or source["service_ids"] != both:
                    parent["service_ids"] = both
                    source["service_ids"] = both
                    changed = True
        if not changed:
            break
    for source in sources.values():
        strings(source["service_ids"], "source.service_ids")
        require(set(source["service_ids"]) <= set(entities), "Source references an unknown entity")
        require(source.get("disposition") in {"reviewed", "irrelevant", "unread", "inaccessible"}, "Invalid source disposition")
        if source.get("url"):
            require(isinstance(source["url"], str) and re.match(r"https?://[^/\s]+", source["url"]), "Source links must be supplied HTTP(S) URLs")
        require(not (source["disposition"] == "irrelevant" and source["id"] in material_refs),
                "A material assertion source cannot be irrelevant")
    for search in searches:
        require(set(strings(search.get("service_ids", []), "search.service_ids")) <= set(entities), "Search references an unknown entity")
    for row in report["subscriptions"] + report["other_cases"]:
        known = {ref for e in events.values() if e["entity_id"] == row["id"] for ref in e["source_refs"]}
        known |= {ref for i in invoices.values() if i["_entity_id"] == row["id"] for ref in i["source_refs"]}
        row["evidence"] += [{"id": s["id"], "source_refs": [s["id"]], "label": s.get("label", s["id"]), "date": s.get("date"), "note": s["note"],
                             **({"url": s["url"]} if s.get("url") else {})}
                            for s in sources.values() if row["id"] in s["service_ids"] and (s["id"] not in known or s.get("url")) and s["disposition"] != "irrelevant"]
    facts = {"schema_version": "0.1", "scope": deepcopy(scope),
             "sources": [{"id": s["id"], "type": s.get("type", "email" if s.get("kind") == "message" else "other"),
                          "locator": s.get("file") or s.get("label") or s["id"]} for s in sources.values()],
             "invoices": [{k: v for k, v in invoice.items() if k != "_entity_id"} for invoice in invoices.values()]}
    facts_tool.validate(facts)
    evidence = {"scope": deepcopy(scope), "sources": list(sources.values()), "searches": searches}
    if data.get("independent_review_file"):
        review_file = local_file(root, input_dir, data["independent_review_file"], False)
        input_files.add(review_file)
        evidence["independent_review_file"] = review_file.relative_to(root).as_posix()
    artifacts = {"facts.json": facts, "checks.json": facts_tool.check_facts(facts),
                 "dashboard.json": renderer.prepare(report), "audit-evidence.json": evidence}
    if case_rows:
        artifacts["cases.json"] = {"schema_version": VERSION, "cases": case_rows}
    if outcomes:
        artifacts["outcomes.json"] = {"schema_version": VERSION, "events": outcomes}
    return artifacts, input_files


def billing_dates(invoices, events, as_of, zone=None):
    zone = zone or ZoneInfo("UTC")
    unknown = lambda note: {"date": None, "status": "unknown", "note": note, "sources": []}
    result = {"last_invoice": unknown("No invoice issue date established."),
              "last_charge": unknown("No successful cash payment date established."),
              "next_renewal": unknown("No current explicit renewal schedule established.")}
    issued = [i for i in invoices if i.get("issued_on") is None or i["issued_on"] <= as_of]
    paid = [e for e in events if e["type"] == "payment_succeeded"]
    for key, rows, field, note in (("last_invoice", issued, "issued_on", "Latest observed invoice issue date; not proof of payment."),
                                   ("last_charge", paid, "occurred_on", "Latest explicitly observed successful cash payment; failed payments and refunds excluded.")):
        if rows:
            undated = [r for r in rows if r[field] is None]
            dated = [r for r in rows if r[field] is not None]
            if dated:
                matches, actual_date = latest_records(dated, field, zone)
                result[key] = {"date": actual_date, "status": "confirmed", "note": note,
                               "sources": list(dict.fromkeys(ref for r in matches for ref in r["source_refs"]))}
                if len(actual_date) == 10:
                    result[key]["note"] += " Clock-time ordering is not established by date-only evidence."
            if undated:
                previous = result[key]
                result[key] = unknown("Undated evidence prevents establishing the latest event date; an observation or email date is not the event date.")
                result[key]["sources"] = list(dict.fromkeys(previous["sources"] + [ref for r in undated for ref in r["source_refs"]]))
                if previous["date"]:
                    result[key]["related_date"] = {"date": previous["date"], "label": "Latest dated record; other event dates unknown"}
    scheduling = [e for e in events if e["type"] in {"renewal_scheduled", "renewal_disabled", "subscription_cancelled", "subscription_reactivated", "plan_changed"}]
    if scheduling:
        dated = [e for e in scheduling if e["occurred_on"]]
        undated = [e for e in scheduling if e["occurred_on"] is None]
        rows = (latest_records(dated, "occurred_on", zone)[0] if dated else []) + undated
        states = {(e["type"], e.get("renews_on")) for e in rows}
        sources = list(dict.fromkeys(ref for e in rows for ref in e["source_refs"]))
        scheduled = [e for e in rows if e["type"] == "renewal_scheduled"]
        types = {e["type"] for e in rows}
        common_source = set.intersection(*(set(e["source_refs"]) for e in rows))
        compatible_schedule = (bool(scheduled) and len({e["renews_on"] for e in scheduled}) == 1
                               and types <= {"renewal_scheduled", "subscription_reactivated", "plan_changed"}
                               and (len(states) == 1 or common_source))
        event = scheduled[0] if scheduled else rows[0]
        if not undated and compatible_schedule and local_day(event["renews_on"], zone) >= as_of:
            result["next_renewal"] = {"date": event["renews_on"], "status": "confirmed", "note": event["note"], "sources": sources}
        elif not undated and "renewal_disabled" in types and types <= {"renewal_disabled", "subscription_cancelled"} and (len(states) == 1 or common_source):
            result["next_renewal"] = {"date": None, "status": "not_scheduled", "note": event["note"], "sources": sources}
        else:
            result["next_renewal"].update(note="A later, expired or conflicting lifecycle event prevents reuse of the earlier renewal schedule.", sources=sources)
    periods = [e for e in events if e["type"] == "service_period" and e["period"].get("end")]
    periods += [{"period": line["period"], "source_refs": line.get("source_refs", invoice["source_refs"])}
                for invoice in invoices for line in invoice.get("line_items", [])
                if line.get("period", {}).get("end")]
    if periods and result["next_renewal"]["status"] == "unknown":
        end = max(e["period"]["end"] for e in periods)
        rows = [e for e in periods if e["period"]["end"] == end]
        result["next_renewal"]["related_date"] = {"date": end, "label": "Observed service period ends; renewal unverified"}
        result["next_renewal"]["sources"] = list(dict.fromkeys(result["next_renewal"]["sources"] + [ref for e in rows for ref in e["source_refs"]]))
    return result


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    path.chmod(0o600)


def run(input_path, output_dir, force=False):
    source, root = Path(input_path).resolve(), Path(output_dir).resolve()
    require(source.is_relative_to(root), "Keep audit.json and all sources inside the output bundle")
    artifacts, inputs = build(load_json(source), root, source.parent)
    names = set(artifacts) | {"audit-checks.json", "dashboard.html"}
    stale = []
    for name in {"cases.json", "outcomes.json"} - names:
        target = root / name
        if target.exists():
            require(force, f"Stale optional output exists: {name}; use --force intentionally")
            require(not target.is_symlink() and target.resolve() not in inputs | {source}, "Refusing to remove imported evidence")
            old = load_json(target)
            require(isinstance(old, dict) and old.get("schema_version") == VERSION,
                    f"Refusing to remove unrecognized optional file: {name}")
            stale.append(target)
    for name in names:
        target = root / name
        require(target.resolve() not in inputs | {source}, "Refusing to overwrite canonical input or imported evidence")
        require(not target.is_symlink(), "Output must not be a symbolic link")
        require(force or not target.exists(), f"Output exists: {name}; use --force intentionally")
    root.mkdir(parents=True, exist_ok=True)
    evidence_path = root / "audit-evidence.json"
    write_json(evidence_path, artifacts["audit-evidence.json"])
    artifacts["audit-checks.json"] = gate.assess(artifacts["dashboard.json"], evidence_path)
    html = renderer.render(deepcopy(artifacts["dashboard.json"]), evidence_path)
    for name, value in artifacts.items():
        write_json(root / name, value)
    (root / "dashboard.html").write_text(html, encoding="utf-8")
    (root / "dashboard.html").chmod(0o600)
    for path in stale:
        path.unlink()
    return artifacts["audit-checks.json"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        quality = run(args.input, args.output_dir, args.force)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"output_dir": str(args.output_dir.resolve()), "status": quality["status"], "issues": len(quality["issues"])}))


if __name__ == "__main__":
    main()
