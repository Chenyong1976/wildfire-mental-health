"""
Build Western US matched panels (one per fire-size threshold).

For each threshold T1/T2/T3:
  - Load matched_west_{tag}.csv to get the treated + control county sets
  - Filter panel_analysis.csv to Western counties, pop >= 10,000
  - Assign new cohort_g (0 = never-treated control for this threshold)
  - Add fire intensity variables: pct_burned, cumulative_acres, land_area_acres
  - Compute IHS outcomes: ihs_suicide_rate, ihs_overdose_rate
  - Add ALAND-based land area from shapefile
  - Output: panel_west_T1_moderate_1k.csv, panel_west_T2_large_5k.csv, panel_west_T3_verylarge_25k.csv
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

# ── Land area from county shapefile ───────────────────────────────────────────
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
acs_2014 = acs_raw[acs_raw["year"] == 2014][["GEOID","population"]].copy()
acs_2014 = acs_2014.rename(columns={"population": "county_pop_2014"})

# ── Base panel ────────────────────────────────────────────────────────────────
print("Loading base panel_analysis.csv...")
panel = pd.read_csv(f"{OUTDIR}/panel_analysis.csv", dtype={"GEOID": str}, low_memory=False)
panel["GEOID"]   = panel["GEOID"].str.zfill(5)
panel["STATEFP"] = panel["GEOID"].str[:2]
panel = panel[panel["STATEFP"].isin(WESTERN_FIPS)].copy()
panel = panel[panel["year"].isin(YEARS)].copy()
print(f"  Western panel rows: {len(panel)}  Counties: {panel['GEOID'].nunique()}")

# Merge land area
panel = panel.merge(land_df, on="GEOID", how="left")

# Merge ACS population for filter
panel = panel.merge(acs_2014, on="GEOID", how="left")

# Population filter: use county_pop_2014; fallback to panel county_pop for counties without ACS 1-yr
panel["pop_for_filter"] = panel["county_pop_2014"].combine_first(
    panel["county_pop"].where(panel["year"] == 2014)
)
# Fill remaining NAs via forward/backfill within county
panel = panel.sort_values(["GEOID","year"])
panel["pop_for_filter"] = panel.groupby("GEOID")["pop_for_filter"].transform(
    lambda x: x.ffill().bfill()
)
pop_ok = panel.groupby("GEOID")["pop_for_filter"].first()
pop_ok = pop_ok[pop_ok >= MIN_POP].index
panel_filt = panel[panel["GEOID"].isin(pop_ok)].copy()
print(f"  After pop >= {MIN_POP:,} filter: {panel_filt['GEOID'].nunique()} counties")

# ── MTBS fire acres per county 2015-2019 (all fires, for cumulative exposure) ─
print("Loading MTBS for fire intensity variables...")
mtbs = gpd.read_file(
    f"{BASE}/mtbs_perims/S_USA.MTBS_BURN_AREA_BOUNDARY.shp"
).to_crs("EPSG:5070")
mtbs["YEAR"]      = pd.to_numeric(mtbs["YEAR"],  errors="coerce")
mtbs["ACRES"]     = pd.to_numeric(mtbs["ACRES"], errors="coerce")
mtbs["FIRE_TYPE"] = mtbs["FIRE_TYPE"].astype(str).str.strip()

fires_window = mtbs[
    mtbs["YEAR"].between(2015, 2019) & (mtbs["FIRE_TYPE"] == "Wildfire")
].copy()
fires_window["geometry"] = fires_window.geometry.centroid
counties_geo = gpd.read_file(counties_dir).to_crs("EPSG:5070")
counties_geo["GEOID"] = counties_geo["GEOID"].astype(str).str.zfill(5)
counties_geo = counties_geo[["GEOID","geometry"]]

fire_joined = gpd.sjoin_nearest(
    fires_window[["FIRE_ID","YEAR","ACRES","geometry"]],
    counties_geo,
    how="left"
)
fire_joined = fire_joined.dropna(subset=["GEOID","ACRES"])
fire_yearly = (fire_joined.groupby(["GEOID","YEAR"])["ACRES"]
               .sum().reset_index().rename(columns={"YEAR":"year","ACRES":"acres_burned_yr"}))

# ── Build panels per threshold ─────────────────────────────────────────────────
for tag, min_acres in THRESHOLDS:
    print(f"\n{'='*55}")
    print(f"Building panel: {tag}  (>= {min_acres:,} acres)")
    print(f"{'='*55}")

    # Load matched pairs
    mf = pd.read_csv(f"{OUTDIR}/matched_west_{tag}.csv", dtype={
        "treated_GEOID": str, "control_GEOID": str})
    mf["treated_GEOID"] = mf["treated_GEOID"].str.zfill(5)
    mf["control_GEOID"] = mf["control_GEOID"].str.zfill(5)
    primary = mf[mf["match_rank"] == 1]

    # Treated set with cohort info
    treated_info = (primary[["treated_GEOID","treated_first_fire_yr",
                              "treated_total_acres","treated_pct_burned"]]
                    .drop_duplicates("treated_GEOID")
                    .rename(columns={
                        "treated_GEOID":        "GEOID",
                        "treated_first_fire_yr":"cohort_g_new",
                        "treated_total_acres":  "total_acres",
                        "treated_pct_burned":   "pct_burned",
                    }))
    treated_info["treated"] = 1

    # Control set (all unique controls from primary matches)
    ctrl_geoids = primary["control_GEOID"].unique()
    ctrl_info = pd.DataFrame({
        "GEOID":       ctrl_geoids,
        "cohort_g_new": 0,
        "total_acres": 0.0,
        "pct_burned":  0.0,
        "treated":     0,
    })

    match_info = pd.concat([treated_info, ctrl_info], ignore_index=True)
    county_set = set(match_info["GEOID"])
    print(f"  Matched set: {match_info['treated'].sum()} treated + "
          f"{(match_info['treated']==0).sum()} controls = {len(match_info)} counties")

    # Subset panel to matched counties; drop stale treatment columns from base panel
    p = panel_filt[panel_filt["GEOID"].isin(county_set)].copy()
    for drop_col in ["treated","cohort_g","event_time","match_set","first_fire_yr","post","surprise_fire"]:
        if drop_col in p.columns:
            p = p.drop(columns=[drop_col])
    p = p.merge(match_info, on="GEOID", how="left")
    print(f"  Panel rows: {len(p)}  ({p['GEOID'].nunique()} counties × {len(YEARS)} years)")

    # ── Fire intensity by year ──────────────────────────────────────────────
    p = p.merge(fire_yearly, on=["GEOID","year"], how="left")
    p["acres_burned_yr"] = p["acres_burned_yr"].fillna(0.0)

    # Cumulative acres through current year (within threshold >= min_acres)
    # Filter fire_yearly to only fires meeting threshold
    fy_thresh = (fire_joined[fire_joined["ACRES"] >= min_acres]
                 .groupby(["GEOID","YEAR"])["ACRES"]
                 .sum().reset_index().rename(columns={"YEAR":"year","ACRES":"acres_thresh_yr"}))
    p = p.merge(fy_thresh, on=["GEOID","year"], how="left")
    p["acres_thresh_yr"] = p["acres_thresh_yr"].fillna(0.0)
    p = p.sort_values(["GEOID","year"])
    p["cumulative_acres"] = p.groupby("GEOID")["acres_thresh_yr"].cumsum()

    # pct_burned_yr = annual acres / land area (for dose-response analyses)
    p["pct_burned_yr"] = np.where(
        p["land_area_acres"] > 0,
        p["acres_burned_yr"] / p["land_area_acres"] * 100,
        0.0
    )

    # ── Outcome transformations ─────────────────────────────────────────────
    for rc in ["suicide_rate","overdose_rate"]:
        p[rc] = pd.to_numeric(p[rc], errors="coerce").fillna(0)
    p["ihs_suicide_rate"]  = asinh(p["suicide_rate"])
    p["ihs_overdose_rate"] = asinh(p["overdose_rate"])

    # Deaths (raw counts, already in panel)
    for dc in ["suicide_deaths","overdose_deaths"]:
        p[dc] = pd.to_numeric(p[dc], errors="coerce").fillna(0)

    # ── CS2021 identifiers ──────────────────────────────────────────────────
    p["cohort_g"] = p["cohort_g_new"].fillna(0).astype(int)
    p["event_time"] = np.where(
        p["cohort_g"] > 0,
        p["year"] - p["cohort_g"],
        np.nan
    )

    # ── County-level time-varying unemployment ──────────────────────────────
    p["unemployment_rate"] = pd.to_numeric(p["unemployment_rate"], errors="coerce")

    # ── log treatment intensity (for dose-response regressions) ─────────────
    p["log_pct_burned"] = np.log1p(p["pct_burned"])  # log(1+pct_burned_cumulative)
    p["log_cumulative_acres"] = np.log1p(p["cumulative_acres"])

    # ── Select and order columns ────────────────────────────────────────────
    keep_cols = [
        "GEOID","year","NAME","STATEFP","treated","cohort_g","event_time",
        "WHP_quintile","RUCC2013","BP_NATIONAL_RANK","BUILDINGS_FRACTION_DE",
        "county_pop","county_pop_2014","median_hh_income","poverty_rate",
        "unemployment_rate","HPSA_mental_health",
        "share_NH_black","share_hispanic","share_AIAN",
        "land_area_acres","total_acres","pct_burned",
        "acres_burned_yr","acres_thresh_yr","cumulative_acres",
        "pct_burned_yr","log_pct_burned","log_cumulative_acres",
        "suicide_deaths","suicide_rate","ihs_suicide_rate",
        "overdose_deaths","overdose_rate","ihs_overdose_rate",
        "pct_depression","pct_poor_mh_days",
    ]
    keep_cols = [c for c in keep_cols if c in p.columns]
    p = p[keep_cols].reset_index(drop=True)

    # ── Summary stats ───────────────────────────────────────────────────────
    treated_obs = p[p["treated"]==1]
    print(f"\n  === PANEL SUMMARY ===")
    print(f"  Rows: {len(p)}  Treated rows: {len(treated_obs)}")
    print(f"  Treated cohorts: "
          f"{p[p['treated']==1].groupby('cohort_g')['GEOID'].nunique().to_dict()}")
    print(f"  Outcome zeros (treated, ihs=0):")
    print(f"    suicide_rate:  {(treated_obs['suicide_rate']==0).mean()*100:.1f}%")
    print(f"    overdose_rate: {(treated_obs['overdose_rate']==0).mean()*100:.1f}%")
    print(f"  pct_burned (treated, 2015-2019):")
    tpost = treated_obs[treated_obs["year"] >= treated_obs["cohort_g"]]
    print(f"    mean={tpost['pct_burned'].mean():.2f}%  "
          f"median={tpost['pct_burned'].median():.2f}%  "
          f"p90={tpost['pct_burned'].quantile(.9):.2f}%")
    if "pct_depression" in p.columns:
        ndep = p["pct_depression"].notna().sum()
        print(f"  pct_depression non-null: {ndep} / {len(p)} rows "
              f"({ndep/len(p)*100:.1f}%)")
        dep_yrs = p[p["pct_depression"].notna()]["year"].value_counts().sort_index()
        print(f"    Years with depression data: {dep_yrs.to_dict()}")

    # ── Save ────────────────────────────────────────────────────────────────
    out_path = f"{OUTDIR}/panel_west_{tag}.csv"
    p.to_csv(out_path, index=False)
    print(f"\n  Saved: panel_west_{tag}.csv ({len(p)} rows, "
          f"{p['GEOID'].nunique()} counties)")

print("\nAll panels built. Run estimate_west.R next.")
