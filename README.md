# NVIDIA CEO quantile forecaster

Entry for make.fun `polymarket-nvidia-ceo-forecast-01`: forecast every
Polymarket "Next CEO of NVIDIA?" market's Yes price, minute by minute, 4
hours ahead, as five quantiles (5/25/50/75/95%).

## Method

- **Median = last price, flat.** Extrapolating recent drift, unwinding fresh
  jumps, and pulling toward the hourly mean all made held-out scores worse
  (trends in this market reverse); the median stays put.
- **Spread = the market's own recent change distribution.** For look-ahead
  steps of 5/15/30/60/120/240 minutes, take the quantiles of every
  overlapping price change in the last day, interpolate them across
  horizons, and shrink them by 0.6 (chosen on held-out windows: narrower
  bands win on calm practice-like windows; below ~0.5 they start losing on
  violent windows).
- Deterministic, standard library only, no network. ~0.15 s per case.

## Held-out evidence (offline, kit data only)

- Practice-forward overlap (p00–p04 scored against the next case's history):
  loss **0.352** vs house baseline **0.399** on the same windows.
- Rolling-origin cuts (12h / 24h before each checkpoint, 12 cuts):
  loss **1.462** vs house baseline **1.463** — essentially tied; those
  windows contain regime shifts the practice windows do not.
- Reference server practice scores: rank 1 0.190, rank 100 0.240, house
  model 0.313, house baseline 0.364. The rules warn the practice is no
  guide to the final, so no rank claim is made here.

## Run

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```
