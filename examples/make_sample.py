"""Builds examples/sample-events.jsonl. ALL DATA IS INVENTED EXAMPLE DATA."""
import json
from pathlib import Path

rows = []
def add(eid, res, seq, ts, outcome, sig=True):
    rows.append(dict(event_id=eid, resource_id=res, seq=seq, ts=ts, outcome=outcome, signature_ok=sig))

# order-1: clean
add("evt_01", "order-1", 1, 100.0, "processed")
add("evt_02", "order-1", 2, 130.0, "processed")
# evt_02 redelivered and correctly ignored
add("evt_02", "order-1", 2, 190.0, "ignored")
# order-2: duplicate applied twice (no idempotency)
add("evt_03", "order-2", 1, 200.0, "processed")
add("evt_03", "order-2", 1, 260.0, "processed")
# order-3: out of order (seq 3 arrives before 2)
add("evt_04", "order-3", 1, 300.0, "processed")
add("evt_06", "order-3", 3, 310.0, "processed")
add("evt_05", "order-3", 2, 320.0, "processed")
# order-4: gap (seq 2 never arrives)
add("evt_07", "order-4", 1, 400.0, "processed")
add("evt_09", "order-4", 3, 410.0, "processed")
# unsigned event applied
add("evt_10", "order-5", 1, 500.0, "processed", sig=False)
# fast retries then success
add("evt_11", "order-6", 1, 600.0, "failed")
add("evt_11", "order-6", 1, 600.2, "failed")
add("evt_11", "order-6", 1, 660.0, "processed")
# never succeeded
add("evt_12", "order-7", 1, 700.0, "failed")
add("evt_12", "order-7", 1, 760.0, "failed")

out = Path(__file__).with_name("sample-events.jsonl")
out.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
print(f"wrote {len(rows)} rows to {out}")
