import json
import subprocess
import sys
from pathlib import Path

import pytest

from eventlog_audit.audit import audit, load_jsonl, render_markdown

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "examples" / "sample-events.jsonl"


def row(eid, res="r", seq=1, ts=0.0, outcome="processed", sig=True):
    return dict(event_id=eid, resource_id=res, seq=seq, ts=ts, outcome=outcome, signature_ok=sig)


def checks(rows):
    return {f.check for f in audit(rows).findings}


def test_clean_log_has_no_findings():
    rows = [row("a", seq=1, ts=1), row("b", seq=2, ts=2), row("b", seq=2, ts=70, outcome="ignored")]
    assert audit(rows).findings == []


def test_double_processed():
    assert "double-processed" in checks([row("a", ts=1), row("a", ts=70)])


def test_ignored_duplicate_is_fine():
    assert "double-processed" not in checks([row("a", ts=1), row("a", ts=70, outcome="ignored")])


def test_unsigned_processed():
    assert "unsigned-processed" in checks([row("a", sig=False)])


def test_unsigned_but_rejected_is_fine():
    assert "unsigned-processed" not in checks([row("a", sig=False, outcome="failed"),
                                                row("a", ts=70)])


def test_fast_retry_detected_and_slow_retry_ok():
    assert "fast-retry" in checks([row("a", outcome="failed", ts=0), row("a", ts=0.3)])
    assert "fast-retry" not in checks([row("a", outcome="failed", ts=0), row("a", ts=30)])


def test_out_of_order():
    rows = [row("a", seq=1, ts=1), row("c", seq=3, ts=2), row("b", seq=2, ts=3)]
    found = audit(rows).by_check()["out-of-order"]
    assert [f.event_id for f in found] == ["b"]


def test_gap():
    found = audit([row("a", seq=1, ts=1), row("c", seq=4, ts=2)]).by_check()["gap"]
    assert "2..3" in found[0].detail
    single = audit([row("a", seq=1, ts=1), row("c", seq=3, ts=2)]).by_check()["gap"]
    assert single[0].detail.endswith("seq 2")


def test_never_succeeded():
    assert "never-succeeded" in checks([row("a", outcome="failed", ts=0),
                                         row("a", outcome="failed", ts=60)])


def test_resources_are_independent():
    rows = [row("a", res="x", seq=5, ts=1), row("b", res="y", seq=1, ts=2)]
    assert audit(rows).findings == []


def test_counts():
    rep = audit([row("a", ts=1), row("a", ts=70, outcome="ignored"), row("b", seq=2, ts=2)])
    assert (rep.total_deliveries, rep.unique_events) == (3, 2)


def test_load_jsonl_skips_blank_and_reports_bad_line(tmp_path):
    p = tmp_path / "x.jsonl"
    p.write_text(json.dumps(row("a")) + "\n\n")
    assert len(load_jsonl(str(p))) == 1
    p.write_text("{bad\n")
    with pytest.raises(ValueError, match="line 1"):
        load_jsonl(str(p))


def test_sample_file_finds_each_planted_problem():
    by = audit(load_jsonl(str(SAMPLE))).by_check()
    assert [f.event_id for f in by["double-processed"]] == ["evt_03"]
    assert [f.event_id for f in by["unsigned-processed"]] == ["evt_10"]
    assert [f.event_id for f in by["out-of-order"]] == ["evt_05"]
    assert [f.event_id for f in by["never-succeeded"]] == ["evt_12"]
    assert [f.event_id for f in by["fast-retry"]] == ["evt_11"]
    assert "order-4" in by["gap"][0].detail


def test_markdown_render_lists_high_first():
    md = render_markdown(audit(load_jsonl(str(SAMPLE))), "sample")
    assert md.index("double-processed") < md.index("fast-retry")


def test_cli_exit_codes():
    cmd = [sys.executable, "-m", "eventlog_audit"]
    ok = subprocess.run(cmd + [str(SAMPLE)], cwd=ROOT, capture_output=True, text=True)
    assert ok.returncode == 0 and "double-processed" in ok.stdout
    bad = subprocess.run(cmd + [str(SAMPLE), "--fail-on-high"], cwd=ROOT, capture_output=True)
    assert bad.returncode == 1
    missing = subprocess.run(cmd + ["nope.jsonl"], cwd=ROOT, capture_output=True)
    assert missing.returncode == 2
