# consensus-rank

Compute a consensus ranking from multiple ranked lists. Good for decision-making when you have multiple ranked lists. 

Features:

- Borda count, mean, and median aggregation methods
- Presence penalty for items missing from some lists
- Bootstrap uncertainty quantification (95% CI, *P*(#1), *P*(top-3))
- Cleveland-dot plot output showing bootstrapped uncertainty of ranking
- Multiple input files pooled into one combined ranking

Replaces my own `ranking.ipynb` notebook workflow with a simple CLI.

## Try without installing

If you have [`uv`](https://astral.sh/uv) — Astral's Python toolchain — run `rank` ephemerally with `uvx`, the Python equivalent of `npx -y`:

```sh
uvx --from git+https://github.com/rsnemmen/consensus-rank.git rank your_rankings.yaml
```

This downloads and caches the package in a throwaway environment under `~/.cache/uv`; nothing is added to your `PATH`. The next run is fast (cache hit); clear the cache with `uv cache clean` whenever.

Don't have `uv` yet? One-time install:

```sh
curl -fsSL https://astral.sh/uv/install.sh | sh
```

Already a [`pipx`](https://pipx.pypa.io) user? `pipx run` works the same way:

```sh
pipx run --spec git+https://github.com/rsnemmen/consensus-rank.git rank your_rankings.yaml
```

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/rsnemmen/consensus-rank/main/install.sh | bash
```

Installs [`uv`](https://astral.sh/uv) if needed, then installs `rank` into an isolated environment so it's available globally on your PATH.

## Quick start

```sh
rank examples/neighborhoods.yaml
```

```
score  name
-----  -----------------
 7.67  Higienópolis
 7.33  Butantã
 7.33  Pompéia
 6.33  Vila Leopoldina
 6.33  Vila Mariana
 3.00  Alto da Lapa
 2.67  Jardim Paulista
 2.33  Moema
 2.00  Alto de Pinheiros
```

## Input format

A YAML file containing a list of lists. Each inner list is one voter's ranking, **best → worst**. Items are arbitrary strings.

```yaml
- [option_a, option_b, option_c]   # voter 1
- [option_b, option_a, option_c]   # voter 2
- [option_a, option_c, option_b]   # voter 3
```

Multiple files can be passed; their rankings are pooled into one combined list of voters before aggregation.

See `examples/neighborhoods.yaml` (full overlap) and `examples/llms.yaml` (partial overlap) for runnable demos.

## Aggregation methods

| `--method` | Direction       | What it computes                           |
|------------|-----------------|--------------------------------------------|
| `borda`    | higher = better | Mean Borda points — default, matches notebook |
| `mean`     | lower = better  | Mean 1-indexed rank                        |
| `median`   | lower = better  | Median 1-indexed rank                      |

```sh
rank input.yaml --method mean
rank input.yaml --method median
```

## Missing items

Items absent from some lists are **kept and penalised**, not dropped. The score for each item is weighted by `appearances / total_voters`, so an item ranked first by one voter out of four scores a quarter of what it would if all four had ranked it. Use `-m` to see which items were affected:

```sh
rank examples/llms.yaml -m
```

```
note: partial items (penalised):
  gpt5chat: 2/3 rankings
  grok4: 2/3 rankings
  grok-fast: 2/3 rankings
score  name
-----  ------------
 5.67  gemini
 5.33  gpt5
 3.67  sonnet
 3.00  grok4
 1.67  gemini-flash
 1.33  gpt5chat
 1.33  grok-fast
```

## Uncertainty (bootstrap)

Use `--bootstrap` to quantify how stable the ranking is by resampling voters with replacement and re-aggregating. Three columns are added: a 95% score CI and the probability each item lands at rank #1 or in the top 3.

```sh
rank examples/neighborhoods.yaml --bootstrap          # 1000 resamples (default)
rank examples/neighborhoods.yaml --bootstrap 5000     # custom N
rank examples/neighborhoods.yaml --bootstrap --seed 0 # reproducible output
```

```
score  95% CI        P(#1)  P(top-3)  name
-----  ------------  -----  --------  -----------------
 7.67  [5.00, 9.00]   0.62      0.72  Higienópolis
 7.33  [5.00, 9.00]   0.38      0.72  Pompéia
 7.33  [7.00, 8.00]   0.00      1.00  Butantã
 ...
```

Wide CIs and low `P(top-3)` signal fragile positions; items absent from many voter lists will show both naturally (the existing presence penalty still applies inside each resample). Works with all `--method` options.

A PNG plot is also written automatically alongside the table. It shows a horizontal Cleveland-dot chart with each item's score and 95% CI as error bars, numbered in ranking order. The file is named `<first-input-stem>_ranking.png` in the current directory (e.g. `rank examples/llms.yaml --bootstrap` writes `./llms_ranking.png`).

## CLI reference

```
rank <input> [<input> ...] [--method {borda,mean,median}] [-m] [--bootstrap [N]] [--seed S]

positional:
  inputs                one or more YAML files; rankings from all files are pooled

options:
  --method              aggregation method (default: borda)
  -m, --show-missing    report items that appear in fewer than all rankings
  --bootstrap [N]       add 95% CI and top-K probabilities via voter bootstrap (default N=1000)
  --seed S              random seed for --bootstrap (reproducibility)
```
