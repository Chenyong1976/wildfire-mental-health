"""
2015-cohort matching for Western US wildfire study.

Treated:  Western counties whose FIRST qualifying wildfire was in 2015.
Controls: Western counties with NO qualifying wildfire in 2015–2019
          (true never-treated — counties with fires only in 2016–2019 excluded).

Three fire-size thresholds (separate matching each):
  T1 >= 1,000 ac  |  T2 >= 5,000 ac  |  T3 >= 25,000 ac

Matching: Mahalanobis 1:2 NN within WHP quintile, pairwise 50 km constraint.
Matching variables: WHP rank, RUCC, building density, pre-fire flag,
                    population 2014, income 2014, pre-suicide rate,
                    pre-overdose rate (all 2011–2014).

Outputs: matched_2015_T1_moderate_1k.csv
         matched_2015_T2_large_5k.csv
         matched_2015_T3_verylarge_25k.csv
         matching_2015_summary.csv
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

WESTERN_FIPS  = ['04','06','08','16','30','32','35','41','49','53','56']
MIN_POP       = 10_000
PAIR_BUFFER_M = 50_000   # 50 km pairwise geo constraint

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

# ── 1. County shapefile ────────────────────────────────────────────────────────
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

fires_2015_all = mtbs[
    (mtbs["YEAR"] == 2015) & (mtbs["FIRE_TYPE"] == "Wildfire")
].copy()
fires_1619_all = mtbs[
    mtbs["YEAR"].between(2016, 2019) & (mtbs["FIRE_TYPE"] == "Wildfire")
].copy()
fires_pre = mtbs[
    (mtbs["YEAR"] <= 2014) & (mtbs["FIRE_TYPE"] == "Wildfire") & (mtbs["ACRES"] >= 1000)
].copy()

def fires_to_county(fire_gdf, counties_gdf):
    fc = fire_gdf.copy()
    fc["geometry"] = fire_gdf.geometry.centroid
    joined = gpd.sjoin_nearest(
        fc[["FIRE_ID","YEAR","ACRES","geometry"]],
        counties_gdf[["GEOID","geometry"]],
        how="left"
    )
    return joined.dropna(subset=["GEOID","ACRES","YEAR"])

joined_pre  = fires_to_county(fires_pre,  counties)
pre_fire_geoids = set(joined_pre["GEOID"].unique())
joined_2015 = fires_to_county(fires_2015_all, counties)
joined_1619 = fires_to_county(fires_1619_all, counties)
print(f"  Pre-2015 fire counties: {len(pre_fire_geoids)}")
print(f"  2015 fire-county pairs: {len(joined_2015)}")

# ── 3. WHP ─────────────────────────────────────────────────────────────────────
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
ws_r = rucc_raw.sheet_by_index(0)
rh   = [str(ws_r.cell_value(0, c)) for c in range(ws_r.ncols)]
rrows = [[ws_r.cell_value(r, c) for c in range(ws_r.ncols)] for r in range(1, ws_r.nrows)]
rucc_df = pd.DataFrame(rrows, columns=rh)
fcol = [c for c in rucc_df.columns if "FIPS"  in c.upper()][0]
rcol = [c for c in rucc_df.columns if "RUCC"  in c.upper() and "2013" in c][0]
rucc_df["GEOID"] = rucc_df[fcol].apply(
    lambda x: str(int(x)).zfill(5) if pd.notna(x) and str(x).strip() != "" else None)
rucc_df = rucc_df.dropna(subset=["GEOID"])[["GEOID", rcol]].rename(
    columns={rcol: "RUCC2013"})
rucc_df["RUCC2013"] = pd.to_numeric(rucc_df["RUCC2013"], errors="coerce")

# ── 5. ACS 2014 ────────────────────────────────────────────────────────────────
print("Loading ACS 2014...")
acs_raw = pd.read_csv(f"{OUTDIR}/acs_covariates.csv", dtype={"GEOID": str})
acs_raw["GEOID"] = acs_raw["GEOID"].str.zfill(5)
acs_2014 = acs_raw[acs_raw["year"] == 2014][["GEOID","population","median_hh_income"]].copy()
acs_2014 = acs_2014.rename(columns={
    "population": "county_pop_2014", "median_hh_income": "median_hh_income_2014"})

# ── 6. Pre-treatment outcome rates (2011–2014 mean) ───────────────────────────
print("Computing pre-treatment outcome rates (2011–2014)...")
panel = pd.read_csv(f"{OUTDIR}/panel_analysis.csv", dtype={"GEOID": str}, low_memory=False)
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

# ── 7. Master Western county panel ────────────────────────────────────────────
print("Building master county panel...")
master = (counties[["GEOID","STATEFP","NAME","land_area_acres","cx","cy"]]
          .merge(whp_df,    on="GEOID", how="left")
          .merge(rucc_df,   on="GEOID", how="left")
          .merge(acs_2014,  on="GEOID", how="left")
          .merge(pre_agg,   on="GEOID", how="left"))
master["pre_fire_flag"] = master["GEOID"].isin(pre_fire_geoids).astype(int)
master = master.dropna(subset=["BP_NATIONAL_RANK","RUCC2013"])
for f in MATCH_FEATURES:
    if f in master.columns:
        master[f] = master[f].fillna(master[f].median())
master["WHP_quintile"] = pd.qcut(
    master["BP_NATIONAL_RANK"], q=5, labels=[1,2,3,4,5]).astype(int)
print(f"  Master panel: {len(master)} Western counties")

# ── 8. Loop over thresholds ────────────────────────────────────────────────────
all_summary = []

for tag, min_acres, label in THRESHOLDS:
    print(f"\n{'='*60}")
    print(f"THRESHOLD: {label}  (>= {min_acres:,} acres)")
    print(f"{'='*60}")

    # Counties with qualifying fire in 2015 (treated)
    f2015 = joined_2015[joined_2015["ACRES"] >= min_acres].copy()
    treated_agg = (f2015.groupby("GEOID")
                   .agg(n_fires_2015=("FIRE_ID",  "nunique"),
                        acres_2015  =("ACRES",     lambda x: float(x.sum())))
                   .reset_index())
    treated_set = set(treated_agg["GEOID"])

    # Counties with qualifying fire in 2016–2019 (excluded from controls)
    f1619 = joined_1619[joined_1619["ACRES"] >= min_acres].copy()
    later_treated_set = set(f1619["GEOID"].unique()) - treated_set

    print(f"  2015-treated counties: {len(treated_set)}")
    print(f"  2016-2019-treated (excluded from controls): {len(later_treated_set)}")

    # Build panel with treatment indicators
    panel_t = master.copy()
    panel_t["treated"] = panel_t["GEOID"].isin(treated_set).astype(int)
    panel_t = panel_t.merge(
        treated_agg[["GEOID","n_fires_2015","acres_2015"]], on="GEOID", how="left")
    panel_t["n_fires_2015"] = panel_t["n_fires_2015"].fillna(0)
    panel_t["acres_2015"]   = panel_t["acres_2015"].fillna(0.0)
    panel_t["pct_burned_2015"] = np.where(
        panel_t["land_area_acres"] > 0,
        panel_t["acres_2015"] / panel_t["land_area_acres"] * 100,
        0.0)

    # Pop filter
    n_before = len(panel_t)
    panel_t  = panel_t[panel_t["county_pop_2014"] >= MIN_POP].copy()
    print(f"  After pop >= {MIN_POP:,}: {len(panel_t)} "
          f"(dropped {n_before - len(panel_t)})")

    treated_df  = panel_t[panel_t["treated"] == 1].reset_index(drop=True)
    # Controls = never-treated: exclude later-treated counties
    controls_df = panel_t[
        (panel_t["treated"] == 0) &
        (~panel_t["GEOID"].isin(later_treated_set))
    ].reset_index(drop=True)

    print(f"  Treated: {len(treated_df)}  |  Never-treated controls: {len(controls_df)}")

    if len(treated_df) == 0:
        print("  WARNING: no treated counties — skipping")
        continue
    if len(controls_df) == 0:
        print("  WARNING: no control counties — skipping")
        continue

    # ── Mahalanobis matching within WHP quintile ───────────────────────────────
    results = []
    for q in sorted(treated_df["WHP_quintile"].unique()):
        t_q = treated_df[treated_df["WHP_quintile"] == q].reset_index(drop=True)
        c_q = controls_df[controls_df["WHP_quintile"] == q].reset_index(drop=True)

        if len(c_q) == 0:
            # Fallback: relax quintile and use nearest overall quintile controls
            print(f"  Q{q}: no exact-quintile controls — using nearest quintile fallback")
            c_q = controls_df.iloc[
                np.argsort(np.abs(
                    controls_df["WHP_quintile"].values - q
                ))[:max(10, len(treated_df)*2)]
            ].reset_index(drop=True)

        t_feat = t_q[MATCH_FEATURES].values.astype(float)
        c_feat = c_q[MATCH_FEATURES].values.astype(float)
        t_geo  = t_q[["cx","cy"]].values.astype(float)
        c_geo  = c_q[["cx","cy"]].values.astype(float)

        all_feat = np.vstack([t_feat, c_feat])
        cov_mat  = np.cov(all_feat.T)
        reg      = 0.01 * np.trace(cov_mat) / len(MATCH_FEATURES) * np.eye(len(MATCH_FEATURES))
        VI       = np.linalg.inv(cov_mat + reg)

        mah_dists = cdist(t_feat, c_feat, metric="mahalanobis", VI=VI)
        geo_dists = cdist(t_geo,  c_geo)
        n_match   = min(2, len(c_q))

        for i in range(len(t_q)):
            t_row = t_q.iloc[i]
            d_i   = mah_dists[i].copy()
            d_i[geo_dists[i] < PAIR_BUFFER_M] = np.inf
            valid = [j for j in np.argsort(d_i)[:n_match] if d_i[j] < np.inf]
            if not valid:
                valid = list(np.argsort(mah_dists[i])[:n_match])
            for rank, idx in enumerate(valid, 1):
                c_row = c_q.iloc[idx]
                results.append({
                    "treated_GEOID"        : t_row["GEOID"],
                    "treated_NAME"         : t_row["NAME"],
                    "treated_STATE"        : t_row["STATEFP"],
                    "treated_WHP_rank"     : round(float(t_row["BP_NATIONAL_RANK"]), 3),
                    "treated_RUCC"         : int(t_row["RUCC2013"]),
                    "treated_BldDE"        : round(float(t_row["BUILDINGS_FRACTION_DE"]), 3),
                    "treated_pre_fire"     : int(t_row["pre_fire_flag"]),
                    "treated_pop_2014"     : round(float(t_row["county_pop_2014"])),
                    "treated_income_2014"  : round(float(t_row["median_hh_income_2014"])),
                    "treated_pre_suicide"  : round(float(t_row["pre_suicide_rate"]), 3),
                    "treated_pre_overdose" : round(float(t_row["pre_overdose_rate"]), 3),
                    "treated_WHP_quintile" : q,
                    "treated_acres_2015"   : round(float(t_row["acres_2015"]), 0),
                    "treated_pct_burned_2015": round(float(t_row["pct_burned_2015"]), 4),
                    "control_GEOID"        : c_row["GEOID"],
                    "control_NAME"         : c_row["NAME"],
                    "control_STATE"        : c_row["STATEFP"],
                    "control_WHP_rank"     : round(float(c_row["BP_NATIONAL_RANK"]), 3),
                    "control_RUCC"         : int(c_row["RUCC2013"]),
                    "control_BldDE"        : round(float(c_row["BUILDINGS_FRACTION_DE"]), 3),
                    "control_pre_fire"     : int(c_row["pre_fire_flag"]),
                    "control_pop_2014"     : round(float(c_row["county_pop_2014"])),
                    "control_income_2014"  : round(float(c_row["median_hh_income_2014"])),
                    "control_pre_suicide"  : round(float(c_row["pre_suicide_rate"]), 3),
                    "control_pre_overdose" : round(float(c_row["pre_overdose_rate"]), 3),
                    "match_rank"           : rank,
                    "mahalanobis_dist"     : round(float(mah_dists[i][idx]), 4),
                })

    if not results:
        print("  ERROR: no matched pairs — skipping")
        continue

    matched = pd.DataFrame(results)
    primary = matched[matched["match_rank"] == 1]

    print(f"\n  Matched: {len(primary)} treated | "
          f"{len(primary)*2 if len(primary)*2 <= len(matched) else len(matched)} total pairs")

    # ── Balance ────────────────────────────────────────────────────────────────
    print("\n  === MATCHING BALANCE ===")
    bvars = [
        ("WHP rank",     "treated_WHP_rank",    "control_WHP_rank"),
        ("RUCC",         "treated_RUCC",         "control_RUCC"),
        ("Bld frac DE",  "treated_BldDE",        "control_BldDE"),
        ("Pre-fire",     "treated_pre_fire",     "control_pre_fire"),
        ("Pop 2014",     "treated_pop_2014",     "control_pop_2014"),
        ("Income",       "treated_income_2014",  "control_income_2014"),
        ("Pre-suicide",  "treated_pre_suicide",  "control_pre_suicide"),
        ("Pre-overdose", "treated_pre_overdose", "control_pre_overdose"),
    ]
    for lbl, tc, cc in bvars:
        t_m = primary[tc].astype(float).mean()
        c_m = primary[cc].astype(float).mean()
        pct = abs(t_m - c_m) / max(abs(t_m), 1e-9) * 100
        print(f"  {lbl:<14} treated={t_m:>12.3f}  control={c_m:>12.3f}  ({pct:.1f}% diff)")
    print(f"  Mahal dist:  mean={primary['mahalanobis_dist'].mean():.3f}  "
          f"p90={primary['mahalanobis_dist'].quantile(0.9):.3f}")
    print(f"  pct_burned_2015: treated mean={primary['treated_pct_burned_2015'].mean():.2f}%  "
          f"median={primary['treated_pct_burned_2015'].median():.2f}%  "
          f"p90={primary['treated_pct_burned_2015'].quantile(0.9):.2f}%")

    out_path = f"{OUTDIR}/matched_2015_{tag}.csv"
    matched.to_csv(out_path, index=False)
    print(f"\n  Saved: matched_2015_{tag}.csv ({len(matched)} rows)")

    all_summary.append({
        "tag": tag, "label": label, "min_acres": min_acres,
        "n_treated": len(primary),
        "n_unique_controls": primary["control_GEOID"].nunique(),
        "mean_pct_burned": round(primary["treated_pct_burned_2015"].mean(), 2),
        "p90_pct_burned":  round(primary["treated_pct_burned_2015"].quantile(0.9), 2),
    })

# ── Summary ────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("2015-COHORT MATCHING SUMMARY")
print("="*60)
summary_df = pd.DataFrame(all_summary)
print(summary_df.to_string(index=False))
summary_df.to_csv(f"{OUTDIR}/matching_2015_summary.csv", index=False)
print("\nDone — run build_panel_2015.py next.")
