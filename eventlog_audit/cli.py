import argparse
import sys

from .audit import audit, load_jsonl, render_markdown


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="webhook-log-audit",
                                description="Audit a webhook delivery log (JSONL).")
    p.add_argument("log", help="path to a JSONL file")
    p.add_argument("--fail-on-high", action="store_true", help="exit 1 if any high finding")
    a = p.parse_args(argv)
    try:
        rows = load_jsonl(a.log)
        rep = audit(rows)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc!r}", file=sys.stderr)
        return 2
    print(render_markdown(rep, a.log))
    if a.fail_on_high and any(f.severity == "high" for f in rep.findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
