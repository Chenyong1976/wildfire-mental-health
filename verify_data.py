"""
Data verification audit — checks all sources before DiD estimation.
"""
import warnings; warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np
import os

OUTDIR = r"C:\Users\chenyon\Research Paper 2026(1)"
RAWDIR = r"C:\Users\chenyon\Research Paper 2026(1)\data\raw"
YEARS  = list(range(2011, 2020))

panel = pd.read_csv(f"{OUTDIR}/panel_skeleton.csv", dtype={"GEOID": str})
panel["GEOID"] = panel["GEOID"].str.zfill(5)
target_geoids = set(panel["GEOID"].unique())
n_panel = 1005 * 12   # expected obs

print("=" * 65)
print("DATA AUDIT — Wildfire Mental Health Panel")
print("=" * 65)

# ── 1. Panel skeleton ────────────────────────────────────────────
print("\n[1] Panel skeleton")
skel = pd.read_csv(f"{OUTDIR}/panel_skeleton.csv", dtype={"GEOID": str})
print(f"    Rows:     {len(skel):,}  (expected {n_panel:,})")
print(f"    Counties: {skel['GEOID'].nunique()}  (expected 1,005)")
print(f"    Years:    {sorted(skel['year'].unique())}")
print(f"    Treated:  {(skel['treated']==1).sum()//12} counties")
print(f"    Control:  {(skel['treated']==0).sum()//12} counties")

# ── 2. Covariates ────────────────────────────────────────────────
print("\n[2] Covariates in panel_merged.csv")
merged = pd.read_csv(f"{OUTDIR}/panel_merged.csv", dtype={"GEOID": str})
merged["GEOID"] = merged["GEOID"].str.zfill(5)

cov_cols = {
    "unemployment_rate":  "BLS LAUS",
    "HPSA_mental_health": "HRSA HPSA",
    "median_hh_income":   "ACS median income",
    "poverty_rate":       "ACS poverty rate",
    "population":         "ACS population",
    "share_NH_black":     "ACS race (NH Black)",
    "share_hispanic":     "ACS race (Hispanic)",
    "pct_depression":     "CDC PLACES depression",
    "pct_poor_mh_days":   "CDC PLACES poor MH days",
}
fmt = "    {:<30} {:>7} ({:>5.1f}%)"
for col, label in cov_cols.items():
    if col in merged.columns:
        n = merged[col].notna().sum()
        pct = n / len(merged) * 100
        status = "OK" if pct > 80 else ("PARTIAL" if pct > 10 else "MISSING")
        print(fmt.format(label, f"{n:,}", pct) + f"  [{status}]")
    else:
        print(f"    {label:<30}  NOT IN PANEL")

# ── 3. WONDER TSV files ──────────────────────────────────────────
print("\n[3] CDC WONDER mortality files")

def parse_wonder_tsv(fpath):
    """Parse WONDER tab-delimited export; return clean DataFrame."""
    if not os.path.exists(fpath):
        return None, f"FILE NOT FOUND: {fpath}"

    try:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except Exception as e:
        return None, str(e)

    lines = raw.split("\n")

    # Find data block: starts at header row containing "County" and "Deaths"
    # Ends at first line starting with "---" or "Notes" or "Total"
    header_idx = None
    end_idx = len(lines)
    for i, line in enumerate(lines):
        if header_idx is None:
            if ("County" in line or "county" in line) and ("Deaths" in line or "deaths" in line):
                header_idx = i
        else:
            stripped = line.strip().strip('"')
            if stripped.startswith("---") or stripped.lower().startswith("notes") or stripped.lower().startswith("total"):
                end_idx = i
                break

    if header_idx is None:
        # Try: first line with >= 5 tab-separated fields that looks like a header
        for i, line in enumerate(lines):
            parts = line.split("\t")
            if len(parts) >= 5 and any(k in line for k in ["County","Year","Deaths","Population"]):
                header_idx = i
                break

    if header_idx is None:
        return None, f"Could not find data header. First 3 lines: {lines[:3]}"

    data_text = "\n".join(lines[header_idx:end_idx])
    try:
        df = pd.read_csv(
            pd.io.common.StringIO(data_text),
            sep="\t", dtype=str, na_values=["", "NA"]
        )
    except Exception as e:
        return None, f"CSV parse error: {e}"

    df.columns = [c.strip().strip('"') for c in df.columns]
    # Drop empty rows
    df = df.dropna(how="all")

    return df, "OK"


def standardize_wonder(df, outcome_name):
    """Map WONDER columns to GEOID, year, deaths, population."""
    cols = list(df.columns)

    # Find county FIPS column (usually "County Code")
    fips_c = next((c for c in cols if "County Code" in c), None)
    if fips_c is None:
        fips_c = next((c for c in cols if c.lower() in ("county code","fips","geoid")), None)

    # Find year column
    year_c = next((c for c in cols if c == "Year Code"), None)
    if year_c is None:
        year_c = next((c for c in cols if "Year" in c), None)

    # Find deaths
    death_c = next((c for c in cols if "Deaths" in c), None)

    # Find population
    pop_c = next((c for c in cols if "Population" in c), None)

    missing = [n for n, c in [("FIPS",fips_c),("Year",year_c),("Deaths",death_c)] if c is None]
    if missing:
        return None, f"Missing cols: {missing}. Available: {cols[:10]}"

    out = pd.DataFrame()
    out["GEOID"]  = df[fips_c].astype(str).str.strip().str.zfill(5)
    out["year"]   = pd.to_numeric(df[year_c].astype(str).str.strip(), errors="coerce")
    raw_deaths    = df[death_c].astype(str).str.strip()
    out["deaths"] = pd.to_numeric(
        raw_deaths.replace({"Suppressed": np.nan, "Missing": np.nan,
                            "Not Applicable": np.nan, "Unreliable": np.nan}),
        errors="coerce"
    )
    out["suppressed"] = raw_deaths.str.lower() == "suppressed"
    if pop_c:
        out["population"] = pd.to_numeric(
            df[pop_c].astype(str).str.replace(",","").str.strip(), errors="coerce"
        )
    out = out.rename(columns={"deaths": f"{outcome_name}_deaths"})
    return out, "OK"


wonder_files = {
    "suicide":  ["wonder_suicide_2011_2019.tsv",  "wonder_suicide_2021_2023.tsv"],
    "overdose": ["wonder_overdose_2011_2019.tsv", "wonder_overdose_2021_2023.tsv"],
}

wonder_dfs = {}
all_wonder_ok = True

for outcome, filenames in wonder_files.items():
    chunks = []
    file_ok = True
    for fn in filenames:
        fpath = os.path.join(RAWDIR, fn)
        df_raw, status = parse_wonder_tsv(fpath)
        if df_raw is None:
            print(f"    {fn}: {status}")
            file_ok = False
            all_wonder_ok = False
            continue
        df_std, status2 = standardize_wonder(df_raw, outcome)
        if df_std is None:
            print(f"    {fn}: parse OK but standardize failed — {status2}")
            print(f"      Columns found: {list(df_raw.columns)}")
            file_ok = False
            all_wonder_ok = False
            continue
        # Filter to panel years and counties
        df_std = df_std[df_std["year"].isin(YEARS) & df_std["GEOID"].isin(target_geoids)]
        chunks.append(df_std)
        print(f"    {fn}: {len(df_std):,} county-years, years {sorted(df_std['year'].dropna().unique().astype(int).tolist())}")

    if chunks:
        combined = pd.concat(chunks, ignore_index=True)
        # Deduplicate (overlapping year ranges)
        combined = combined.sort_values(["GEOID","year"]).drop_duplicates(["GEOID","year"])
        wonder_dfs[outcome] = combined

        n_obs   = len(combined)
        n_supp  = combined["suppressed"].sum()
        n_total = 1005 * 12
        yrs     = sorted(combined["year"].dropna().unique().astype(int).tolist())
        cty     = combined["GEOID"].nunique()
        d_col   = f"{outcome}_deaths"
        mean_d  = combined[d_col].mean()

        print(f"\n    {outcome.upper()} combined:")
        print(f"      County-years in panel: {n_obs:,} / {n_total:,}  ({n_obs/n_total:.1%})")
        print(f"      Counties covered:      {cty}")
        print(f"      Years covered:         {yrs}")
        print(f"      Suppressed (<10):      {n_supp:,}  ({n_supp/n_obs:.1%})")
        print(f"      Mean deaths/county-yr: {mean_d:.2f}")

        # Balance check at baseline (2011-2014)
        base = combined[combined["year"].between(2011,2014)].merge(
            panel[["GEOID","treated"]].drop_duplicates(), on="GEOID", how="left"
        )
        t_m = base.loc[base["treated"]==1, d_col].mean()
        c_m = base.loc[base["treated"]==0, d_col].mean()
        print(f"      Baseline mean (2011-2014): treated={t_m:.2f}, control={c_m:.2f}")

# ── 4. Save WONDER into panel ────────────────────────────────────
if wonder_dfs:
    print("\n[4] Merging WONDER outcomes into panel_merged.csv")
    merged = pd.read_csv(f"{OUTDIR}/panel_merged.csv", dtype={"GEOID": str})
    merged["GEOID"] = merged["GEOID"].str.zfill(5)

    # Drop old WONDER cols if present
    drop_cols = [c for c in merged.columns if any(
        x in c for x in ["suicide","overdose"])]
    if drop_cols:
        merged.drop(columns=drop_cols, inplace=True)

    for outcome, df_w in wonder_dfs.items():
        df_w["year"] = df_w["year"].astype(int)
        keep = ["GEOID","year", f"{outcome}_deaths"]
        if "population" in df_w.columns:
            keep.append("population")
        df_merge = df_w[[c for c in keep if c in df_w.columns]].copy()
        if outcome == "overdose" and "population" in df_merge.columns:
            df_merge = df_merge.rename(columns={"population": "county_population"})
        merged = merged.merge(df_merge, on=["GEOID","year"], how="left")

    merged.to_csv(f"{OUTDIR}/panel_merged.csv", index=False)
    print(f"    panel_merged.csv: {len(merged):,} rows × {len(merged.columns)} cols")
    print(f"    Columns: {list(merged.columns)}")

# ── 5. Final summary ─────────────────────────────────────────────
print("\n[5] Final outcome coverage in panel_merged.csv")
merged = pd.read_csv(f"{OUTDIR}/panel_merged.csv", dtype={"GEOID": str})
outcome_cols = [c for c in merged.columns if any(
    x in c for x in ["suicide_deaths","overdose_deaths","pct_depression","pct_poor_mh"])]

fmt2 = "    {:<30} {:>10} {:>10} {:>10}"
print(fmt2.format("Column", "Non-null", "Coverage", "Mean"))
print("    " + "-"*58)
for col in outcome_cols:
    if col not in merged.columns: continue
    n    = merged[col].notna().sum()
    pct  = n / len(merged) * 100
    mean = merged[col].mean()
    print(fmt2.format(col, f"{n:,}", f"{pct:.1f}%", f"{mean:.3f}"))

print("\n[6] Cohort distribution (treated counties)")
t = merged[merged["treated"]==1].drop_duplicates("GEOID")
if "cohort_g" in t.columns:
    print(t["cohort_g"].value_counts().sort_index().to_string())

print("\n" + "=" * 65)
print("AUDIT COMPLETE")
print("=" * 65)

# Check readiness
issues = []
if "suicide_deaths" not in merged.columns or merged["suicide_deaths"].notna().sum() == 0:
    issues.append("suicide_deaths missing or all null")
if "overdose_deaths" not in merged.columns or merged["overdose_deaths"].notna().sum() == 0:
    issues.append("overdose_deaths missing or all null")
if "pct_depression" not in merged.columns or merged["pct_depression"].notna().sum() == 0:
    issues.append("pct_depression missing or all null")

if issues:
    print("\nISSUES TO RESOLVE BEFORE STEP 3:")
    for iss in issues:
        print(f"  - {iss}")
else:
    print("\nAll outcome columns present. Ready for Step 3 (DiD estimation).")
