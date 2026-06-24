"""
Build 2015-cohort matched panels (one per fire-size threshold).

Treatment year: 2015 only.
Study window:   2011–2019 (4 pre, 1 treatment, 4 post years).
event_time:     year - 2015  (treated counties only; controls get NA)
cohort_g:       2015 for treated, 0 for never-treated controls.

Outputs:
  panel_2015_T1_moderate_1k.csv
  panel_2015_T2_large_5k.csv
  panel_2015_T3_verylarge_25k.csv
"""
import warnings; warnings.filterwarnings('ignore')
import zipfile, os
import geopandas as gpd
import pandas as pd
import numpy as np

BASE   = r"C:\Users\chenyon\Research Paper 2026(1)\data\raw"
OUTDIR = r"C:\Users\chenyon\Research Paper 2026(1)"

WESTERN_FIPS = ['04','06','08','16','30','32','35','41','49','53','56']
MIN_POP      = 10_000
YEARS        = list(range(2011, 2020))

THRESHOLDS = [
    ("T1_moderate_1k",   1_000),
    ("T2_large_5k",      5_000),
    ("T3_verylarge_25k", 25_000),
]

def asinh(x):
    return np.arcsinh(x)

# ── Land area ──────────────────────────────────────────────────────────────────
print("Loading county land areas...")
counties_dir = f"{BASE}/counties"
if not os.path.isdir(counties_dir):
    with zipfile.ZipFile(f"{BASE}/tl_2020_us_county.zip") as z:
        z.extractall(counties_dir)
counties_shp = gpd.read_file(counties_dir)
counties_shp["GEOID"] = counties_shp["GEOID"].astype(str).str.zfill(5)
land_df = counties_shp[["GEOID","ALAND"]].copy()
land_df["land_area_acres"] = land_df["ALAND"].astype(float) * 0.000247105
land_df = land_df[["GEOID","land_area_acres"]]

# ── ACS 2014 for population filter ────────────────────────────────────────────
print("Loading ACS 2014 population...")
acs_raw = pd.read_csv(f"{OUTDIR}/acs_covariates.csv", dtype={"GEOID": str})
acs_raw["GEOID"] = acs_raw["GEOID"].str.zfill(5)
acs_2014 = (acs_raw[acs_raw["year"] == 2014][["GEOID","population"]]
            .rename(columns={"population": "county_pop_2014"}))

# ── Base panel ────────────────────────────────────────────────────────────────
print("Loading base panel_analysis.csv...")
panel = pd.read_csv(f"{OUTDIR}/panel_analysis.csv", dtype={"GEOID": str}, low_memory=False)
panel["GEOID"]   = panel["GEOID"].str.zfill(5)
panel["STATEFP"] = panel["GEOID"].str[:2]
panel = panel[panel["STATEFP"].isin(WESTERN_FIPS) & panel["year"].isin(YEARS)].copy()
panel = panel.merge(land_df, on="GEOID", how="left")
panel = panel.merge(acs_2014, on="GEOID", how="left")

# Population filter via forward/backfill
panel["pop_for_filter"] = panel["county_pop_2014"].combine_first(
    panel["county_pop"].where(panel["year"] == 2014))
panel = panel.sort_values(["GEOID","year"])
panel["pop_for_filter"] = panel.groupby("GEOID")["pop_for_filter"].transform(
    lambda x: x.ffill().bfill())
pop_ok = panel.groupby("GEOID")["pop_for_filter"].first()
pop_ok = pop_ok[pop_ok >= MIN_POP].index
panel_filt = panel[panel["GEOID"].isin(pop_ok)].copy()
print(f"  Western panel after pop filter: {panel_filt['GEOID'].nunique()} counties")

# ── MTBS 2015 fire acres per county (for pct_burned_2015) ─────────────────────
print("Loading MTBS 2015 fires...")
mtbs = gpd.read_file(
    f"{BASE}/mtbs_perims/S_USA.MTBS_BURN_AREA_BOUNDARY.shp"
).to_crs("EPSG:5070")
mtbs["YEAR"]      = pd.to_numeric(mtbs["YEAR"],  errors="coerce")
mtbs["ACRES"]     = pd.to_numeric(mtbs["ACRES"], errors="coerce")
mtbs["FIRE_TYPE"] = mtbs["FIRE_TYPE"].astype(str).str.strip()
fires_2015 = mtbs[(mtbs["YEAR"] == 2015) & (mtbs["FIRE_TYPE"] == "Wildfire")].copy()
fires_2015["geometry"] = fires_2015.geometry.centroid

counties_geo = gpd.read_file(counties_dir).to_crs("EPSG:5070")
counties_geo["GEOID"] = counties_geo["GEOID"].astype(str).str.zfill(5)

f2015_joined = gpd.sjoin_nearest(
    fires_2015[["FIRE_ID","ACRES","geometry"]],
    counties_geo[["GEOID","geometry"]],
    how="left"
).dropna(subset=["GEOID","ACRES"])

fire_2015_by_county = (f2015_joined.groupby("GEOID")["ACRES"]
                        .sum().reset_index()
                        .rename(columns={"ACRES": "acres_2015_all"}))

# ── Build panels per threshold ─────────────────────────────────────────────────
for tag, min_acres in THRESHOLDS:
    print(f"\n{'='*55}")
    print(f"Building panel: {tag}  (>= {min_acres:,} acres)")
    print(f"{'='*55}")

    # Load matched pairs
    mf = pd.read_csv(f"{OUTDIR}/matched_2015_{tag}.csv",
                     dtype={"treated_GEOID": str, "control_GEOID": str})
    mf["treated_GEOID"] = mf["treated_GEOID"].str.zfill(5)
    mf["control_GEOID"] = mf["control_GEOID"].str.zfill(5)
    primary = mf[mf["match_rank"] == 1]

    treated_info = (primary[["treated_GEOID","treated_acres_2015",
                              "treated_pct_burned_2015"]]
                    .drop_duplicates("treated_GEOID")
                    .rename(columns={
                        "treated_GEOID":           "GEOID",
                        "treated_acres_2015":      "acres_2015",
                        "treated_pct_burned_2015": "pct_burned_2015",
                    }))
    treated_info["treated"]  = 1
    treated_info["cohort_g"] = 2015

    ctrl_geoids = primary["control_GEOID"].unique()
    ctrl_info = pd.DataFrame({
        "GEOID":           ctrl_geoids,
        "acres_2015":      0.0,
        "pct_burned_2015": 0.0,
        "treated":         0,
        "cohort_g":        0,
    })

    match_info = pd.concat([treated_info, ctrl_info], ignore_index=True)
    county_set = set(match_info["GEOID"])
    print(f"  Matched set: {match_info['treated'].sum()} treated + "
          f"{(match_info['treated']==0).sum()} controls = {len(match_info)} counties")

    # Subset to matched counties; drop stale treatment columns
    p = panel_filt[panel_filt["GEOID"].isin(county_set)].copy()
    for dc in ["treated","cohort_g","event_time","match_set",
               "first_fire_yr","post","surprise_fire"]:
        if dc in p.columns:
            p = p.drop(columns=[dc])
    p = p.merge(match_info, on="GEOID", how="left")
    print(f"  Panel rows: {len(p)}  ({p['GEOID'].nunique()} counties × {len(YEARS)} years)")

    # ── Fire intensity ──────────────────────────────────────────────────────
    # All-fire acres in 2015 (threshold-agnostic — used for reference)
    p = p.merge(fire_2015_by_county, on="GEOID", how="left")
    p["acres_2015_all"] = p["acres_2015_all"].fillna(0.0)

    # Threshold-specific 2015 acres (from matching output)
    p["pct_burned_2015"]      = p["pct_burned_2015"].fillna(0.0)
    p["log_pct_burned_2015"]  = np.log1p(p["pct_burned_2015"])

    # ── Outcome transformations ─────────────────────────────────────────────
    for rc in ["suicide_rate","overdose_rate"]:
        p[rc] = pd.to_numeric(p[rc], errors="coerce").fillna(0)
    p["ihs_suicide_rate"]  = asinh(p["suicide_rate"])
    p["ihs_overdose_rate"] = asinh(p["overdose_rate"])

    for dc in ["suicide_deaths","overdose_deaths"]:
        p[dc] = pd.to_numeric(p[dc], errors="coerce").fillna(0)

    # ── DiD identifiers ──────────────────────────────────────────────────────
    # event_time = year - 2015  for treated; NA for controls
    p["event_time"] = np.where(p["treated"] == 1, p["year"] - 2015, np.nan)
    p["post"]       = (p["year"] >= 2015).astype(int)
    p["did"]        = p["treated"] * p["post"]  # simple DiD interaction

    # ── Covariates ──────────────────────────────────────────────────────────
    p["unemployment_rate"] = pd.to_numeric(p["unemployment_rate"], errors="coerce")

    # ── Select columns ──────────────────────────────────────────────────────
    keep = [
        "GEOID","year","NAME","STATEFP","treated","cohort_g","event_time","post","did",
        "WHP_quintile","RUCC2013","BP_NATIONAL_RANK","BUILDINGS_FRACTION_DE",
        "county_pop","county_pop_2014","median_hh_income","poverty_rate",
        "unemployment_rate","HPSA_mental_health",
        "share_NH_black","share_hispanic","share_AIAN",
        "land_area_acres","acres_2015","acres_2015_all","pct_burned_2015","log_pct_burned_2015",
        "suicide_deaths","suicide_rate","ihs_suicide_rate",
        "overdose_deaths","overdose_rate","ihs_overdose_rate",
        "pct_depression","pct_poor_mh_days",
    ]
    keep = [c for c in keep if c in p.columns]
    p = p[keep].reset_index(drop=True)

    # ── Summary ─────────────────────────────────────────────────────────────
    tr = p[p["treated"] == 1]
    ct = p[p["treated"] == 0]
    print(f"\n  Treated obs: {len(tr)}  Control obs: {len(ct)}")
    print(f"  Treated counties: {tr['GEOID'].nunique()}  "
          f"Control counties: {ct['GEOID'].nunique()}")
    print(f"  Suicide zero rate:  treated={( tr['suicide_rate']==0).mean()*100:.1f}%  "
          f"control={(ct['suicide_rate']==0).mean()*100:.1f}%")
    print(f"  Overdose zero rate: treated={(tr['overdose_rate']==0).mean()*100:.1f}%  "
          f"control={(ct['overdose_rate']==0).mean()*100:.1f}%")
    print(f"  pct_burned_2015 (treated): "
          f"mean={tr['pct_burned_2015'].mean():.2f}%  "
          f"median={tr['pct_burned_2015'].median():.2f}%  "
          f"p90={tr['pct_burned_2015'].quantile(.9):.2f}%")
    if "pct_depression" in p.columns:
        dep_n = p["pct_depression"].notna().sum()
        dep_yrs = (p[p["pct_depression"].notna()]["year"]
                   .value_counts().sort_index().to_dict())
        print(f"  pct_depression: {dep_n} non-null rows | years: {dep_yrs}")

    out_path = f"{OUTDIR}/panel_2015_{tag}.csv"
    p.to_csv(out_path, index=False)
    print(f"\n  Saved: panel_2015_{tag}.csv ({len(p)} rows)")

print("\nAll 2015-cohort panels built. Run estimate_2015.R next.")
