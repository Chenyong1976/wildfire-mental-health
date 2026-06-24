"""
Robustness: Three fire-size thresholds for treatment definition.
T1: >= 1,000 ac  (Moderate+, current baseline)
T2: >= 5,000 ac  (Large+)
T3: >= 25,000 ac (Very Large)

Redefines cohort_g in panel_analysis.csv for each threshold:
  - County is treated only if it had at least one qualifying fire (>= threshold)
  - Counties below threshold have cohort_g = 0 (no-treatment)
  - cohort_g = first year with a qualifying fire
"""
import warnings; warnings.filterwarnings('ignore')
import zipfile, os
import geopandas as gpd
import pandas as pd
import numpy as np

BASE   = r"C:\Users\chenyon\Research Paper 2026(1)\data\raw"
OUTDIR = r"C:\Users\chenyon\Research Paper 2026(1)"

# ── Load MTBS fires 2015-2019 ─────────────────────────────────────────────────
print("Loading MTBS fire perimeters...")
mtbs = gpd.read_file(
    f"{BASE}/mtbs_perims/S_USA.MTBS_BURN_AREA_BOUNDARY.shp"
).to_crs("EPSG:5070")
mtbs["YEAR"]      = pd.to_numeric(mtbs["YEAR"],  errors="coerce")
mtbs["ACRES"]     = pd.to_numeric(mtbs["ACRES"], errors="coerce")
mtbs["FIRE_TYPE"] = mtbs["FIRE_TYPE"].astype(str).str.strip()

fires_all = mtbs[
    mtbs["YEAR"].between(2015, 2019) &
    (mtbs["FIRE_TYPE"] == "Wildfire")
].copy()
print(f"  Total MTBS wildfires 2015-2019: {len(fires_all)}")
print(f"  Acres: min={fires_all['ACRES'].min():.0f}  max={fires_all['ACRES'].max():.0f}")

# ── Load CONUS counties ───────────────────────────────────────────────────────
print("\nLoading county boundaries...")
counties_dir = f"{BASE}/counties"
if not os.path.isdir(counties_dir):
    with zipfile.ZipFile(f"{BASE}/tl_2020_us_county.zip") as z:
        z.extractall(counties_dir)
counties = gpd.read_file(counties_dir).to_crs("EPSG:5070")
counties["GEOID"] = counties["GEOID"].astype(str).str.zfill(5)
valid_fips = [str(i).zfill(2) for i in range(1, 57)
              if i not in [2, 3, 7, 14, 15, 43, 52]]
counties = counties[counties["STATEFP"].isin(valid_fips)][
    ["GEOID", "geometry"]
].copy()
print(f"  CONUS counties: {len(counties)}")

# ── Spatial join: fire centroids -> counties ─────────────────────────────────
print("\nSpatially joining fires to counties...")
fires_c = fires_all.copy()
fires_c["geometry"] = fires_all.geometry.centroid
joined = gpd.sjoin_nearest(
    fires_c[["FIRE_ID", "YEAR", "ACRES", "geometry"]],
    counties[["GEOID", "geometry"]],
    how="left"
)
joined = joined.dropna(subset=["GEOID", "ACRES", "YEAR"])
print(f"  Fire-county pairs: {len(joined):,}")

# ── Load existing panel ───────────────────────────────────────────────────────
panel = pd.read_csv(f"{OUTDIR}/panel_analysis.csv", dtype={"GEOID": str})
panel["GEOID"] = panel["GEOID"].str.zfill(5)
print(f"\nExisting panel: {len(panel):,} rows | {panel['GEOID'].nunique()} counties")
print(f"Current cohort distribution:")
orig_cohorts = (panel[panel["cohort_g"] > 0]
                .drop_duplicates("GEOID")["cohort_g"]
                .value_counts().sort_index())
print(orig_cohorts.to_string())

# ── Build three panel variants ────────────────────────────────────────────────
THRESHOLDS = [
    ("T1_moderate_1k",   1_000,  "Moderate+ (>=1,000 ac)"),
    ("T2_large_5k",      5_000,  "Large+    (>=5,000 ac)"),
    ("T3_verylarge_25k", 25_000, "Very Large (>=25,000 ac)"),
]

print("\n" + "="*60)
summary_rows = []

for tag, min_acres, label in THRESHOLDS:
    print(f"\n{label}")
    print(f"  Filtering fires >= {min_acres:,} acres...")

    fires_sub = joined[joined["ACRES"] >= min_acres].copy()
    print(f"  Qualifying fires: {len(fires_sub):,}")

    # Per county: first year with a qualifying fire, max single fire size
    fire_agg = (
        fires_sub.groupby("GEOID")
        .agg(
            first_year = ("YEAR",    lambda x: int(x.astype(int).min())),
            n_fires    = ("FIRE_ID", "nunique"),
            max_acres  = ("ACRES",   "max"),
        )
        .reset_index()
    )
    geoid_to_first = dict(zip(fire_agg["GEOID"], fire_agg["first_year"]))

    # Copy panel, update cohort_g
    panel_rb = panel.copy()
    panel_rb["cohort_g"] = (
        panel_rb["GEOID"]
        .map(geoid_to_first)
        .fillna(0)
        .astype(int)
    )

    # Recompute event_time from new cohort_g
    panel_rb["event_time"] = np.where(
        panel_rb["cohort_g"] > 0,
        panel_rb["year"] - panel_rb["cohort_g"],
        np.nan
    )

    n_treated = panel_rb[panel_rb["cohort_g"] > 0]["GEOID"].nunique()
    n_control = panel_rb[panel_rb["cohort_g"] == 0]["GEOID"].nunique()
    cohorts   = (panel_rb[panel_rb["cohort_g"] > 0]
                 .drop_duplicates("GEOID")["cohort_g"]
                 .value_counts().sort_index().to_dict())

    print(f"  Treated counties : {n_treated}")
    print(f"  Control counties : {n_control}")
    print(f"  Cohort breakdown : {cohorts}")

    out_path = f"{OUTDIR}/panel_robustness_{tag}.csv"
    panel_rb.to_csv(out_path, index=False)
    print(f"  Saved: panel_robustness_{tag}.csv")

    summary_rows.append({
        "tag": tag, "label": label, "min_acres": min_acres,
        "n_treated": n_treated, "n_control": n_control,
        "g2015": cohorts.get(2015, 0), "g2016": cohorts.get(2016, 0),
        "g2017": cohorts.get(2017, 0), "g2018": cohorts.get(2018, 0),
        "g2019": cohorts.get(2019, 0),
    })

# ── Summary table ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("THRESHOLD SUMMARY")
print("="*60)
summary_df = pd.DataFrame(summary_rows)
print(summary_df.to_string(index=False))
summary_df.to_csv(f"{OUTDIR}/robustness_threshold_summary.csv", index=False)
print(f"\nSaved: robustness_threshold_summary.csv")
print("Done — ready for estimate_robustness.R")
