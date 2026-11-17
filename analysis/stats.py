"""Aggregate statistics of a household aid register. Outputs contain no row-level data.
Usage: python stats.py <households.csv> <out_dir>
"""
import csv
import json
import sys

import numpy as np
import pandas as pd

PROGRAMS = ["program_a", "program_b", "program_c", "program_d", "program_e", "program_f"]
MIN_AREA = 50  # areas with fewer households are left out of the area table

src, out = sys.argv[1:3]
df = pd.read_csv(src)
progs = [p for p in PROGRAMS if p in df]
Y = {p: df[p].fillna(0).astype(int) == 1 for p in progs}
nprog = sum(v.astype(int) for v in Y.values())
anyaid = nprog > 0
assessed = df["social_status"].notna()
social, health, cover = df["social_status"], df["health_status"], df["health_cover"]
family, sex = df["family_status"], df["sex"]
women = sex == "F"
vv = social == "very_vulnerable"
fragile = assessed & (vv | health.isin(["disability", "serious", "chronic"]))
nocover = cover == "none"
middle = social.isin(["middle", "well_off"])


def w(name, header, rows):
    with open(f"{out}/{name}", "w", newline="") as f:
        c = csv.writer(f)
        c.writerow(header)
        c.writerows(rows)


N = len(df)
# Lorenz curve on the number of programmes per household
cnt = np.sort(nprog.to_numpy())
cum = np.cumsum(cnt) / max(cnt.sum(), 1)
pts = [(0.0, 0.0)] + [(round(q, 3), round(float(cum[int(q * N) - 1]), 4)) for q in np.linspace(0.05, 1, 20)]
gini = 1 - 2 * np.trapezoid([p[1] for p in pts], [p[0] for p in pts])
w("lorenz.csv", ["households_share", "aid_share"], pts)

kp = dict(records=N, assessed=int(assessed.sum()), any_aid=int(anyaid.sum()), no_aid=int((~anyaid).sum()),
          multi_aid=int((nprog >= 2).sum()), three_plus=int((nprog >= 3).sum()),
          fragile=int(fragile.sum()), fragile_no_aid=int((fragile & ~anyaid).sum()),
          fragile_no_cover=int((fragile & nocover).sum()),
          middle_with_aid=int((middle & anyaid).sum()), middle=int(middle.sum()),
          missing_assessment=int((~assessed).sum()), missing_age=int(pd.to_numeric(df["age"], errors="coerce").isna().sum()),
          missing_sex=int(sex.isna().sum()), women_heads=int((women & assessed).sum()), gini=round(float(gini), 3),
          vv_share=round(float(vv[assessed].mean()), 4))
w("kpis.csv", ["metric", "value"], kp.items())

w("programs.csv", ["program", "households"], sorted(((k, int(v.sum())) for k, v in Y.items()), key=lambda x: -x[1]))

# Programme combinations among households with two or more programmes
lab = pd.DataFrame(Y).apply(lambda r: "+".join(k for k in progs if r[k]), axis=1)
w("combos.csv", ["combo", "households"], lab[nprog >= 2].value_counts().head(8).items())

# Profile of assessed households, one block per dimension
rows = []
for dim, s in [("social", social), ("health", health), ("coverage", cover), ("family", family), ("sector", df["work_sector"]), ("sex", sex)]:
    for k, v in s[assessed].value_counts().items():
        rows.append((dim, k, int(v)))
ages = pd.to_numeric(df["age"], errors="coerce")
ages = ages[assessed & (ages >= 15) & (ages <= 105)]
bins = pd.cut(ages, [15, 25, 35, 45, 55, 65, 75, 106], right=False, labels=["15-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75+"])
rows += [("age", k, int(v)) for k, v in bins.value_counts().sort_index().items()]
hh = pd.to_numeric(df["household_size"], errors="coerce")
hh = hh[assessed & (hh >= 1)]
rows += [("household", str(k) if k < 10 else "10+", int((hh == k).sum() if k < 10 else (hh >= 10).sum())) for k in range(1, 11)]
rows += [("programs", str(k), int(v)) for k, v in nprog.value_counts().sort_index().items()]
w("profile.csv", ["dimension", "category", "households"], rows)

# Gender lens (assessed households)
G = {"women_heads": assessed & women, "men_heads": assessed & (sex == "M"), "widows": assessed & women & (family == "widowed"),
     "divorced_abandoned_women": assessed & women & family.isin(["divorced", "abandoned"]),
     "single_parents": assessed & (family == "single_parent")}
w("gender.csv", ["group", "households", "aid_any", "multi", "very_vulnerable", "no_cover"],
  [(g, int(m.sum()), round(float(anyaid[m].mean()), 4), round(float((nprog >= 2)[m].mean()), 4),
    round(float(vv[m].mean()), 4), round(float(nocover[m].mean()), 4)) for g, m in G.items() if m.any()])

# Area alert table: coverage, need and how complete the records are
key = ["age", "sex", "social_status", "health_status", "health_cover", "household_size"]
filled = df[key].notna().mean(axis=1)
arows = []
for a, s in df.groupby("area"):
    i = s.index
    if len(s) < MIN_AREA:
        continue
    arows.append(dict(area=a, households=len(s), assessed=int(assessed[i].sum()),
                      any_aid=int(anyaid[i].sum()), no_aid=int((~anyaid[i]).sum()), multi=int((nprog[i] >= 2).sum()),
                      very_vuln=int(vv[i].sum()), fragile=int(fragile[i].sum()),
                      fragile_no_aid=int((fragile & ~anyaid)[i].sum()), fragile_no_cover=int((fragile & nocover)[i].sum()),
                      women=int(women[i].sum()), completeness=round(float(filled[i].mean()), 4),
                      programs_per_hh=round(float(nprog[i].mean()), 3)))
am = pd.DataFrame(arows)
need = am["fragile"] / am["assessed"].replace(0, np.nan)
z = lambda s: (s - s.mean()) / s.std()
am["need_index"] = need.round(4)
am["gap"] = (z(am["programs_per_hh"]) - z(need)).round(3)  # below 0: less aid than the need suggests
am.sort_values("households", ascending=False).to_csv(f"{out}/areas.csv", index=False)

# First aid received, per day
if "aid_date" in df:
    dd = pd.to_datetime(df["aid_date"], errors="coerce").dropna()
    w("daily.csv", ["date", "households"], [(k.strftime("%Y-%m-%d"), int(v)) for k, v in dd.value_counts().sort_index().items()])

print(json.dumps(kp))
