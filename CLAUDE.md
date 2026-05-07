# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```sh
pip install -e .
```

## Running the tool

```sh
rank <input.yaml>
rank <input.yaml> --method {borda,mean,median}
rank <input.yaml> -m          # show items penalised for partial presence
```

## Architecture

The entire implementation lives in a single file: `rank.py`. There is no package structure.

**Data flow:** `load()` → `aggregate()` → `format_table()` → `print`

- `load(path)` — parses the YAML (list of lists, best→worst) and returns `list[list[str]]`
- `aggregate(rankings, method)` — computes the consensus score for each item across all voters and returns a sorted `list[tuple[str, float]]`
- `format_table(rows, method)` — formats the result as a column-aligned text table
- `main()` — `argparse` entry point wired to the `rank` script in `pyproject.toml`

## Aggregation methods and penalty

All three methods apply a **presence penalty**: an item's score is weighted by `appearances / n_voters_total`, so items missing from some lists are penalised rather than dropped.

- **borda** (default): `sum(L_v - p for present voters) / n_voters_total` — Borda points (position `p` is 0-indexed; first place in a list of length `L_v` earns `L_v` points). Higher score = better.
- **mean**: `mean(1-indexed rank across present voters) × (n_voters_total / appearances)`. Lower score = better.
- **median**: same as mean but with median instead of mean. Lower score = better.

When all items appear in every list the penalty is 1.0 and Borda matches `ranky.ranking.borda` exactly.

## Examples

`examples/neighborhoods.yaml` — 9 items × 3 voters, full overlap (verifies Borda against the original notebook).  
`examples/llms.yaml` — 7 items × 3 voters, partial overlap (demonstrates the penalty).
