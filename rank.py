#!/usr/bin/env python3
"""Consensus ranking CLI — aggregate multiple ranked lists into one."""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

import yaml


def load(path: Path) -> list[list[str]]:
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, list):
        sys.exit(f"error: {path}: expected a YAML list of ranked lists")
    rankings: list[list[str]] = []
    for i, row in enumerate(data):
        if not isinstance(row, list) or len(row) == 0:
            sys.exit(f"error: ranking {i + 1} must be a non-empty list")
        items: list[str] = []
        for item in row:
            if not isinstance(item, str):
                print(
                    f"warning: ranking {i + 1}: coercing {item!r} to string",
                    file=sys.stderr,
                )
                item = str(item)
            items.append(item)
        rankings.append(items)
    return rankings


def aggregate(
    rankings: list[list[str]], method: str
) -> list[tuple[str, float]]:
    n = len(rankings)
    universe: set[str] = set()
    for r in rankings:
        universe.update(r)

    results: list[tuple[str, float]] = []
    for item in universe:
        present = [
            (v, ranking.index(item))
            for v, ranking in enumerate(rankings)
            if item in ranking
        ]
        k = len(present)

        if method == "borda":
            # Borda points for voter v at position p (0-indexed): L_v - p
            # Divide sum by n_voters_total so absent voters contribute 0 (penalty)
            points = sum(len(rankings[v]) - p for v, p in present)
            score = points / n
        elif method == "mean":
            # Mean 1-indexed rank, then inflate by n/k to penalise absent voters
            mean_r = statistics.mean(p + 1 for _, p in present)
            score = mean_r * (n / k)
        else:  # median
            med_r = float(statistics.median(p + 1 for _, p in present))
            score = med_r * (n / k)

        results.append((item, score))

    # borda: higher = better → descending; mean/median: lower = better → ascending
    results.sort(key=lambda x: x[1], reverse=(method == "borda"))
    return results


def format_table(rows: list[tuple[str, float]], method: str) -> str:
    label = "score" if method == "borda" else "rank"
    w1 = max(len(label), max(len(f"{s:.2f}") for _, s in rows))
    w2 = max(len("name"), max(len(name) for name, _ in rows))
    lines = [
        f"{label:>{w1}}  {'name':<{w2}}",
        f"{'-' * w1}  {'-' * w2}",
    ]
    for name, score in rows:
        lines.append(f"{score:>{w1}.2f}  {name:<{w2}}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="rank",
        description="Compute a consensus ranking from a YAML list of rankings.",
    )
    parser.add_argument(
        "inputs",
        type=Path,
        nargs="+",
        help="one or more YAML files; rankings from all files are pooled",
    )
    parser.add_argument(
        "--method",
        choices=["borda", "mean", "median"],
        default="borda",
        help="aggregation method (default: borda)",
    )
    parser.add_argument(
        "-m",
        "--show-missing",
        action="store_true",
        help="report items that appear in fewer than all rankings",
    )
    args = parser.parse_args()

    rankings: list[list[str]] = []
    for path in args.inputs:
        rankings.extend(load(path))
    if len(rankings) < 2:
        sys.exit(
            f"error: need at least 2 rankings across all inputs, got {len(rankings)}"
        )
    n = len(rankings)

    if args.show_missing:
        universe: set[str] = set()
        for r in rankings:
            universe.update(r)
        partial = {
            item: sum(1 for r in rankings if item in r)
            for item in universe
            if sum(1 for r in rankings if item in r) < n
        }
        if partial:
            print("note: partial items (penalised):", file=sys.stderr)
            for item, k in sorted(partial.items(), key=lambda x: x[1]):
                print(f"  {item}: {k}/{n} rankings", file=sys.stderr)

    rows = aggregate(rankings, args.method)
    print(format_table(rows, args.method))


if __name__ == "__main__":
    main()
