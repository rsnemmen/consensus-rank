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

_NATURE_RC: dict[str, object] = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica Neue", "Helvetica", "DejaVu Sans"],
    "axes.facecolor": "white",
    "figure.facecolor": "white",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.8,
    "axes.labelsize": 10,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "xtick.major.size": 4,
    "ytick.major.size": 4,
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "grid.color": "#d0d0d0",
    "grid.linewidth": 0.6,
    "legend.fontsize": 9,
    "legend.frameon": True,
    "legend.framealpha": 0.9,
    "legend.edgecolor": "#cccccc",
    "legend.title_fontsize": 9,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
}


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


def plot_ranking(
    rows: list[tuple[str, float]],
    uncertainty: dict[str, dict[str, float]],
    method: str,
    output_path: Path,
    title: str | None = None,
) -> None:
    """Cleveland-dot plot: items ranked top→bottom, score on x, 95% CI as error bars."""
    try:
        import matplotlib
        import matplotlib.pyplot as plt
    except ImportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("Plotting requires matplotlib: pip install matplotlib", file=sys.stderr)
        sys.exit(1)

    x_labels = {
        "borda": "Borda score (higher = better)",
        "mean": "Mean rank (lower = better)",
        "median": "Median rank (lower = better)",
    }

    n = len(rows)
    with matplotlib.rc_context(_NATURE_RC):
        fig, ax = plt.subplots(figsize=(8, max(4, n * 0.4)))

        for i in range(n):
            if i % 2 == 0:
                ax.axhspan(i - 0.5, i + 0.5, facecolor="#f5f5f5", alpha=1.0, zorder=0)

        for i, (name, score) in enumerate(rows):
            u = uncertainty[name]
            lo, hi = u["score_lo"], u["score_hi"]
            ax.errorbar(
                score,
                i,
                xerr=[[score - lo], [hi - score]],
                fmt="o",
                color="#0072B2",
                ecolor="#0072B2",
                elinewidth=0.9,
                alpha=0.88,
                markersize=9,
                capsize=2,
                capthick=0.9,
                markeredgecolor="white",
                markeredgewidth=0.6,
                zorder=2,
            )

        ax.set_yticks(range(n))
        ax.set_yticklabels([f"{i + 1}. {name}" for i, (name, _) in enumerate(rows)])
        ax.invert_yaxis()
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.grid(True, axis="x", linestyle="--", linewidth=0.6, alpha=0.5)
        ax.set_xlabel(x_labels.get(method, "score"))
        ax.set_title(title or "Ranking", pad=12)

        fig.savefig(output_path)
        plt.close(fig)

    print(f"Plot saved to: {output_path}", file=sys.stderr)


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

    if uncertainty is not None:
        out_path = Path(f"{args.inputs[0].stem}_ranking.png")
        plot_ranking(rows, uncertainty, args.method, out_path, title=f"Ranking — {args.inputs[0].stem}")


if __name__ == "__main__":
    main()
