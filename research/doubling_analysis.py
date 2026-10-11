"""What "double the account in a day" requires, measured on real BTC perp data.

For each UTC day, a trader picks a direction at 00:00 from the prior 24h trend (a simple,
honest rule), applies leverage L and holds until the account doubles, is liquidated
(equity ≤ 5% of the day's start — exchange maintenance margin), or the day ends. Costs:
one round trip at 13 bps × L of equity. We report, for each L, how often a day doubles,
how often it liquidates, and the probability of surviving N consecutive attempts.

    python -m research.doubling_analysis
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import data

LEVERAGES = (1, 2, 5, 10, 20, 50, 100)
ROUND_TRIP_BPS = 13.0
LIQUIDATION_EQUITY = 0.05


def day_paths(start: str = "2023-01-01", end: str = "2026-10-01") -> list[np.ndarray]:
    df = data.load("BTC/USDT:USDT", "1h", start, end).to_pandas().set_index("ts_close")
    df.index = pd.DatetimeIndex(df.index).tz_convert("UTC")
    c = df["close"]
    day = (df.index - pd.Timedelta(hours=1)).normalize()
    prev_close = c.groupby(day).last().shift(1)
    trend = np.sign(prev_close.diff())
    out = []
    for d, g in c.groupby(day):
        if len(g) < 24 or pd.isna(prev_close.get(d)) or pd.isna(trend.get(d)) or trend[d] == 0:
            continue
        out.append(trend[d] * (g.to_numpy() / prev_close[d] - 1.0))
    return out


def simulate(paths: list[np.ndarray], lev: float) -> dict:
    doubled = liquidated = 0
    end_eq = []
    for path in paths:
        eq_path = 1.0 + lev * path - lev * ROUND_TRIP_BPS / 1e4
        hit_double = np.argmax(eq_path >= 2.0) if (eq_path >= 2.0).any() else None
        hit_liq = np.argmax(eq_path <= LIQUIDATION_EQUITY) if (eq_path <= LIQUIDATION_EQUITY).any() else None
        if hit_liq is not None and (hit_double is None or hit_liq <= hit_double):
            liquidated += 1
            end_eq.append(0.0)
        elif hit_double is not None:
            doubled += 1
            end_eq.append(2.0)
        else:
            end_eq.append(max(eq_path[-1], 0.0))
    n = len(paths)
    p_liq = liquidated / n
    e = np.asarray(end_eq)
    return {
        "leverage": lev,
        "days": n,
        "p_double": doubled / n,
        "p_liquidated": p_liq,
        "mean_end_equity": float(e.mean()),
        "median_end_equity": float(np.median(e)),
        "p_survive_5_days": (1 - p_liq) ** 5,
        "p_survive_20_days": (1 - p_liq) ** 20,
        "growth_if_compounded": float(np.exp(np.log(np.clip(e, 1e-12, None)).mean())) if p_liq == 0 else 0.0,
    }


def main() -> int:
    paths = day_paths()
    abs_moves = np.array([np.abs(p).max() for p in paths])
    rows = [simulate(paths, L) for L in LEVERAGES]
    tbl = pd.DataFrame(rows)
    lines = [
        "# Doubling the account in one day — what it takes (BTC perp, 2023-01 → 2026-09)",
        "",
        f"Days analysed: {len(paths)}. Median largest intraday move from prior close: {np.median(abs_moves):.2%}; "
        f"days where it exceeded 5%: {(abs_moves > 0.05).mean():.1%}; exceeded 10%: {(abs_moves > 0.10).mean():.1%}.",
        f"Even with perfect foresight of the day's best point, doubling needs leverage ≈ 1 / move: "
        f"{1 / np.median(abs_moves):.0f}× on a median day.",
        "",
        "Trend-following direction each day, leverage L, stop at double or liquidation:",
        "",
        "| leverage | P(double) | P(liquidated) | median end equity | P(survive 5 days) | P(survive 20 days) | compounded daily growth |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['leverage']}× | {r['p_double']:.1%} | {r['p_liquidated']:.1%} | {r['median_end_equity']:.3f} | "
            f"{r['p_survive_5_days']:.1%} | {r['p_survive_20_days']:.1%} | {r['growth_if_compounded']:.4f} |"
        )
    lines += [
        "",
        "Reading: the leverage at which doubling becomes even occasionally possible is the leverage at which "
        "liquidation is more likely than doubling, and repeated attempts end in ruin with near certainty. "
        "The compounded growth column is 0 whenever any day liquidates — one wipe-out ends the game.",
    ]
    out = "\n".join(lines)
    from pathlib import Path

    p = Path("research/reports/doubling_analysis.md")
    p.write_text(out + "\n")
    print(out)
    print(tbl.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
