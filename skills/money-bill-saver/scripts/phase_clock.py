#!/usr/bin/env python3
"""Record one staged benchmark and stop at the first exceeded phase budget."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


PHASES = (
    ("discovery", 150),
    ("evidence", 270),
    ("report", 150),
    ("preview", 30),
)
TARGET_SECONDS = sum(budget for _, budget in PHASES)


def _time(value=None):
    parsed = datetime.now(timezone.utc) if value is None else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp needs an explicit timezone")
    return parsed.astimezone(timezone.utc)


def _stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def _write(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def begin(path, revision, mode, window, model, now=None):
    if path.exists():
        raise ValueError("A benchmark already exists at this path; resume its next phase instead of restarting")
    at = _time(now)
    record = {
        "schema_version": "1", "revision": revision, "mode": mode,
        "window": window, "model": model, "target_seconds": TARGET_SECONDS,
        "started_at": _stamp(at), "status": "running", "phases": [],
    }
    _write(path, record)
    return record


def finish(path, phase, counts=None, now=None):
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("status") != "running":
        raise ValueError("Benchmark stopped or completed; resume the failed phase explicitly")
    completed = [row for row in record["phases"] if row["result"] == "within_budget"]
    expected = PHASES[len(completed)][0]
    if phase != expected:
        raise ValueError(f"Next phase must be {expected}; do not repeat or skip a phase")
    start = _time(record.get("phase_started_at") or
                  (completed[-1]["ended_at"] if completed else record["started_at"]))
    end = _time(now)
    seconds = round((end - start).total_seconds(), 3)
    if seconds < 0:
        raise ValueError("Phase end precedes its start")
    budget = PHASES[len(completed)][1]
    effective_elapsed = round(sum(row["seconds"] for row in completed) + seconds, 3)
    state = "over_budget" if seconds > budget or effective_elapsed > TARGET_SECONDS else "within_budget"
    record["phases"].append({"phase": phase, "started_at": _stamp(start), "ended_at": _stamp(end),
                             "seconds": seconds, "budget_seconds": budget, "result": state,
                             "mode": record.get("current_mode", record["mode"]),
                             "counts": counts or {}})
    record.pop("phase_started_at", None)
    record["elapsed_seconds"] = effective_elapsed
    record["wall_elapsed_seconds"] = round((end - _time(record["started_at"])).total_seconds(), 3)
    record["status"] = "stop" if state == "over_budget" else ("completed" if len(completed) + 1 == len(PHASES) else "running")
    if state == "over_budget":
        record["stop_reason"] = f"{phase} exceeded its phase or overall budget; inspect this stage before any replay"
    else:
        record.pop("stop_reason", None)
    _write(path, record)
    return record


def resume(path, now=None):
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("status") != "stop" or record["phases"][-1]["result"] != "over_budget":
        raise ValueError("Only a stopped failed phase can be resumed")
    record["status"] = "running"
    record["current_mode"] = "replay"
    record["phase_started_at"] = _stamp(_time(now))
    record["retries"] = record.get("retries", 0) + 1
    _write(path, record)
    return record


def _counts(items):
    result = {}
    for item in items:
        name, sep, value = item.partition("=")
        if not sep or not name.isidentifier() or name in result or not value.isdecimal():
            raise ValueError("Each --count needs a unique name=nonnegative_integer")
        result[name] = int(value)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    first = commands.add_parser("begin")
    first.add_argument("--output", required=True, type=Path)
    first.add_argument("--revision", required=True)
    first.add_argument("--mode", required=True, choices=("live", "replay"))
    first.add_argument("--window", required=True)
    first.add_argument("--model", required=True)
    next_step = commands.add_parser("finish")
    next_step.add_argument("--output", required=True, type=Path)
    next_step.add_argument("--phase", required=True, choices=tuple(name for name, _ in PHASES))
    next_step.add_argument("--count", action="append", default=[])
    replay = commands.add_parser("resume")
    replay.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == "begin":
            result = begin(args.output, args.revision, args.mode, args.window, args.model)
        elif args.command == "finish":
            result = finish(args.output, args.phase, _counts(args.count))
        else:
            result = resume(args.output)
        print(json.dumps({"status": result["status"], "elapsed_seconds": result.get("elapsed_seconds", 0),
                          "latest_phase": result["phases"][-1] if result["phases"] else None}, ensure_ascii=False))
        return 2 if result["status"] == "stop" else 0
    except (OSError, ValueError, KeyError, IndexError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
