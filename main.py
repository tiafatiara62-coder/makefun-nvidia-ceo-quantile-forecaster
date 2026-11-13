# Quantile forecaster for Polymarket's "Next CEO of NVIDIA?" event.
#
# Idea in one paragraph: Yes prices mostly sit still, then jump. The median
# therefore stays at the last price (extrapolating the recent drift hurt
# every held-out window), and the spread is the market's own recent
# for each look-ahead step, the quantiles of every overlapping change in
# the last day, interpolated across horizons. A band that fits how far the
# price actually moved lately beats a one-size-fits-all random walk.
#
# Standard library only. No network, no randomness, no model calls.

import glob
import json
import math
import os

LEVELS = (0.05, 0.25, 0.5, 0.75, 0.95)
# Overall multiplier on the empirical spreads (tuning knob; 0.6 chosen on
# held-out windows: best overlap score with rolling-origin still tied
# with the baseline, where narrower bands start to lose).
SPREAD_MULT = 0.6


def _quantile(sorted_values, level):
    """Linear-interpolation quantile of an already sorted list."""
    n = len(sorted_values)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_values[0]
    pos = level * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def _change_quantiles(prices):
    """Empirical quantiles of price changes over several look-ahead steps.

    For each step in GRID, take every overlapping change p[t+step]-p[t] in
    the last day and record its five quantiles. Prices mostly sit still, so
    these quantiles are tight for short steps and widen with the step --
    exactly the shape a pinball score rewards. Returns
    {step: [q05, q25, q50, q75, q95]} plus the median change per step.
    """
    window = prices[-1440:] if len(prices) > 1440 else prices[:]
    grid = (5, 15, 30, 60, 120, 240)
    table = {}
    for step in grid:
        if len(window) <= step + 30:
            continue
        changes = sorted(window[i + step] - window[i]
                         for i in range(len(window) - step))
        table[step] = [_quantile(changes, lv) for lv in LEVELS]
    if not table:
        # Very short history: fall back to a narrow random-walk band.
        table = {5: [-0.004, -0.001, 0.0, 0.001, 0.004],
                 240: [-0.03, -0.01, 0.0, 0.01, 0.03]}
    return table


def _interp_spread(table, horizon, level_idx):
    """Spread (quantile minus median) at an arbitrary horizon, log-log
    interpolated between the measured steps, monotone in the horizon."""
    steps = sorted(table)
    # Work in log space on the step; spreads are positive by construction
    # after taking absolute values per level side.
    def spread_at(step):
        row = table[step]
        return row[level_idx] - row[2]

    if horizon <= steps[0]:
        return spread_at(steps[0])
    if horizon >= steps[-1]:
        return spread_at(steps[-1])
    for a, b in zip(steps, steps[1:]):
        if a <= horizon <= b:
            wa = (math.log(b) - math.log(horizon)) / (math.log(b) - math.log(a))
            return wa * spread_at(a) + (1.0 - wa) * spread_at(b)
    return spread_at(steps[-1])


def _interp_median(table, horizon):
    """Median change at an arbitrary horizon.

    Deliberately zero: extrapolating the last day's median drift hurt every
    held-out window (trends in this market reverse). The median stays at
    the last price; all the signal lives in the spread.
    """
    return 0.0


def _forecast_market(prices, horizon):
    """Return 240 rows of five quantiles for one market.

    Median: last price plus the (usually ~zero) empirical median change.
    Spread: the market's own recent change quantiles, widened with the
    horizon and kept monotone in both horizon and level.
    """
    last = prices[-1]
    table = _change_quantiles(prices)
    rows = []
    prev_spreads = [0.0] * len(LEVELS)
    for h in range(1, horizon + 1):
        median = last + _interp_median(table, h)
        row = []
        for j in range(len(LEVELS)):
            spread = _interp_spread(table, h, j) * SPREAD_MULT
            # Spreads must not shrink as the horizon grows.
            if j == 2:
                spread = 0.0
            elif j < 2:
                spread = min(spread, 0.0)
                spread = min(spread, prev_spreads[j])
            else:
                spread = max(spread, 0.0)
                spread = max(spread, prev_spreads[j])
            prev_spreads[j] = spread
            row.append(median + spread)
        rows.append(row)
    return rows


def forecast_case(case):
    horizon = int(case.get("horizon_minutes", 240))
    forecasts = []
    for market in case["markets"]:
        prices = [float(v) for v in market["prices"]]
        rows = _forecast_market(prices, horizon)
        fixed_rows = []
        for row in rows:
            row = [max(0.0, min(1.0, v)) for v in row]
            for j in range(1, len(row)):
                if row[j] < row[j - 1]:
                    row[j] = row[j - 1]
            fixed_rows.append([round(v, 6) for v in row])
        forecasts.append({"id": market["id"], "q": fixed_rows})
    return {"forecasts": forecasts}


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR") or "/input/"
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output/"
    os.makedirs(out_dir, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(in_dir, "*.in"))):
        with open(path, "r", encoding="utf-8") as fh:
            case = json.load(fh)
        result = forecast_case(case)
        stem = os.path.splitext(os.path.basename(path))[0]
        out_path = os.path.join(out_dir, stem + ".out")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, separators=(",", ":"))


if __name__ == "__main__":
    main()
