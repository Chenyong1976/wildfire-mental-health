"""
Compute summary statistics table for the T1 matched panel.
Outputs: summary_stats_table.csv  (used by make_sumstats_docx.py and LaTeX)
"""
import warnings; warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np
from scipy import stats

PANEL = r"C:\Users\chenyon\Research Paper 2026(1)\panel_2015_T1_moderate_1k.csv"
OUT   = r"C:\Users\chenyon\Research Paper 2026(1)\summary_stats_table.csv"

df = pd.read_csv(PANEL, dtype={"GEOID": str}, low_memory=False)
df["GEOID"] = df["GEOID"].str.zfill(5)

# ── Cross-section of county-level invariants (one row per county) ─────────────
county = (df[df["year"] == 2011]
          [["GEOID","treated","BP_NATIONAL_RANK","RUCC2013",
            "BUILDINGS_FRACTION_DE","county_pop_2014","median_hh_income"]]
          .copy())
# pop in thousands, income in thousands
county["pop_k"]    = county["county_pop_2014"] / 1000
county["income_k"] = county["median_hh_income"] / 1000

# pre-fire flag (any qualifying fire before 2015)
pre_flag = (df[df["year"] == 2011][["GEOID","HPSA_mental_health"]].copy()
            .rename(columns={"HPSA_mental_health":"hpsa"}))
county = county.merge(pre_flag, on="GEOID", how="left")

# ── Pre-treatment means (2011-2014, county-level averages) ────────────────────
pre = df[df["year"].between(2011, 2014)].copy()
pre["suicide_rate"]  = pd.to_numeric(pre["suicide_rate"],  errors="coerce")
pre["overdose_rate"] = pd.to_numeric(pre["overdose_rate"], errors="coerce")
pre["unemployment_rate"] = pd.to_numeric(pre["unemployment_rate"], errors="coerce")

pre_means = (pre.groupby("GEOID")
               .agg(pre_suicide  =("suicide_rate",      "mean"),
                    pre_overdose =("overdose_rate",     "mean"),
                    pre_unemp    =("unemployment_rate", "mean"))
               .reset_index())

county = county.merge(pre_means, on="GEOID", how="left")

# ── 2019 outcomes (cross-section) ─────────────────────────────────────────────
post = df[df["year"] == 2019][["GEOID","treated","pct_depression","pct_poor_mh_days"]].copy()
post["pct_depression"]   = pd.to_numeric(post["pct_depression"],   errors="coerce")
post["pct_poor_mh_days"] = pd.to_numeric(post["pct_poor_mh_days"], errors="coerce")

# ── Helper: mean/sd/diff/pval for a variable ──────────────────────────────────
def row_stats(data, var, label, fmt=".2f"):
    t = data.loc[data["treated"] == 1, var].dropna()
    c = data.loc[data["treated"] == 0, var].dropna()
    t_mean, t_sd = t.mean(), t.std()
    c_mean, c_sd = c.mean(), c.std()
    diff  = t_mean - c_mean
    _, pval = stats.ttest_ind(t, c, equal_var=False)
    return {
        "Variable"   : label,
        "T_mean"     : t_mean,
        "T_sd"       : t_sd,
        "T_n"        : len(t),
        "C_mean"     : c_mean,
        "C_sd"       : c_sd,
        "C_n"        : len(c),
        "Diff"       : diff,
        "p_value"    : pval,
        "fmt"        : fmt,
    }

rows = []

# ── Panel A: Matching variables ───────────────────────────────────────────────
rows.append({"Variable": "Panel A: County Characteristics (Pre-Treatment)", "panel_header": True})
rows.append(row_stats(county, "BP_NATIONAL_RANK", "WHP national rank (0–1)",            fmt=".3f"))
rows.append(row_stats(county, "RUCC2013",          "Rural-urban continuum code (1–9)",    fmt=".1f"))
rows.append(row_stats(county, "BUILDINGS_FRACTION_DE", "Share of buildings in direct exposure zone", fmt=".3f"))
rows.append(row_stats(county, "pop_k",             "Population, 2014 (thousands)",        fmt=".1f"))
rows.append(row_stats(county, "income_k",          "Median household income, 2014 ($k)",  fmt=".1f"))
rows.append(row_stats(county, "hpsa",              "Mental health HPSA (0/1)",            fmt=".2f"))

# ── Panel B: Pre-treatment outcomes ──────────────────────────────────────────
rows.append({"Variable": "Panel B: Pre-Treatment Outcomes (2011–2014 means)", "panel_header": True})
rows.append(row_stats(county, "pre_suicide",  "Suicide rate (per 100,000)",   fmt=".1f"))
rows.append(row_stats(county, "pre_overdose", "Overdose rate (per 100,000)",  fmt=".1f"))
rows.append(row_stats(county, "pre_unemp",    "Unemployment rate (%)",        fmt=".1f"))

# ── Panel C: 2019 outcomes ────────────────────────────────────────────────────
rows.append({"Variable": "Panel C: Post-Treatment Outcomes (2019)", "panel_header": True})
rows.append(row_stats(post, "pct_depression",   "Depression prevalence (%)",       fmt=".1f"))
rows.append(row_stats(post, "pct_poor_mh_days", "Poor mental health days (pct 14+)", fmt=".1f"))

# ── Print & save ──────────────────────────────────────────────────────────────
result = pd.DataFrame(rows)
result.to_csv(OUT, index=False, encoding="utf-8")
for _, r in result.iterrows():
    if r.get("panel_header"):
        print(f"\n{r['Variable']}")
    else:
        tm = f"{r['T_mean']:.2f}" if pd.notna(r.get('T_mean')) else ""
        cm = f"{r['C_mean']:.2f}" if pd.notna(r.get('C_mean')) else ""
        d  = f"{r['Diff']:.2f}"   if pd.notna(r.get('Diff'))   else ""
        p  = f"{r['p_value']:.3f}" if pd.notna(r.get('p_value')) else ""
        print(f"  {str(r['Variable']):<52} T={tm}  C={cm}  diff={d}  p={p}")
print(f"\nSaved: {OUT}")
