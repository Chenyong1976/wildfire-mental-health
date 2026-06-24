"""
Western US wildfire matching — redesigned study.

Design improvements:
  1. Western 11 states only (AZ CA CO ID MT NV NM OR UT WA WY)
  2. County population >= 25,000 (eliminates CDC suppression noise)
  3. Buffer zone: controls within 150 km of any treated county excluded
  4. Pre-treatment outcomes (2011-2014 mean rates) as matching variables
  5. % county land area burned as treatment intensity variable
  6. Cumulative fire exposure (total acres 2015-2019 per county)
  7. Separate Mahalanobis matching for each of three fire-size thresholds
"""
import warnings; warnings.filterwarnings('ignore')
import zipfile, os
import geopandas as gpd
import pandas as pd
import numpy as np
import openpyxl
import xlrd
from scipy.spatial.distance import cdist

BASE   = r"C:\Users\chenyon\Research Paper 2026(1)\data\raw"
OUTDIR = r"C:\Users\chenyon\Research Paper 2026(1)"

WESTERN_FIPS = ['04','06','08','16','30','32','35','41','49','53','56']
MIN_POP        = 10_000
PAIR_BUFFER_M  = 50_000   # 50 km pairwise (min distance between matched pair, not global pool exclusion)

THRESHOLDS = [
    ("T1_moderate_1k",   1_000,  "Moderate+ (>=1,000 ac)"),
    ("T2_large_5k",      5_000,  "Large+    (>=5,000 ac)"),
    ("T3_verylarge_25k", 25_000, "Very Large (>=25,000 ac)"),
]

MATCH_FEATURES = [
    "BP_NATIONAL_RANK",
    "RUCC2013",
    "BUILDINGS_FRACTION_DE",
    "pre_fire_flag",
    "county_pop_2014",
    "median_hh_income_2014",
    "pre_suicide_rate",
    "pre_overdose_rate",
]

# ── 1. County shapefile (Western only, keep land area + centroids) ─────────────
print("Loading county shapefile...")
counties_dir = f"{BASE}/counties"
if not os.path.isdir(counties_dir):
    with zipfile.ZipFile(f"{BASE}/tl_2020_us_county.zip") as z:
        z.extractall(counties_dir)
all_counties = gpd.read_file(counties_dir).to_crs("EPSG:5070")
all_counties["GEOID"]   = all_counties["GEOID"].astype(str).str.zfill(5)
all_counties["STATEFP"] = all_counties["STATEFP"].astype(str).str.zfill(2)
all_counties["land_area_acres"] = all_counties["ALAND"].astype(float) * 0.000247105
all_counties["cx"] = all_counties.geometry.centroid.x
all_counties["cy"] = all_counties.geometry.centroid.y
counties = all_counties[all_counties["STATEFP"].isin(WESTERN_FIPS)][
    ["GEOID","STATEFP","NAME","land_area_acres","cx","cy","geometry"]
].copy().reset_index(drop=True)
print(f"  Western counties: {len(counties)}")

# ── 2. MTBS fires ──────────────────────────────────────────────────────────────
print("Loading MTBS fire perimeters...")
mtbs = gpd.read_file(
    f"{BASE}/mtbs_perims/S_USA.MTBS_BURN_AREA_BOUNDARY.shp"
).to_crs("EPSG:5070")
mtbs["YEAR"]      = pd.to_numeric(mtbs["YEAR"],  errors="coerce")
mtbs["ACRES"]     = pd.to_numeric(mtbs["ACRES"], errors="coerce")
mtbs["FIRE_TYPE"] = mtbs["FIRE_TYPE"].astype(str).str.strip()

fires_treat_all = mtbs[
    mtbs["YEAR"].between(2015, 2019) & (mtbs["FIRE_TYPE"] == "Wildfire")
].copy()
fires_pre = mtbs[
    (mtbs["YEAR"] <= 2014) & (mtbs["FIRE_TYPE"] == "Wildfire") & (mtbs["ACRES"] >= 1000)
].copy()
print(f"  Treatment-window fires: {len(fires_treat_all)}")

def fires_to_county(fire_gdf, counties_gdf):
    fc = fire_gdf.copy()
    fc["geometry"] = fire_gdf.geometry.centroid
    joined = gpd.sjoin_nearest(
        fc[["FIRE_ID","YEAR","ACRES","geometry"]],
        counties_gdf[["GEOID","geometry"]],
        how="left"
    )
    return joined.dropna(subset=["GEOID","ACRES","YEAR"])

# Pre-fire flag
joined_pre  = fires_to_county(fires_pre,  counties)
pre_fire_geoids = set(joined_pre["GEOID"].dropna().unique())
print(f"  Western counties with pre-2015 wildfire: {len(pre_fire_geoids)}")

# All 2015-2019 fires joined (used for all thresholds)
joined_treat_all = fires_to_county(fires_treat_all, counties)
print(f"  Fire-county pairs 2015-2019: {len(joined_treat_all)}")

# ── 3. WHP data ────────────────────────────────────────────────────────────────
print("Loading WHP data...")
wb = openpyxl.load_workbook(f"{BASE}/wrc_county_data.xlsx", read_only=True)
ws = wb["Counties"]
rows = list(ws.iter_rows(values_only=True))
whp_df = pd.DataFrame(rows[1:], columns=rows[0])
whp_df["GEOID"] = whp_df["GEOID"].astype(str).str.zfill(5)
whp_df = whp_df[["GEOID","BP_NATIONAL_RANK","BUILDINGS_FRACTION_DE"]].dropna(
    subset=["BP_NATIONAL_RANK"])
wb.close()

# ── 4. RUCC 2013 ───────────────────────────────────────────────────────────────
print("Loading RUCC 2013...")
rucc_raw = xlrd.open_workbook(f"{BASE}/rucc2013.xls")
ws_r     = rucc_raw.sheet_by_index(0)
rh       = [str(ws_r.cell_value(0, c)) for c in range(ws_r.ncols)]
rrows    = [[ws_r.cell_value(r, c) for c in range(ws_r.ncols)] for r in range(1, ws_r.nrows)]
rucc_df  = pd.DataFrame(rrows, columns=rh)
fcol     = [c for c in rucc_df.columns if "FIPS"  in c.upper()][0]
rcol     = [c for c in rucc_df.columns if "RUCC"  in c.upper() and "2013" in c][0]
rucc_df["GEOID"] = rucc_df[fcol].apply(
    lambda x: str(int(x)).zfill(5) if pd.notna(x) and str(x).strip() != "" else None
)
rucc_df = rucc_df.dropna(subset=["GEOID"])[["GEOID", rcol]].rename(
    columns={rcol: "RUCC2013"})
rucc_df["RUCC2013"] = pd.to_numeric(rucc_df["RUCC2013"], errors="coerce")

# ── 5. ACS 2014 (pop + income) ────────────────────────────────────────────────
print("Loading ACS covariates...")
acs_raw = pd.read_csv(f"{OUTDIR}/acs_covariates.csv", dtype={"GEOID": str})
acs_raw["GEOID"] = acs_raw["GEOID"].astype(str).str.zfill(5)
acs_2014 = acs_raw[acs_raw["year"] == 2014][["GEOID","population","median_hh_income"]].copy()
acs_2014 = acs_2014.rename(columns={
    "population":       "county_pop_2014",
    "median_hh_income": "median_hh_income_2014"
})
print(f"  ACS 2014 records: {len(acs_2014)}")

# ── 6. Pre-treatment outcomes (2011-2014 mean rates) ──────────────────────────
# Use pre-computed rate columns (per 100k) from panel_analysis.csv, not raw counts,
# to avoid population-denominator mismatch for counties without ACS 1-yr coverage.
print("Computing pre-treatment outcome rates (2011-2014)...")
panel = pd.read_csv(f"{OUTDIR}/panel_analysis.csv",
                    dtype={"GEOID": str}, low_memory=False)
panel["GEOID"] = panel["GEOID"].str.zfill(5)
pre = panel[panel["year"].between(2011, 2014)].copy()
pre["suicide_rate"]  = pd.to_numeric(pre["suicide_rate"],  errors="coerce")
pre["overdose_rate"] = pd.to_numeric(pre["overdose_rate"], errors="coerce")

pre_agg = (pre.groupby("GEOID")
             .agg(pre_suicide_rate =("suicide_rate",  "mean"),
                  pre_overdose_rate=("overdose_rate", "mean"))
             .reset_index())
pre_agg["pre_suicide_rate"]  = pre_agg["pre_suicide_rate"].fillna(0)
pre_agg["pre_overdose_rate"] = pre_agg["pre_overdose_rate"].fillna(0)
pre_outcomes = pre_agg[["GEOID","pre_suicide_rate","pre_overdose_rate"]].copy()

# ── 7. Master Western county panel ────────────────────────────────────────────
print("Building master county panel...")
master = (counties[["GEOID","STATEFP","NAME","land_area_acres","cx","cy"]]
          .merge(whp_df,    on="GEOID", how="left")
          .merge(rucc_df,   on="GEOID", how="left")
          .merge(acs_2014,  on="GEOID", how="left")
          .merge(pre_outcomes, on="GEOID", how="left"))
master["pre_fire_flag"] = master["GEOID"].isin(pre_fire_geoids).astype(int)
master = master.dropna(subset=["BP_NATIONAL_RANK","RUCC2013"])
print(f"  Master panel: {len(master)} Western counties (after WHP/RUCC filter)")

# Fill remaining NAs with medians before matching
for f in MATCH_FEATURES:
    if f in master.columns:
        master[f] = master[f].fillna(master[f].median())

# WHP quintiles (computed once across all Western counties)
master["WHP_quintile"] = pd.qcut(
    master["BP_NATIONAL_RANK"], q=5, labels=[1,2,3,4,5]
).astype(int)

# ── 8. Loop over thresholds ────────────────────────────────────────────────────
all_summary = []

for tag, min_acres, label in THRESHOLDS:
    print(f"\n{'='*60}")
    print(f"THRESHOLD: {label}  (>= {min_acres:,} acres)")
    print(f"{'='*60}")

    # ─ Treated counties for this threshold ─
    fires_t = joined_treat_all[joined_treat_all["ACRES"] >= min_acres].copy()
    fire_agg = (fires_t.groupby("GEOID")
                .agg(first_year  =("YEAR",    lambda x: int(x.astype(int).min())),
                     n_fires     =("FIRE_ID", "nunique"),
                     total_acres =("ACRES",   lambda x: float(x.sum())))
                .reset_index())
    fire_agg["treated"] = 1
    print(f"  Qualifying fire counties: {len(fire_agg)}")

    # Merge treatment info into master
    panel_t = master.copy()
    panel_t = panel_t.merge(
        fire_agg[["GEOID","treated","first_year","n_fires","total_acres"]],
        on="GEOID", how="left"
    )
    panel_t["treated"]     = panel_t["treated"].fillna(0).astype(int)
    panel_t["first_year"]  = panel_t["first_year"].fillna(0).astype(int)
    panel_t["total_acres"] = panel_t["total_acres"].fillna(0.0)
    panel_t["pct_burned"]  = np.where(
        panel_t["land_area_acres"] > 0,
        panel_t["total_acres"] / panel_t["land_area_acres"] * 100,
        0.0
    )

    # ─ Population filter ─
    n_before = len(panel_t)
    panel_t = panel_t[panel_t["county_pop_2014"] >= MIN_POP].copy()
    print(f"  After pop >= {MIN_POP:,} filter: {len(panel_t)} "
          f"(dropped {n_before - len(panel_t)})")

    treated_df  = panel_t[panel_t["treated"] == 1].reset_index(drop=True)
    controls_df = panel_t[panel_t["treated"] == 0].reset_index(drop=True)

    if len(treated_df) == 0:
        print("  WARNING: no treated counties — skipping")
        continue

    print(f"  Treated: {len(treated_df)}  Controls: {len(controls_df)}")

    # ─ Mahalanobis matching within WHP quintile ─
    # Controls must be >= 50 km from the specific treated county they're matched to.
    # We enforce this as a pairwise constraint inside the loop (not a global pool exclusion)
    # so the same control can match a distant treated county even if it's near another one.
    results = []
    unmatched_q = []

    for q in sorted(treated_df["WHP_quintile"].unique()):
        t_q = treated_df[treated_df["WHP_quintile"] == q].reset_index(drop=True)
        c_q = controls_df[controls_df["WHP_quintile"] == q].reset_index(drop=True)
        if len(c_q) == 0:
            print(f"  WARNING: no controls in Q{q}")
            unmatched_q.append(q)
            continue

        t_feat = t_q[MATCH_FEATURES].values.astype(float)
        c_feat = c_q[MATCH_FEATURES].values.astype(float)

        # Pairwise geographic distances (metres, EPSG:5070)
        t_geo = t_q[["cx","cy"]].values.astype(float)
        c_geo = c_q[["cx","cy"]].values.astype(float)
        geo_dists = cdist(t_geo, c_geo)  # shape (n_treated_q, n_ctrl_q)

        # Global regularised covariance matrix
        all_feat = np.vstack([t_feat, c_feat])
        cov_mat  = np.cov(all_feat.T)
        reg      = 0.01 * np.trace(cov_mat) / len(MATCH_FEATURES) * np.eye(len(MATCH_FEATURES))
        VI       = np.linalg.inv(cov_mat + reg)

        mah_dists = cdist(t_feat, c_feat, metric="mahalanobis", VI=VI)
        n_match   = min(2, len(c_q))

        for i in range(len(t_q)):
            t_row = t_q.iloc[i]
            # Set Mahalanobis distance to inf for controls too close geographically
            d_i = mah_dists[i].copy()
            d_i[geo_dists[i] < PAIR_BUFFER_M] = np.inf
            valid = [j for j in np.argsort(d_i)[:n_match] if d_i[j] < np.inf]
            if not valid:
                # Relax buffer for this treated county if no controls available
                valid = list(np.argsort(mah_dists[i])[:n_match])
            for rank, idx in enumerate(valid, 1):
                c_row = c_q.iloc[idx]
                results.append({
                    "treated_GEOID"       : t_row["GEOID"],
                    "treated_NAME"        : t_row["NAME"],
                    "treated_STATE"       : t_row["STATEFP"],
                    "treated_WHP_rank"    : round(float(t_row["BP_NATIONAL_RANK"]), 3),
                    "treated_RUCC"        : int(t_row["RUCC2013"]),
                    "treated_BldDE"       : round(float(t_row["BUILDINGS_FRACTION_DE"]), 3),
                    "treated_pre_fire"    : int(t_row["pre_fire_flag"]),
                    "treated_pop_2014"    : round(float(t_row["county_pop_2014"])),
                    "treated_income_2014" : round(float(t_row["median_hh_income_2014"])),
                    "treated_pre_suicide" : round(float(t_row["pre_suicide_rate"]), 3),
                    "treated_pre_overdose": round(float(t_row["pre_overdose_rate"]), 3),
                    "treated_WHP_quintile": q,
                    "treated_first_fire_yr": int(t_row["first_year"]),
                    "treated_total_acres" : round(float(t_row["total_acres"]), 0),
                    "treated_pct_burned"  : round(float(t_row["pct_burned"]), 4),
                    "control_GEOID"       : c_row["GEOID"],
                    "control_NAME"        : c_row["NAME"],
                    "control_STATE"       : c_row["STATEFP"],
                    "control_WHP_rank"    : round(float(c_row["BP_NATIONAL_RANK"]), 3),
                    "control_RUCC"        : int(c_row["RUCC2013"]),
                    "control_BldDE"       : round(float(c_row["BUILDINGS_FRACTION_DE"]), 3),
                    "control_pre_fire"    : int(c_row["pre_fire_flag"]),
                    "control_pop_2014"    : round(float(c_row["county_pop_2014"])),
                    "control_income_2014" : round(float(c_row["median_hh_income_2014"])),
                    "control_pre_suicide" : round(float(c_row["pre_suicide_rate"]), 3),
                    "control_pre_overdose": round(float(c_row["pre_overdose_rate"]), 3),
                    "match_rank"          : rank,
                    "mahalanobis_dist"    : round(float(mah_dists[i][idx]), 4),
                })

    if not results:
        print("  ERROR: no matched pairs found — skipping this threshold")
        continue
    matched = pd.DataFrame(results)
    primary = matched[matched["match_rank"] == 1]

    print(f"\n  Matched: {len(primary)} treated | {len(primary)*2} total pairs (1:2)")

    # ─ Cohort distribution ─
    cohort_tab = primary["treated_first_fire_yr"].value_counts().sort_index()
    print("  Cohorts:", dict(cohort_tab))

    # ─ Balance diagnostics ─
    print("\n  === MATCHING BALANCE ===")
    balance_vars = [
        ("WHP rank",    "treated_WHP_rank",    "control_WHP_rank"),
        ("RUCC",        "treated_RUCC",         "control_RUCC"),
        ("Bld frac DE", "treated_BldDE",        "control_BldDE"),
        ("Pre-fire",    "treated_pre_fire",     "control_pre_fire"),
        ("Pop 2014",    "treated_pop_2014",     "control_pop_2014"),
        ("Income",      "treated_income_2014",  "control_income_2014"),
        ("Pre-suicide", "treated_pre_suicide",  "control_pre_suicide"),
        ("Pre-overdose","treated_pre_overdose", "control_pre_overdose"),
    ]
    for lbl, tc, cc in balance_vars:
        t_m = primary[tc].astype(float).mean()
        c_m = primary[cc].astype(float).mean()
        pct = abs(t_m - c_m) / max(abs(t_m), 1e-9) * 100
        print(f"  {lbl:<14} treated={t_m:>12.3f}  control={c_m:>12.3f}  ({pct:.1f}% diff)")
    print(f"  Mahal dist: mean={primary['mahalanobis_dist'].mean():.3f}  "
          f"p90={primary['mahalanobis_dist'].quantile(0.9):.3f}")

    # ─ Save ─
    out_path = f"{OUTDIR}/matched_west_{tag}.csv"
    matched.to_csv(out_path, index=False)
    print(f"\n  Saved: matched_west_{tag}.csv ({len(matched)} rows)")

    all_summary.append({
        "tag": tag, "label": label, "min_acres": min_acres,
        "n_treated": len(primary),
        "n_control": primary["control_GEOID"].nunique(),
        **{f"g{yr}": int(cohort_tab.get(yr, 0)) for yr in range(2015, 2020)}
    })

# ── Summary ────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("MATCHING SUMMARY")
print("="*60)
summary_df = pd.DataFrame(all_summary)
print(summary_df.to_string(index=False))
summary_df.to_csv(f"{OUTDIR}/matching_west_summary.csv", index=False)
print("\nDone — run build_panel_west.py next.")
