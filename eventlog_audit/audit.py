"""Core checks. Input: list of dicts (one per delivery attempt). Pure functions, no network."""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field

BACKOFF_MIN_SECONDS = 1.0


@dataclass
class Finding:
    check: str
    severity: str  # "high" | "medium" | "low"
    event_id: str
    detail: str


@dataclass
class Report:
    total_deliveries: int = 0
    unique_events: int = 0
    findings: list[Finding] = field(default_factory=list)

    def by_check(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = defaultdict(list)
        for f in self.findings:
            out[f.check].append(f)
        return dict(out)


def load_jsonl(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {n}: invalid JSON ({exc.msg})") from exc
    return rows


def audit(rows: list[dict]) -> Report:
    """Fields used per row: event_id, resource_id, seq, ts (seconds), signature_ok, outcome.
    outcome is "processed" (side effect applied), "ignored" (deduplicated) or "failed"."""
    rep = Report(total_deliveries=len(rows))
    by_event: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_event[r["event_id"]].append(r)
    rep.unique_events = len(by_event)

    # 1. Same event applied more than once = missing idempotency.
    for eid, items in by_event.items():
        applied = [i for i in items if i["outcome"] == "processed"]
        if len(applied) > 1:
            rep.findings.append(Finding(
                "double-processed", "high", eid,
                f"side effect applied {len(applied)} times (deliveries: {len(items)})"))

    # 2. Event applied without a valid signature.
    for r in rows:
        if r["outcome"] == "processed" and not r.get("signature_ok", False):
            rep.findings.append(Finding(
                "unsigned-processed", "high", r["event_id"],
                "processed although signature check failed or was missing"))

    # 3. Retries too fast (no backoff) for the same event.
    for eid, items in by_event.items():
        times = sorted(i["ts"] for i in items)
        for a, b in zip(times, times[1:]):
            if b - a < BACKOFF_MIN_SECONDS:
                rep.findings.append(Finding(
                    "fast-retry", "low", eid,
                    f"retry after {b - a:.2f}s (< {BACKOFF_MIN_SECONDS}s)"))
                break

    # 4 + 5. Per resource: out-of-order and gaps, using the first applied delivery of each event.
    per_res: dict[str, list[dict]] = defaultdict(list)
    for eid, items in by_event.items():
        applied = sorted((i for i in items if i["outcome"] == "processed"), key=lambda i: i["ts"])
        if applied and "seq" in applied[0]:
            per_res[applied[0]["resource_id"]].append(applied[0])
    for res, items in per_res.items():
        items.sort(key=lambda i: i["ts"])
        highest = None
        for i in items:
            if highest is not None and i["seq"] < highest:
                rep.findings.append(Finding(
                    "out-of-order", "medium", i["event_id"],
                    f"resource {res}: seq {i['seq']} applied after seq {highest}"))
            else:
                highest = i["seq"]
        seqs = sorted({i["seq"] for i in items})
        for a, b in zip(seqs, seqs[1:]):
            if b - a > 1:
                rep.findings.append(Finding(
                    "gap", "medium", f"{res}:{a + 1}" + (f"-{b - 1}" if b - a > 2 else ""),
                    f"resource {res}: no applied event for seq {a + 1}" + (f"..{b - 1}" if b - a > 2 else "")))

    # 6. Events that never succeeded.
    for eid, items in by_event.items():
        if all(i["outcome"] == "failed" for i in items):
            rep.findings.append(Finding(
                "never-succeeded", "high", eid,
                f"{len(items)} attempt(s), all failed; needs replay or dead-letter"))
    return rep


def render_markdown(rep: Report, source: str = "log") -> str:
    lines = [f"# Webhook log audit: {source}", "",
             f"- Deliveries: {rep.total_deliveries}",
             f"- Unique events: {rep.unique_events}",
             f"- Findings: {len(rep.findings)}", ""]
    if not rep.findings:
        lines.append("No findings.")
        return "\n".join(lines) + "\n"
    order = {"high": 0, "medium": 1, "low": 2}
    for check, items in sorted(rep.by_check().items(), key=lambda kv: order[kv[1][0].severity]):
        lines.append(f"## {check} ({items[0].severity}, {len(items)})")
        for f in items:
            lines.append(f"- `{f.event_id}`: {f.detail}")
        lines.append("")
    return "\n".join(lines)
