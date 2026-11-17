"""Build the numeric household feature table used by models.py (assessed households only).
Usage: python features.py <households.csv> <features.csv>
"""
import sys

import pandas as pd

df = pd.read_csv(sys.argv[1])
d = df[df["social_status"].notna()].copy()
num = lambda c: pd.to_numeric(d[c], errors="coerce").where(lambda x: x >= 0)
flag = lambda cond: cond.astype(float)
out = pd.DataFrame({
    "area": d["area"],
    "age": num("age").where(lambda x: (x >= 15) & (x <= 105)),
    "female": flag(d["sex"] == "F").where(d["sex"].isin(["F", "M"])),
    "children": num("children").where(lambda x: x <= 20),
    "household": num("household_size"),
    "n_disabled": num("n_disabled"),
    "n_chronic": num("n_chronic"),
    "informal": flag(d["work_sector"] == "informal"),
    "no_work": flag(d["work_sector"] == "no_work"),
    "no_coverage": flag(d["health_cover"] == "none"),
    "basic_cover": flag(d["health_cover"] == "basic"),
    "widowed": flag(d["family_status"] == "widowed"),
    "divorced_abandoned": flag(d["family_status"].isin(["divorced", "abandoned", "single_parent"])),
    "single": flag(d["family_status"] == "single"),
    "health_disability": flag(d["health_status"] == "disability"),
    "health_chronic": flag(d["health_status"].isin(["chronic", "serious"])),
    "health_elderly": flag(d["health_status"] == "elderly"),
    "head": flag(d["head_of_household"] == 1),
    "aid_any": flag(d[[c for c in d if c.startswith("program_")]].fillna(0).sum(axis=1) > 0),
    "target": d["social_status"].where(d["social_status"].isin(["very_vulnerable", "vulnerable", "middle"])),
})
out.to_csv(sys.argv[2], index=False)
print(out.shape)
