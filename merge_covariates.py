"""
Populate panel_merged.csv with covariates from old panel_analysis.csv.
New panel (2011-2019, CONUS) overlaps substantially with old panel.
Counties not in old panel get NaN -> filled downstream with medians.
"""
import warnings; warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np

OUTDIR = r"C:\Users\chenyon\Research Paper 2026(1)"

new_panel = pd.read_csv(f"{OUTDIR}/panel_merged.csv", dtype={"GEOID": str})
new_panel["GEOID"] = new_panel["GEOID"].str.zfill(5)
print(f"New panel: {len(new_panel):,} rows, {new_panel['GEOID'].nunique()} counties")
print(f"Cols: {list(new_panel.columns)}")

old_panel = pd.read_csv(f"{OUTDIR}/panel_analysis.csv", dtype={"GEOID": str})
old_panel["GEOID"] = old_panel["GEOID"].str.zfill(5)
print(f"\nOld panel: {len(old_panel):,} rows, {old_panel['GEOID'].nunique()} counties")

# Covariates to carry over (time-varying)
cov_cols = [
    "unemployment_rate", "HPSA_mental_health",
    "median_hh_income", "poverty_rate",
    "share_NH_black", "share_hispanic", "share_AIAN",
    "uninsured_rate",
    "pct_depression", "pct_poor_mh_days",
]
cov_cols = [c for c in cov_cols if c in old_panel.columns]
print(f"\nCarrying over: {cov_cols}")

old_cov = old_panel[["GEOID", "year"] + cov_cols].copy()
old_cov["year"] = old_cov["year"].astype(int)

# How many new-panel counties are covered?
new_geoids = set(new_panel["GEOID"].unique())
old_geoids = set(old_panel["GEOID"].unique())
covered = new_geoids & old_geoids
missing = new_geoids - old_geoids
print(f"\nNew panel counties: {len(new_geoids)}")
print(f"  Covered by old panel: {len(covered)}")
print(f"  Not in old panel (will get NaN): {len(missing)}")

# Restrict old covariates to 2011-2019
old_cov = old_cov[old_cov["year"].between(2011, 2019)]

# Drop any existing cov cols from new panel to avoid duplication
drop_existing = [c for c in cov_cols if c in new_panel.columns]
if drop_existing:
    new_panel.drop(columns=drop_existing, inplace=True)

# Merge
merged = new_panel.merge(old_cov, on=["GEOID", "year"], how="left")
print(f"\nAfter merge: {len(merged):,} rows × {len(merged.columns)} cols")

# Coverage report
fmt = "  {:<28} {:>8} {:>8}"
print(fmt.format("Covariate", "Non-null", "Coverage"))
print("  " + "-"*46)
for c in cov_cols:
    if c not in merged.columns:
        continue
    n   = merged[c].notna().sum()
    pct = n / len(merged) * 100
    print(fmt.format(c, f"{n:,}", f"{pct:.1f}%"))

# Also carry over the static matching vars (county_pop, median_hh_income_2014, pre_fire_flag)
# that came from matching.py — already in new panel_merged via panel_skeleton merge
# Add log_pop and ihs outcomes placeholder columns (built in clean_panel.py)

merged.to_csv(f"{OUTDIR}/panel_merged.csv", index=False)
print(f"\nSaved panel_merged.csv: {len(merged):,} rows × {len(merged.columns)} cols")
print(f"Cols: {list(merged.columns)}")
