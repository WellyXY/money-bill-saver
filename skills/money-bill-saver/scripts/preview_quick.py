#!/usr/bin/env python3
"""Fast structural preview of a generated focused report."""

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path


REQUIRED_IDS = {"subscriptions", "services-panel", "cost-panel", "refunds", "other", "report-data"}


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.in_data = False
        self.data = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "script" and attrs.get("id") == "report-data":
            self.in_data = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_data = False

    def handle_data(self, data):
        if self.in_data:
            self.data += data


def check(folder):
    report = json.loads((folder / "dashboard.json").read_text(encoding="utf-8"))
    page = ReportParser()
    page.feed((folder / "dashboard.html").read_text(encoding="utf-8"))
    missing = REQUIRED_IDS - page.ids
    if missing:
        raise ValueError("Missing report sections: " + ", ".join(sorted(missing)))
    embedded = json.loads(page.data)
    if embedded != report:
        raise ValueError("Embedded page data differs from dashboard.json")
    computed = report["computed"]
    if computed["service_count"] != len(report["subscriptions"]):
        raise ValueError("Service count differs from displayed inventory")
    if computed["audit_quality"]["status"] != "focused":
        raise ValueError("Focused report must not claim independent review")
    return {"method": "generated HTML structure and embedded data",
            "status": "passed", "services": computed["service_count"],
            "refund_questions": computed["refund_count"],
            "other_issues": computed["other_issue_count"],
            "monthly_baseline": computed["monthly_baseline"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.output_dir), ensure_ascii=False))


if __name__ == "__main__":
    main()
