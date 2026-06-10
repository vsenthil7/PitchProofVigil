"""CLI entry point: ppv gate-check --version v1.3.0 --dataset golden-wc26"""
from __future__ import annotations

import argparse
import sys

from pitchproof_vigil.client import Client, GateRequest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ppv", description="PitchProof Vigil CLI")
    sub = parser.add_subparsers(dest="command")

    gate = sub.add_parser("gate-check", help="Run the promotion gate check")
    gate.add_argument("--version", required=True, help="Candidate agent version")
    gate.add_argument("--dataset", required=True, help="Dataset ID to evaluate against")
    gate.add_argument("--policy", default="production", help="Gate policy name")
    gate.add_argument("--base-url", default=None)
    gate.add_argument("--api-key", default=None)
    gate.add_argument("--no-fail", action="store_true", help="Exit 0 even on BLOCKED")

    args = parser.parse_args(argv)
    if args.command == "gate-check":
        client = Client(base_url=args.base_url, api_key=args.api_key)
        result = client.gate.evaluate(
            GateRequest(
                candidate_version=args.version,
                dataset_id=args.dataset,
                policy_name=args.policy,
            )
        )
        print(f"Decision: {result.decision}")
        print(
            f"Score: {result.aggregate_score:.3f} / "
            f"Threshold: {result.threshold:.3f}"
        )
        print(f"Summary: {result.summary}")
        if not args.no_fail:
            result.raise_if_blocked()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
