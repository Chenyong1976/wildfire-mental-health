"""
Step 2: Build county × year panel (2011-2019, 2021-2023).

Outputs:
  panel_skeleton.csv       — county × year scaffold with treatment/cohort vars
  acs_covariates.csv       — ACS 5-year estimates (income, poverty, pop, race)
  bls_laus_covariates.csv  — BLS LAUS county unemployment
  panel_merged.csv         — panel skeleton + all available covariates
  summary_stats.csv        — summary statistics by treatment group
"""

import warnings; warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np
import requests
import time
import os
import openpyxl
import xlrd

BASE   = r"C:\Users\chenyon\Research Paper 2026(1)\data\raw"
OUTDIR = r"C:\Users\chenyon\Research Paper 2026(1)"
YEARS  = list(range(2011, 2020))  # 2011-2019; 2020 COVID excluded; 2021-2023 dropped

# ─── 1. Load matched county pairs ─────────────────────────────────────────────
print("=== Loading matched county pairs ===")
matched = pd.read_csv(
    f"{OUTDIR}/matched_county_pairs.csv",
    dtype={"treated_GEOID": str, "control_GEOID": str}
)
matched["treated_GEOID"] = matched["treated_GEOID"].str.zfill(5)
matched["control_GEOID"]  = matched["control_GEOID"].str.zfill(5)

# Unique treated counties
treated_df = (
    matched[["treated_GEOID","treated_NAME","treated_STATE",
             "treated_WHP_quintile","treated_first_fire_yr",
             "treated_WHP_rank","treated_RUCC","treated_BldDE"]]
    .drop_duplicates("treated_GEOID")
    .rename(columns={
        "treated_GEOID": "GEOID", "treated_NAME": "NAME", "treated_STATE": "STATEFP",
        "treated_WHP_quintile": "WHP_quintile", "treated_first_fire_yr": "first_fire_yr",
        "treated_WHP_rank": "BP_NATIONAL_RANK", "treated_RUCC": "RUCC2013",
        "treated_BldDE": "BUILDINGS_FRACTION_DE"
    })
)
treated_df["treated"]  = 1
treated_df["match_set"] = "treated"

# Unique control counties (include both primary and secondary, deduplicated)
ctrl_df = (
    matched[["control_GEOID","control_NAME","control_STATE",
             "control_WHP_rank","control_RUCC","control_BldDE",
             "treated_WHP_quintile"]]
    .drop_duplicates("control_GEOID")
    .rename(columns={
        "control_GEOID": "GEOID", "control_NAME": "NAME", "control_STATE": "STATEFP",
        "treated_WHP_quintile": "WHP_quintile",
        "control_WHP_rank": "BP_NATIONAL_RANK",
        "control_RUCC": "RUCC2013",
        "control_BldDE": "BUILDINGS_FRACTION_DE"
    })
)
ctrl_df["treated"]       = 0
ctrl_df["first_fire_yr"] = np.nan
ctrl_df["match_set"]     = "control"

# Exclude any control county that is also a treated county (rare cross-sample overlap)
ctrl_df = ctrl_df[~ctrl_df["GEOID"].isin(treated_df["GEOID"])]

counties = pd.concat([treated_df, ctrl_df], ignore_index=True)
counties["GEOID"]  = counties["GEOID"].str.zfill(5)
counties["STATEFP"] = counties["STATEFP"].astype(str).str.zfill(2)

print(f"  Treated counties : {(counties['treated']==1).sum()}")
print(f"  Control counties : {(counties['treated']==0).sum()}")
print(f"  Total counties   : {len(counties)}")

# ─── 2. Build county × year scaffold ──────────────────────────────────────────
print("\n=== Building panel skeleton ===")
idx = pd.MultiIndex.from_product([counties["GEOID"], YEARS], names=["GEOID","year"])
panel = pd.DataFrame(index=idx).reset_index()
panel = panel.merge(counties, on="GEOID", how="left")

# Treatment timing variables
panel["first_fire_yr"] = pd.to_numeric(panel["first_fire_yr"], errors="coerce")
panel["event_time"]    = np.where(
    panel["treated"] == 1,
    panel["year"] - panel["first_fire_yr"],
    np.nan
)
# Cohort g for Callaway-Sant'Anna (0 = never-treated)
panel["cohort_g"] = np.where(panel["treated"] == 1, panel["first_fire_yr"], 0).astype(float)

# Post-treatment indicator
panel["post"] = np.where(
    (panel["treated"] == 1) & (panel["event_time"] >= 0), 1, 0
)

# "Surprise fire" subsample flag (Q2-Q3 treated counties)
panel["surprise_fire"] = np.where(
    (panel["treated"] == 1) & (panel["WHP_quintile"].isin([2, 3])), 1, 0
)

panel_out = f"{OUTDIR}/panel_skeleton.csv"
panel.to_csv(panel_out, index=False)
print(f"  Saved: panel_skeleton.csv  ({len(panel):,} rows × {len(panel.columns)} cols)")

print(f"  Panel years  : {sorted(panel['year'].unique())}")
print(f"  Treated obs  : {(panel['treated']==1).sum():,}")
print(f"  Control obs  : {(panel['treated']==0).sum():,}")
cohort_dist = panel[panel['treated']==1].groupby('cohort_g')['GEOID'].nunique()
print(f"\n  Cohort distribution (treated counties by first fire year):")
print(cohort_dist.to_string())

# ─── 3. ACS 5-year estimates via Census API ────────────────────────────────────
# Variables:
#   B19013_001E  median household income
#   B17001_002E  population below poverty level
#   B17001_001E  universe for poverty ratio
#   B01003_001E  total population
#   B03002_001E  total (race/ethnicity denominator)
#   B03002_003E  NH White alone
#   B03002_004E  NH Black alone
#   B03002_012E  Hispanic/Latino
#   B03002_005E  NH American Indian/AK Native
#   B27010_017E  under 18 uninsured (crude insurance proxy)
#   B27010_033E  18-34 uninsured
#   B27010_050E  35-64 uninsured
#   B27010_066E  65+ uninsured

ACS_VARS = [
    "B19013_001E",  # median HH income
    "B17001_002E",  # below poverty
    "B17001_001E",  # poverty denom
    "B01003_001E",  # population
    "B03002_001E",  # race denom
    "B03002_003E",  # NH White
    "B03002_004E",  # NH Black
    "B03002_012E",  # Hispanic
    "B03002_005E",  # AIAN
    "B27010_017E",  # uninsured <18
    "B27010_033E",  # uninsured 18-34
    "B27010_050E",  # uninsured 35-64
    "B27010_066E",  # uninsured 65+
]

# ACS 5-year data years available: 2009 onward
# For year t, ACS 5-year vintage t covers t-4 to t
# Available: 2011-2023 (2022 released Dec 2023; 2023 released Dec 2024)
ACS_YEARS = [y for y in YEARS if y <= 2023]

def fetch_acs_state(state_fips, year, var_list):
    """Fetch ACS 5-year county data for one state and year."""
    vars_str = ",".join(["NAME"] + var_list)
    url = (
        f"https://api.census.gov/data/{year}/acs/acs5"
        f"?get={vars_str}&for=county:*&in=state:{state_fips}"
    )
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            data = r.json()
            cols = data[0]
            rows = data[1:]
            df = pd.DataFrame(rows, columns=cols)
            df["GEOID"] = df["state"].str.zfill(2) + df["county"].str.zfill(3)
            df["year"] = year
            return df[["GEOID","year"] + [v for v in var_list if v in df.columns]]
        else:
            return None
    except Exception:
        return None

print("\n=== Downloading ACS 5-year estimates ===")
print("  (downloading county data by state; this may take several minutes)")

target_states = counties["STATEFP"].unique().tolist()
target_geoids = set(counties["GEOID"].tolist())

acs_chunks = []
fail_count  = 0
total_calls = len(target_states) * len(ACS_YEARS)
done_calls  = 0

for state in sorted(target_states):
    for yr in ACS_YEARS:
        df_s = fetch_acs_state(state, yr, ACS_VARS)
        done_calls += 1
        if df_s is not None:
            df_s = df_s[df_s["GEOID"].isin(target_geoids)]
            if len(df_s) > 0:
                acs_chunks.append(df_s)
        else:
            fail_count += 1
        if done_calls % 50 == 0:
            print(f"  Progress: {done_calls}/{total_calls} calls ({fail_count} failed)")
        time.sleep(0.05)  # gentle rate limiting

if acs_chunks:
    acs_raw = pd.concat(acs_chunks, ignore_index=True)
    for v in ACS_VARS:
        if v in acs_raw.columns:
            acs_raw[v] = pd.to_numeric(acs_raw[v], errors="coerce").replace(-666666666, np.nan)

    # Derived variables
    acs_raw["poverty_rate"]     = acs_raw["B17001_002E"] / acs_raw["B17001_001E"]
    acs_raw["share_NH_white"]   = acs_raw["B03002_003E"] / acs_raw["B03002_001E"]
    acs_raw["share_NH_black"]   = acs_raw["B03002_004E"] / acs_raw["B03002_001E"]
    acs_raw["share_hispanic"]   = acs_raw["B03002_012E"] / acs_raw["B03002_001E"]
    acs_raw["share_AIAN"]       = acs_raw["B03002_005E"] / acs_raw["B03002_001E"]
    acs_raw["uninsured_count"]  = (
        acs_raw["B27010_017E"].fillna(0) + acs_raw["B27010_033E"].fillna(0) +
        acs_raw["B27010_050E"].fillna(0) + acs_raw["B27010_066E"].fillna(0)
    )
    acs_raw["uninsured_rate"] = acs_raw["uninsured_count"] / acs_raw["B01003_001E"]

    acs_out = acs_raw[["GEOID","year","B19013_001E","poverty_rate","B01003_001E",
                        "share_NH_white","share_NH_black","share_hispanic",
                        "share_AIAN","uninsured_rate"]].rename(columns={
        "B19013_001E": "median_hh_income",
        "B01003_001E": "population"
    })
    acs_out.to_csv(f"{OUTDIR}/acs_covariates.csv", index=False)
    print(f"\n  Saved: acs_covariates.csv  ({len(acs_out):,} rows, {fail_count} failed API calls)")
else:
    print(f"\n  WARNING: ACS download failed ({fail_count} errors). acs_covariates.csv not written.")
    acs_out = pd.DataFrame()

# ─── 4. BLS LAUS county unemployment ──────────────────────────────────────────
print("\n=== Downloading BLS LAUS county unemployment ===")
LAUS_URL = "https://download.bls.gov/pub/time.series/la/la.data.64.County"
try:
    r = requests.get(LAUS_URL, timeout=120, headers={"User-Agent": "research/1.0"})
    if r.status_code == 200:
        from io import StringIO
        laus_raw = pd.read_csv(
            StringIO(r.text), sep="\t",
            names=["series_id","year","period","value","footnote"],
            skiprows=1, dtype={"series_id": str, "value": str}
        )
        # series_id format: LAUCN<5-digit FIPS>0000000000003 (unemployment rate type=3)
        # type code: 3=unemployment rate, 4=unemployment count, 5=employment, 6=labor force
        laus_raw = laus_raw[laus_raw["series_id"].str.endswith("3")]
        laus_raw["GEOID"]  = laus_raw["series_id"].str[5:10]
        laus_raw["value"]  = pd.to_numeric(laus_raw["value"].str.strip(), errors="coerce")
        # Annual: period = M13 (annual average)
        laus_ann = laus_raw[laus_raw["period"].str.strip() == "M13"].copy()
        laus_ann["year"]   = pd.to_numeric(laus_ann["year"], errors="coerce").astype(int)
        laus_ann = laus_ann[
            laus_ann["GEOID"].isin(target_geoids) &
            laus_ann["year"].isin(YEARS)
        ][["GEOID","year","value"]].rename(columns={"value": "unemployment_rate"})
        laus_ann.to_csv(f"{OUTDIR}/bls_laus_covariates.csv", index=False)
        print(f"  Saved: bls_laus_covariates.csv  ({len(laus_ann):,} rows)")
    else:
        print(f"  WARNING: BLS LAUS returned HTTP {r.status_code}")
        laus_ann = pd.DataFrame()
except Exception as e:
    print(f"  WARNING: BLS LAUS download failed: {e}")
    laus_ann = pd.DataFrame()

# ─── 5. Merge into unified panel ──────────────────────────────────────────────
print("\n=== Merging into panel_merged.csv ===")
panel_merged = panel.copy()

if len(acs_out) > 0:
    panel_merged = panel_merged.merge(acs_out, on=["GEOID","year"], how="left")
    print(f"  ACS merge: {panel_merged['median_hh_income'].notna().sum():,} non-null income obs")

if "unemployment_rate" in locals() and len(laus_ann) > 0:
    panel_merged = panel_merged.merge(laus_ann, on=["GEOID","year"], how="left")
    print(f"  LAUS merge: {panel_merged['unemployment_rate'].notna().sum():,} non-null unemployment obs")

panel_merged.to_csv(f"{OUTDIR}/panel_merged.csv", index=False)
print(f"  Saved: panel_merged.csv  ({len(panel_merged):,} rows × {len(panel_merged.columns)} cols)")

# ─── 6. Summary statistics ────────────────────────────────────────────────────
print("\n=== Summary statistics (pre-treatment period: 2011-2014) ===")
pre = panel_merged[panel_merged["year"].between(2011, 2014)].copy()

# Covariates available
avail_vars = ["BP_NATIONAL_RANK","RUCC2013","BUILDINGS_FRACTION_DE"]
if "median_hh_income" in pre.columns:    avail_vars.append("median_hh_income")
if "poverty_rate" in pre.columns:        avail_vars.append("poverty_rate")
if "population" in pre.columns:          avail_vars.append("population")
if "share_NH_black" in pre.columns:      avail_vars.append("share_NH_black")
if "share_hispanic" in pre.columns:      avail_vars.append("share_hispanic")
if "unemployment_rate" in pre.columns:   avail_vars.append("unemployment_rate")

rows = []
for v in avail_vars:
    if v not in pre.columns:
        continue
    t_mean = pre.loc[pre["treated"]==1, v].mean()
    c_mean = pre.loc[pre["treated"]==0, v].mean()
    t_sd   = pre.loc[pre["treated"]==1, v].std()
    c_sd   = pre.loc[pre["treated"]==0, v].std()
    diff   = t_mean - c_mean
    pct    = abs(diff/t_mean*100) if t_mean != 0 else 0
    rows.append({"Variable": v, "Treated mean": round(t_mean,4), "Treated SD": round(t_sd,4),
                 "Control mean": round(c_mean,4), "Control SD": round(c_sd,4),
                 "Difference": round(diff,4), "Diff %": round(pct,1)})

stats_df = pd.DataFrame(rows)
stats_df.to_csv(f"{OUTDIR}/summary_stats.csv", index=False)
print(stats_df.to_string(index=False))

# ─── 7. Data acquisition checklist ────────────────────────────────────────────
print("""
=== DATA STILL NEEDED (not available locally) ===

Outcomes (require separate download/application):
  1. CDC WONDER compressed mortality (suicide/overdose):
       https://wonder.cdc.gov/cmf-icd10.html
       -> Download county-year counts, ICD-10 X60-X84 (suicide), T36-T65 (overdose)
       -> Note: counties with <10 deaths are suppressed; will need suppression strategy

  2. Medicaid T-MSIS (primary outcome — restricted):
       Apply via ResDAC (resdac.org) or CMS Data Navigator
       -> Mental health ED visits, inpatient stays, Rx by county-year
       -> 6-12 month processing time typical; start application now

  3. EPA HMS wildfire-specific PM2.5 (smoke mechanism variable):
       https://www.epa.gov/hms
       -> Annual county-level smoke days / PM2.5 averages
       -> Used to separate PM2.5 from trauma pathways

  4. NOAA NLDN lightning strikes (IV):
       Commercial license required via Vaisala
       -> Annual county-level CG lightning strike counts
       -> Alternative: GHCN daily thunderstorm observation days (free)

  5. FEMA disaster declarations (evacuation/displacement mechanism):
       https://www.fema.gov/api/open/v2/disasterDeclarationsSummaries
       -> Free API, can download now

  6. BRFSS county-level poor mental health days:
       https://www.cdc.gov/brfss/smart/smart_data.htm
       -> SMART BRFSS — selected metro and micro areas; not all counties covered

  7. SAMHSA TEDS substance use admissions:
       https://www.samhsa.gov/data/data-we-collect/teds/datafiles
       -> State-level microdata; county available in most states
""")
