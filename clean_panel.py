"""
Clean up panel_merged.csv: resolve duplicate population columns,
fill WONDER zeros, and produce the analysis-ready panel.
"""
import warnings; warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np

OUTDIR = r"C:\Users\chenyon\Research Paper 2026(1)"
YEARS  = list(range(2011, 2020))

merged = pd.read_csv(f"{OUTDIR}/panel_merged.csv", dtype={"GEOID": str})
merged["GEOID"] = merged["GEOID"].str.zfill(5)

print(f"Before: {len(merged):,} rows × {len(merged.columns)} cols")
print(f"Columns: {list(merged.columns)}")

# ── Resolve duplicate population columns ────────────────────────
# population_x = ACS population (preferred, ~77% coverage)
# population_y = WONDER suicide population
# county_population = WONDER overdose population
# Coalesce: ACS > WONDER suicide pop > WONDER overdose pop
pop_cols = [c for c in merged.columns if "population" in c.lower()]
print(f"\nPopulation columns found: {pop_cols}")

for col in pop_cols:
    merged[col] = pd.to_numeric(merged[col], errors="coerce")

merged["county_pop"] = merged.get("population_x", np.nan)
for fallback in ["population_y", "county_population"]:
    if fallback in merged.columns:
        merged["county_pop"] = merged["county_pop"].fillna(merged[fallback])

# Drop the raw duplicates
merged.drop(columns=[c for c in pop_cols], inplace=True, errors="ignore")

print(f"county_pop: {merged['county_pop'].notna().sum():,} non-null ({merged['county_pop'].notna().mean():.1%})")
print(f"county_pop range: {merged['county_pop'].min():,.0f} – {merged['county_pop'].max():,.0f}")

# ── Fill WONDER zeros ────────────────────────────────────────────
# Rows with no WONDER data = small counties where deaths < 10
# Treat as 0 for Poisson regression (these are genuine structural zeros)
# Flag them so we can run sensitivity checks (zero-inflated vs. basic Poisson)
merged["suicide_suppressed"]  = merged["suicide_deaths"].isna().astype(int)
merged["overdose_suppressed"] = merged["overdose_deaths"].isna().astype(int)
merged["suicide_deaths"]  = merged["suicide_deaths"].fillna(0)
merged["overdose_deaths"] = merged["overdose_deaths"].fillna(0)

print(f"\nAfter zero-fill:")
print(f"  suicide_deaths:  mean={merged['suicide_deaths'].mean():.2f}, "
      f"zeros={( merged['suicide_deaths']==0).mean():.1%}")
print(f"  overdose_deaths: mean={merged['overdose_deaths'].mean():.2f}, "
      f"zeros={(merged['overdose_deaths']==0).mean():.1%}")

# ── Compute per-100k rates (for descriptive use only; DiD uses counts + offset)
merged["suicide_rate"]  = np.where(
    merged["county_pop"] > 0,
    merged["suicide_deaths"]  / merged["county_pop"] * 100_000,
    np.nan
)
merged["overdose_rate"] = np.where(
    merged["county_pop"] > 0,
    merged["overdose_deaths"] / merged["county_pop"] * 100_000,
    np.nan
)

# ── Final column order ───────────────────────────────────────────
id_cols     = ["GEOID","year","NAME","STATEFP"]
design_cols = ["treated","match_set","WHP_quintile","cohort_g","event_time",
               "post","surprise_fire","first_fire_yr"]
geo_cols    = ["BP_NATIONAL_RANK","RUCC2013","BUILDINGS_FRACTION_DE"]
cov_cols    = ["unemployment_rate","HPSA_mental_health","median_hh_income",
               "poverty_rate","county_pop","share_NH_black","share_hispanic","share_AIAN"]
outcome_cols = ["suicide_deaths","suicide_rate","suicide_suppressed",
                "overdose_deaths","overdose_rate","overdose_suppressed",
                "pct_depression","pct_poor_mh_days"]

all_ordered = id_cols + design_cols + geo_cols + cov_cols + outcome_cols
final_cols  = [c for c in all_ordered if c in merged.columns]
extra_cols  = [c for c in merged.columns if c not in final_cols]
merged = merged[final_cols + extra_cols]

merged.to_csv(f"{OUTDIR}/panel_analysis.csv", index=False)
print(f"\nSaved panel_analysis.csv: {len(merged):,} rows × {len(merged.columns)} cols")

# ── Final summary ────────────────────────────────────────────────
print("\n=== FINAL PANEL SUMMARY ===")
print(f"Observations:  {len(merged):,}")
print(f"Counties:      {merged['GEOID'].nunique()} ({(merged['treated']==1).sum()//12} treated, {(merged['treated']==0).sum()//12} control)")
print(f"Years:         {sorted(merged['year'].unique().tolist())}")

print("\nCohort sizes (treated counties):")
t = merged[merged["treated"]==1].drop_duplicates("GEOID")
print(t["cohort_g"].value_counts().sort_index().rename("counties").to_string())

print("\nOutcome means by treatment status (all years):")
fmt = "  {:<25} {:>10} {:>10}"
print(fmt.format("Outcome", "Treated", "Control"))
print("  " + "-"*45)
for col in ["suicide_deaths","suicide_rate","overdose_deaths","overdose_rate",
            "pct_depression","pct_poor_mh_days"]:
    if col not in merged.columns: continue
    t_m = merged.loc[merged["treated"]==1, col].mean()
    c_m = merged.loc[merged["treated"]==0, col].mean()
    print(fmt.format(col, f"{t_m:.2f}", f"{c_m:.2f}"))

print("\nCovariate coverage:")
fmt2 = "  {:<25} {:>10}"
for col in cov_cols:
    if col not in merged.columns: continue
    n = merged[col].notna().sum()
    print(fmt2.format(col, f"{n/len(merged):.1%}"))
