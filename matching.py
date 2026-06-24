"""
WHP-matched control group construction for wildfire counties 2015-2019.
Study area: CONUS only (excludes Alaska and Hawaii).

Matching variables (Mahalanobis distance within WHP quintile):
  1. BP_NATIONAL_RANK     - USFS burn probability national rank (2014 WHP)
  2. RUCC2013             - Rural-Urban Continuum Code (rurality proxy)
  3. BUILDINGS_FRACTION_DE - share of buildings in Direct Exposure zone
  4. pre_fire_flag        - binary: any MTBS wildfire >=1000 ac in county <=2014
  5. county_pop_2014      - ACS 2014 total population
  6. median_hh_income_2014 - ACS 2014 median household income
"""
import warnings; warnings.filterwarnings('ignore')
import zipfile, os, time, requests
import geopandas as gpd
import pandas as pd
import numpy as np
import openpyxl
import xlrd
from scipy.spatial.distance import cdist

BASE   = r"C:\Users\chenyon\Research Paper 2026(1)\data\raw"
OUTDIR = r"C:\Users\chenyon\Research Paper 2026(1)"
CENSUS_API_KEY = "5e9b8c7b6f13e5d5f10b100ebf88eba8c778a442"

# ── 1. County shapefile ────────────────────────────────────────────────────────
with zipfile.ZipFile(f"{BASE}/tl_2020_us_county.zip") as z:
    z.extractall(f"{BASE}/counties")
counties = gpd.read_file(f"{BASE}/counties").to_crs("EPSG:5070")
counties["GEOID"] = counties["GEOID"].astype(str).str.zfill(5)

# CONUS only — exclude AK (02) and HI (15) plus non-state territories
valid_fips = [str(i).zfill(2) for i in range(1, 57)
              if i not in [2, 3, 7, 14, 15, 43, 52]]
counties = counties[counties["STATEFP"].isin(valid_fips)][
    ["GEOID", "STATEFP", "NAME", "geometry"]
].copy()
print(f"CONUS counties: {len(counties)}")

# ── 2. MTBS fire perimeters — ALL years ──────────────────────────────────────
mtbs = gpd.read_file(
    f"{BASE}/mtbs_perims/S_USA.MTBS_BURN_AREA_BOUNDARY.shp"
).to_crs("EPSG:5070")
mtbs["YEAR"]  = pd.to_numeric(mtbs["YEAR"], errors="coerce")
mtbs["ACRES"] = pd.to_numeric(mtbs["ACRES"], errors="coerce")
mtbs["FIRE_TYPE"] = mtbs["FIRE_TYPE"].astype(str).str.strip()

# Treatment fires: Wildfire 2015-2019, >=1000 acres
fires_treat = mtbs[
    mtbs["YEAR"].between(2015, 2019) &
    (mtbs["FIRE_TYPE"] == "Wildfire") &
    (mtbs["ACRES"] >= 1000)
].copy()
print(f"MTBS wildfires 2015-2019 >=1000 ac: {len(fires_treat)}")

# Pre-treatment fires: Wildfire <=2014, >=1000 acres
fires_pre = mtbs[
    (mtbs["YEAR"] <= 2014) &
    (mtbs["FIRE_TYPE"] == "Wildfire") &
    (mtbs["ACRES"] >= 1000)
].copy()
print(f"MTBS wildfires <=2014 >=1000 ac: {len(fires_pre)}")

def fires_to_county(fire_gdf, counties_gdf):
    """Spatial join fire centroids to nearest county."""
    fc = fire_gdf.copy()
    fc["geometry"] = fire_gdf.geometry.centroid
    joined = gpd.sjoin_nearest(
        fc[["FIRE_ID", "YEAR", "ACRES", "geometry"]],
        counties_gdf[["GEOID", "NAME", "geometry"]].rename(columns={"NAME": "COUNTY_NAME"}),
        how="left"
    )
    return joined

# Treatment counties
joined_treat = fires_to_county(fires_treat, counties)
fire_counties = (
    joined_treat.groupby("GEOID")
    .agg(
        fire_years  = ("YEAR", lambda x: sorted(x.astype(int).unique().tolist())),
        n_fires     = ("FIRE_ID", "nunique"),
        total_acres = ("ACRES", lambda x: x.astype(float).sum()),
        first_year  = ("YEAR", lambda x: int(x.astype(int).min()))
    )
    .reset_index()
)
fire_counties["treated"] = 1
print(f"Treated counties (fire 2015-2019): {len(fire_counties)}")
print(f"  Year distribution:")
for yr, cnt in sorted(
    joined_treat.drop_duplicates(["GEOID","YEAR"]).groupby("YEAR")["GEOID"].count().items()
):
    print(f"    {yr}: {cnt} counties")

# Pre-fire flag (any Wildfire >=1000 ac in county, <=2014)
joined_pre = fires_to_county(fires_pre, counties)
pre_fire_geoids = set(joined_pre["GEOID"].dropna().unique())
print(f"Counties with any pre-2015 wildfire: {len(pre_fire_geoids)}")

# ── 3. WHP data ───────────────────────────────────────────────────────────────
wb = openpyxl.load_workbook(f"{BASE}/wrc_county_data.xlsx", read_only=True)
ws = wb["Counties"]
rows = list(ws.iter_rows(values_only=True))
headers = rows[0]
whp_df = pd.DataFrame(rows[1:], columns=headers)
whp_df["GEOID"] = whp_df["GEOID"].astype(str).str.zfill(5)
whp_df = whp_df[["GEOID", "BP_NATIONAL_RANK", "RISK_NATIONAL_RANK",
                  "BUILDINGS_FRACTION_ME", "BUILDINGS_FRACTION_IE",
                  "BUILDINGS_FRACTION_DE"]].copy()
whp_df = whp_df.dropna(subset=["BP_NATIONAL_RANK"])
print(f"WHP county records: {len(whp_df)}")
wb.close()

# ── 4. RUCC 2013 ──────────────────────────────────────────────────────────────
rucc_raw = xlrd.open_workbook(f"{BASE}/rucc2013.xls")
ws_rucc  = rucc_raw.sheet_by_index(0)
rucc_headers = [str(ws_rucc.cell_value(0, c)) for c in range(ws_rucc.ncols)]
rucc_rows = [[ws_rucc.cell_value(r, c) for c in range(ws_rucc.ncols)]
             for r in range(1, ws_rucc.nrows)]
rucc_df = pd.DataFrame(rucc_rows, columns=rucc_headers)
fips_col = [c for c in rucc_df.columns if "FIPS" in c.upper()][0]
rucc_col = [c for c in rucc_df.columns if "RUCC" in c.upper() and "2013" in c][0]
rucc_df["GEOID"] = rucc_df[fips_col].apply(
    lambda x: str(int(x)).zfill(5) if pd.notna(x) and str(x).strip() != "" else None
)
rucc_df = rucc_df.dropna(subset=["GEOID"])
rucc_df = rucc_df[["GEOID", rucc_col]].rename(columns={rucc_col: "RUCC2013"})
rucc_df["RUCC2013"] = pd.to_numeric(rucc_df["RUCC2013"], errors="coerce")
print(f"RUCC records: {len(rucc_df)}")

# ── 5. ACS 2014: county population and median HH income ──────────────────────
print("\nDownloading ACS 2014 (county population + median HH income)...")

def fetch_acs_state_2014(state_fips):
    vars_str = "B01003_001E,B19013_001E"
    url = (
        f"https://api.census.gov/data/2014/acs/acs5"
        f"?get=NAME,{vars_str}&for=county:*&in=state:{state_fips}"
        f"&key={CENSUS_API_KEY}"
    )
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            data = r.json()
            df = pd.DataFrame(data[1:], columns=data[0])
            df["GEOID"] = df["state"].str.zfill(2) + df["county"].str.zfill(3)
            df["county_pop_2014"]        = pd.to_numeric(df["B01003_001E"], errors="coerce")
            df["median_hh_income_2014"]  = pd.to_numeric(df["B19013_001E"], errors="coerce")
            df["median_hh_income_2014"]  = df["median_hh_income_2014"].replace(-666666666, np.nan)
            return df[["GEOID", "county_pop_2014", "median_hh_income_2014"]]
    except Exception as e:
        print(f"  ACS fetch error state {state_fips}: {e}")
    return None

acs_chunks = []
for state in sorted(valid_fips):
    df_s = fetch_acs_state_2014(state)
    if df_s is not None:
        acs_chunks.append(df_s)
    time.sleep(0.05)

if acs_chunks:
    acs_2014 = pd.concat(acs_chunks, ignore_index=True)
    print(f"  ACS 2014 records: {len(acs_2014)} | "
          f"pop non-null: {acs_2014['county_pop_2014'].notna().sum()} | "
          f"income non-null: {acs_2014['median_hh_income_2014'].notna().sum()}")
else:
    print("  WARNING: ACS 2014 download failed. Using NaN for pop/income.")
    acs_2014 = pd.DataFrame(columns=["GEOID", "county_pop_2014", "median_hh_income_2014"])

# ── 6. Master county panel ────────────────────────────────────────────────────
panel = counties[["GEOID", "STATEFP", "NAME"]].merge(whp_df, on="GEOID", how="left")
panel = panel.merge(rucc_df, on="GEOID", how="left")
panel = panel.merge(acs_2014, on="GEOID", how="left")
panel = panel.merge(
    fire_counties[["GEOID", "treated", "n_fires", "total_acres", "first_year", "fire_years"]],
    on="GEOID", how="left"
)
panel["treated"]      = panel["treated"].fillna(0).astype(int)
panel["pre_fire_flag"] = panel["GEOID"].isin(pre_fire_geoids).astype(int)

# Drop counties missing WHP or RUCC (required for matching stratum)
panel = panel.dropna(subset=["BP_NATIONAL_RANK", "RUCC2013"])
print(f"\nMaster panel: {len(panel)} counties "
      f"({panel['treated'].sum()} treated, {(panel['treated']==0).sum()} potential controls)")

# ── 7. WHP quintile assignment ────────────────────────────────────────────────
panel["WHP_quintile"] = pd.qcut(
    panel["BP_NATIONAL_RANK"], q=5, labels=[1, 2, 3, 4, 5]
).astype(int)

print("\nTreated counties by WHP quintile:")
print(panel[panel["treated"]==1]["WHP_quintile"].value_counts().sort_index().to_string())

# ── 8. Mahalanobis distance matching within WHP quintile ─────────────────────
MATCH_FEATURES = [
    "BP_NATIONAL_RANK",
    "RUCC2013",
    "BUILDINGS_FRACTION_DE",
    "pre_fire_flag",
    "county_pop_2014",
    "median_hh_income_2014",
]

# Impute remaining NAs with global median (within treated+control pool)
for f in MATCH_FEATURES:
    med = panel[f].median()
    panel[f] = panel[f].fillna(med)

# Global inverse covariance matrix (regularized) — computed across all counties
feat_matrix = panel[MATCH_FEATURES].values.astype(float)
cov_mat = np.cov(feat_matrix.T)
# Tikhonov regularization: add 0.01 * trace / n * I to avoid singularity
reg = 0.01 * np.trace(cov_mat) / len(MATCH_FEATURES) * np.eye(len(MATCH_FEATURES))
cov_mat_reg = cov_mat + reg
VI = np.linalg.inv(cov_mat_reg)

treated_df  = panel[panel["treated"] == 1].copy()
controls_df = panel[panel["treated"] == 0].copy()

results  = []
unmatched = []

for q in sorted(treated_df["WHP_quintile"].unique()):
    t_q = treated_df[treated_df["WHP_quintile"] == q].reset_index(drop=True)
    c_q = controls_df[controls_df["WHP_quintile"] == q].reset_index(drop=True)

    if len(c_q) == 0:
        print(f"  WARNING: no controls in quintile {q}")
        unmatched.append(q)
        continue

    t_feat = t_q[MATCH_FEATURES].values.astype(float)
    c_feat = c_q[MATCH_FEATURES].values.astype(float)

    # Full pairwise Mahalanobis distance matrix
    dists = cdist(t_feat, c_feat, metric="mahalanobis", VI=VI)

    n_match = min(2, len(c_q))
    for i in range(len(t_q)):
        t_row = t_q.iloc[i]
        sorted_idx = np.argsort(dists[i])
        for rank, idx in enumerate(sorted_idx[:n_match], 1):
            c_row = c_q.iloc[idx]
            results.append({
                "treated_GEOID"          : t_row["GEOID"],
                "treated_NAME"           : t_row["NAME"],
                "treated_STATE"          : t_row["STATEFP"],
                "treated_WHP_rank"       : round(float(t_row["BP_NATIONAL_RANK"]), 3),
                "treated_RUCC"           : int(t_row["RUCC2013"]),
                "treated_BldDE"          : round(float(t_row["BUILDINGS_FRACTION_DE"]), 3),
                "treated_pre_fire"       : int(t_row["pre_fire_flag"]),
                "treated_pop_2014"       : round(float(t_row["county_pop_2014"])),
                "treated_income_2014"    : round(float(t_row["median_hh_income_2014"])),
                "treated_WHP_quintile"   : q,
                "treated_first_fire_yr"  : int(t_row["first_year"]) if pd.notna(t_row["first_year"]) else None,
                "treated_total_acres"    : round(float(t_row["total_acres"]), 0) if pd.notna(t_row["total_acres"]) else 0,
                "control_GEOID"          : c_row["GEOID"],
                "control_NAME"           : c_row["NAME"],
                "control_STATE"          : c_row["STATEFP"],
                "control_WHP_rank"       : round(float(c_row["BP_NATIONAL_RANK"]), 3),
                "control_RUCC"           : int(c_row["RUCC2013"]),
                "control_BldDE"          : round(float(c_row["BUILDINGS_FRACTION_DE"]), 3),
                "control_pre_fire"       : int(c_row["pre_fire_flag"]),
                "control_pop_2014"       : round(float(c_row["county_pop_2014"])),
                "control_income_2014"    : round(float(c_row["median_hh_income_2014"])),
                "match_rank"             : rank,
                "mahalanobis_dist"       : round(float(dists[i][idx]), 4),
            })

matched = pd.DataFrame(results)
print(f"\nMatched pairs (1:1): {len(matched[matched['match_rank']==1])}")
print(f"Matched pairs (1:2): {len(matched[matched['match_rank']==2])}")
if unmatched:
    print(f"Unmatched quintiles: {unmatched}")

# ── 9. Balance diagnostics ───────────────────────────────────────────────────
print("\n=== MATCHING BALANCE (primary matches only) ===")
primary = matched[matched["match_rank"] == 1]
for feat, tc, cc, label in [
    ("BP_NATIONAL_RANK",      "treated_WHP_rank",    "control_WHP_rank",    "WHP rank"),
    ("RUCC2013",              "treated_RUCC",         "control_RUCC",        "RUCC2013"),
    ("BUILDINGS_FRACTION_DE", "treated_BldDE",        "control_BldDE",       "Bld frac DE"),
    ("pre_fire_flag",         "treated_pre_fire",     "control_pre_fire",    "Pre-fire flag"),
    ("county_pop_2014",       "treated_pop_2014",     "control_pop_2014",    "Pop 2014"),
    ("median_hh_income_2014", "treated_income_2014",  "control_income_2014", "Median HH income"),
]:
    t_mean = primary[tc].astype(float).mean()
    c_mean = primary[cc].astype(float).mean()
    diff   = t_mean - c_mean
    pct    = abs(diff / t_mean * 100) if t_mean != 0 else 0
    print(f"  {label:<22} treated={t_mean:>10.2f}  control={c_mean:>10.2f}  "
          f"diff={diff:+.3f} ({pct:.1f}%)")

print(f"\nMahalanobis distance (primary match): "
      f"mean={primary['mahalanobis_dist'].mean():.3f}  "
      f"p90={primary['mahalanobis_dist'].quantile(0.9):.3f}")

# ── 10. Save ──────────────────────────────────────────────────────────────────
matched.to_csv(f"{OUTDIR}/matched_county_pairs.csv", index=False)
print(f"\nSaved: matched_county_pairs.csv ({len(matched)} rows)")

summary = matched[matched["match_rank"] == 1][[
    "treated_GEOID", "treated_NAME", "treated_STATE",
    "treated_first_fire_yr", "treated_total_acres",
    "treated_WHP_rank", "treated_RUCC", "treated_BldDE",
    "treated_pre_fire", "treated_pop_2014", "treated_income_2014",
    "control_GEOID", "control_NAME", "control_STATE",
    "control_WHP_rank", "control_RUCC", "control_BldDE",
    "control_pre_fire", "control_pop_2014", "control_income_2014",
    "mahalanobis_dist"
]]
summary.to_csv(f"{OUTDIR}/matched_pairs_primary.csv", index=False)
print(f"Saved: matched_pairs_primary.csv ({len(summary)} rows)")
print("\nSample:")
print(summary.head(5).to_string(index=False))
