"""Generate a synthetic household register so the app can run without real data.

Every value is random. Areas are called "Area 01" to "Area 12". There are no names,
ID numbers, addresses or phone numbers, because the app never needs them.

Two effects are built in on purpose, so the analyses have something to find:
  * vulnerability depends on household traits (disability, no work, no cover, widowhood...);
  * each area rates households a little more or less severely than the others,
    which is what the "with / without area" model comparison measures.

Usage: python scripts/make_demo_data.py [--rows 20000] [--seed 7] [--out data/raw/households.csv]
"""
import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(ROOT / "data" / "raw" / "households.csv"))
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    n = a.rows

    areas = [f"Area {i:02d}" for i in range(1, 13)]
    area_w = rng.dirichlet(np.ones(len(areas)) * 3)
    area = rng.choice(areas, n, p=area_w)
    area_bias = dict(zip(areas, rng.normal(0, 0.6, len(areas))))  # local rating severity

    sex = rng.choice(["M", "F"], n, p=[0.62, 0.38])
    age = np.clip(rng.normal(48, 15, n), 18, 95).round()
    family = np.where(sex == "F",
                      rng.choice(["married", "widowed", "divorced", "abandoned", "single_parent", "single"], n, p=[.42, .25, .12, .06, .07, .08]),
                      rng.choice(["married", "widowed", "divorced", "single", "other"], n, p=[.78, .05, .05, .10, .02]))
    sector = rng.choice(["informal", "no_work", "formal"], n, p=[.55, .33, .12])
    health = rng.choice(["healthy", "chronic", "serious", "disability", "elderly"], n, p=[.62, .14, .04, .08, .12])
    health = np.where((age > 70) & (rng.random(n) < .5), "elderly", health)
    cover = rng.choice(["none", "basic", "contributory"], n, p=[.38, .47, .15])
    household = np.clip(rng.poisson(4.2, n), 1, 14)
    children = np.minimum(np.clip(rng.poisson(2.0, n), 0, 10), household - 1)
    n_disabled = np.where(health == "disability", 1, 0) + rng.binomial(1, .04, n)
    n_chronic = np.where(health == "chronic", 1, 0) + rng.binomial(1, .08, n)
    head = (rng.random(n) < .9).astype(int)

    # Latent need -> social status rating (plus the local rating bias)
    score = (1.2 * (health == "disability") + .8 * (health == "serious") + .4 * (health == "chronic")
             + .7 * (sector == "no_work") + .3 * (sector == "informal") - .6 * (sector == "formal")
             + .6 * (cover == "none") + .5 * np.isin(family, ["widowed", "abandoned", "single_parent"])
             + .12 * (household - 4) + .015 * (age - 48)
             + np.vectorize(area_bias.get)(area) + rng.normal(0, .8, n))
    social = pd.cut(score, [-np.inf, -.6, .6, 1.6, np.inf], labels=["well_off", "middle", "vulnerable", "very_vulnerable"]).astype(str)
    assessed = rng.random(n) < .82
    social = np.where(assessed, social, None)

    # Programmes: more likely when the need score is high; some are area-run
    p = 1 / (1 + np.exp(-(score - .6)))
    progs = {
        "program_a": rng.random(n) < .55 * p + .05,
        "program_b": rng.random(n) < .45,
        "program_c": rng.random(n) < .25 * p,
        "program_d": (rng.random(n) < .30) & np.isin(area, areas[:6]),
        "program_e": rng.random(n) < .12,
        "program_f": (rng.random(n) < .30 * p) & (sector == "informal"),
    }
    got = np.vstack(list(progs.values())).any(axis=0)
    start = date(2020, 4, 1)
    aid_date = [str(start + timedelta(days=int(d))) if g else None for g, d in zip(got, rng.gamma(2.0, 12.0, n))]

    df = pd.DataFrame({"household_id": np.arange(1, n + 1), "area": area, "age": age, "sex": sex,
                       "family_status": family, "social_status": social, "health_status": health,
                       "health_cover": cover, "work_sector": sector, "household_size": household,
                       "children": children, "n_disabled": n_disabled, "n_chronic": n_chronic,
                       "head_of_household": head, **{k: v.astype(int) for k, v in progs.items()}, "aid_date": aid_date})
    # Real registers have gaps: blank a few cells
    for col, share in [("age", .03), ("sex", .01), ("household_size", .02), ("health_cover", .02)]:
        df.loc[rng.random(n) < share, col] = None
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Wrote {len(df):,} synthetic households to {out}")


if __name__ == "__main__":
    main()
