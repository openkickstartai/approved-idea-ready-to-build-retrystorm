#!/usr/bin/env python3
"""RetryStorm CLI entry point."""
import argparse
import json
import sys
from retrystorm import load_topology, analyze, to_sarif


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="retrystorm",
        description="Detect retry storms, timeout inversions, and circuit breaker gaps",
    )
    parser.add_argument("config", help="Path to topology YAML file")
    parser.add_argument("--format", choices=["text", "sarif", "json"], default="text",
                        dest="output_format")
    parser.add_argument("--threshold", type=int, default=10,
                        help="Retry amplification threshold (default: 10)")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 on any finding, not just errors")
    args = parser.parse_args(argv)
    try:
        topology = load_topology(args.config)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        sys.exit(2)
    findings = analyze(topology, args.threshold)
    if args.output_format == "sarif":
        print(json.dumps(to_sarif(findings), indent=2))
    elif args.output_format == "json":
        out = [{"rule": f.rule, "severity": f.severity,
                "message": f.message, "path": f.path} for f in findings]
        print(json.dumps(out, indent=2))
    else:
        if not findings:
            print("\u2705 No resilience issues found.")
        else:
            print(f"\U0001f50d Found {len(findings)} issue(s):\n")
            for f in findings:
                icon = "\U0001f534" if f.severity == "error" else "\U0001f7e1"
                print(f"  {icon} [{f.rule}] {f.message}")
    has_errors = any(f.severity == "error" for f in findings)
    sys.exit(1 if has_errors or (args.strict and findings) else 0)


if __name__ == "__main__":
    main()
