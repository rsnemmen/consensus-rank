#!/usr/bin/env python3
"""Consensus ranking CLI — aggregate multiple ranked lists into one."""
from __future__ import annotations

import argparse
import random
import statistics
import sys
from pathlib import Path

import numpy as np
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
    # secondary key on name breaks ties deterministically (also fixes cross-run reproducibility)
    if method == "borda":
        results.sort(key=lambda x: (-x[1], x[0]))
    else:
        results.sort(key=lambda x: (x[1], x[0]))
    return results


def bootstrap(
    rankings: list[list[str]],
    method: str,
    n_iter: int,
    seed: int | None,
) -> dict[str, dict[str, float]]:
    """Resample voters with replacement n_iter times and re-aggregate each time.

    Returns per-item: score_lo, score_hi (2.5/97.5 percentiles), p_top1, p_top3.
    Items absent from a resample contribute 0 to top-K counts (denominator = n_iter).
    """
    rng = random.Random(seed)
    n = len(rankings)

    scores_by_item: dict[str, list[float]] = {}
    top1_by_item: dict[str, int] = {}
    top3_by_item: dict[str, int] = {}

    universe: set[str] = set()
    for r in rankings:
        universe.update(r)
    for item in universe:
        scores_by_item[item] = []
        top1_by_item[item] = 0
        top3_by_item[item] = 0

    for _ in range(n_iter):
        resample = rng.choices(rankings, k=n)
        rows = aggregate(resample, method)
        for rank_idx, (name, score) in enumerate(rows, start=1):
            scores_by_item[name].append(score)
            if rank_idx == 1:
                top1_by_item[name] += 1
            if rank_idx <= 3:
                top3_by_item[name] += 1
        # items absent from this resample: score not recorded, count not incremented

    result: dict[str, dict[str, float]] = {}
    for item in universe:
        s = scores_by_item[item]
        if s:
            lo, hi = float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))
        else:
            lo = hi = float("nan")
        result[item] = {
            "score_lo": lo,
            "score_hi": hi,
            "p_top1": top1_by_item[item] / n_iter,
            "p_top3": top3_by_item[item] / n_iter,
        }
    return result


def format_table(
    rows: list[tuple[str, float]],
    method: str,
    uncertainty: dict[str, dict[str, float]] | None = None,
) -> str:
    label = "score" if method == "borda" else "rank"
    w1 = max(len(label), max(len(f"{s:.2f}") for _, s in rows))
    w2 = max(len("name"), max(len(name) for name, _ in rows))

    if uncertainty is None:
        lines = [
            f"{label:>{w1}}  {'name':<{w2}}",
            f"{'-' * w1}  {'-' * w2}",
        ]
        for name, score in rows:
            lines.append(f"{score:>{w1}.2f}  {name:<{w2}}")
        return "\n".join(lines)

    # build CI strings to size the column
    ci_strs = {
        name: f"[{u['score_lo']:.2f}, {u['score_hi']:.2f}]"
        for name, u in uncertainty.items()
    }
    ci_hdr = "95% CI"
    wci = max(len(ci_hdr), max(len(s) for s in ci_strs.values()))
    wp1 = max(len("P(#1)"), 4)   # 0.xx → 4 chars
    wp3 = max(len("P(top-3)"), 4)

    lines = [
        f"{label:>{w1}}  {ci_hdr:<{wci}}  {'P(#1)':>{wp1}}  {'P(top-3)':>{wp3}}  {'name':<{w2}}",
        f"{'-' * w1}  {'-' * wci}  {'-' * wp1}  {'-' * wp3}  {'-' * w2}",
    ]
    for name, score in rows:
        u = uncertainty[name]
        ci = ci_strs[name]
        lines.append(
            f"{score:>{w1}.2f}  {ci:<{wci}}  {u['p_top1']:>{wp1}.2f}  {u['p_top3']:>{wp3}.2f}  {name:<{w2}}"
        )
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
    parser.add_argument(
        "--bootstrap",
        nargs="?",
        const=1000,
        type=int,
        default=None,
        metavar="N",
        help="quantify uncertainty by bootstrapping voters N times (default N=1000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="random seed for --bootstrap (for reproducibility)",
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
    uncertainty = (
        bootstrap(rankings, args.method, args.bootstrap, args.seed)
        if args.bootstrap is not None
        else None
    )
    print(format_table(rows, args.method, uncertainty))


if __name__ == "__main__":
    main()
