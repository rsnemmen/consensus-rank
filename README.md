# ranking

Compute a consensus ranking from multiple ranked lists. Replaces the `ranking.ipynb` notebook workflow with a simple CLI.

## Install

```sh
pip install -e .
```

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
 6.33  Vila Mariana
 6.33  Vila Leopoldina
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

## CLI reference

```
rank <input> [--method {borda,mean,median}] [-m]

positional:
  input                 YAML file containing a list of ranked lists

options:
  --method              aggregation method (default: borda)
  -m, --show-missing    report items that appear in fewer than all rankings
```
