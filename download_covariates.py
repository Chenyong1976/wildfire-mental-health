"""
Download and process additional covariates for the county × year panel.

Sources handled here:
  - BLS LAUS (already saved to disk) → unemployment_rate
  - CDC SVI 2020  → social vulnerability index components
  - HRSA HPSA    → mental health provider shortage flag
  - FEMA fire declarations → fire_declaration indicator (mechanism variable)
  - Census API    → ACS (requires user to provide API key)
"""

import warnings; warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np
import requests
import os

OUTDIR   = r"C:\Users\chenyon\Research Paper 2026(1)"
RAW_DIR  = r"C:\Users\chenyon\Research Paper 2026(1)\data\raw"

panel    = pd.read_csv(f"{OUTDIR}/panel_skeleton.csv", dtype={"GEOID": str})
panel["GEOID"] = panel["GEOID"].str.zfill(5)
target_geoids  = set(panel["GEOID"].unique())
YEARS    = list(range(2011, 2020)) + list(range(2021, 2024))

# ─── 1. BLS LAUS ──────────────────────────────────────────────────────────────
print("=== Processing BLS LAUS ===")
laus_path = f"{RAW_DIR}/la.data.64.County.txt"

if os.path.exists(laus_path):
    # Only need type=3 (unemployment rate), period=M13 (annual avg)
    chunk_list = []
    chunksize  = 500_000
    reader = pd.read_csv(
        laus_path, sep="\t",
        names=["series_id","year","period","value","footnote"],
        skiprows=1, dtype={"series_id": str, "year": int, "value": str},
        chunksize=chunksize
    )
    for chunk in reader:
        mask = (
            chunk["series_id"].str.strip().str.endswith("3") &
            (chunk["period"].str.strip() == "M13") &
            chunk["year"].isin(YEARS)
        )
        sub = chunk[mask].copy()
        if len(sub) > 0:
            sub["GEOID"] = sub["series_id"].str.strip().str[5:10]
            sub = sub[sub["GEOID"].isin(target_geoids)]
            chunk_list.append(sub[["GEOID","year","value"]])

    if chunk_list:
        laus = pd.concat(chunk_list, ignore_index=True)
        laus["unemployment_rate"] = pd.to_numeric(laus["value"].str.strip(), errors="coerce")
        laus = laus[["GEOID","year","unemployment_rate"]].dropna()
        laus.to_csv(f"{OUTDIR}/bls_laus_covariates.csv", index=False)
        print(f"  Saved: bls_laus_covariates.csv  ({len(laus):,} rows)")
        print(f"  Coverage: {laus['GEOID'].nunique()} counties, years {sorted(laus['year'].unique())}")
        print(f"  Unemployment rate: mean={laus['unemployment_rate'].mean():.2f}, range [{laus['unemployment_rate'].min():.1f}, {laus['unemployment_rate'].max():.1f}]")
    else:
        print("  No matching rows found.")
        laus = pd.DataFrame()
else:
    print(f"  File not found: {laus_path}")
    laus = pd.DataFrame()

# ─── 2. CDC PLACES — depression & poor mental health (replaces SVI direct download) ──
# SVI no longer has a direct CSV download URL; it requires an interactive form at:
#   https://svi.cdc.gov/dataDownloads/data-download.html
# CDC PLACES provides county-level depression and mental health estimates derived from
# BRFSS using small-area estimation — serves as both an outcome variable and a
# cross-check against Medicaid claims data.
print("\n=== Downloading CDC PLACES (depression & mental health) ===")
PLACES_URL = "https://data.cdc.gov/api/views/swc5-untb/rows.csv?accessType=DOWNLOAD"
try:
    r = requests.get(PLACES_URL, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code == 200:
        from io import StringIO
        places_raw = pd.read_csv(StringIO(r.text), dtype={"LocationID": str})
        # Keep mental-health-relevant measures and age-adjusted prevalence
        mh_ids = {"DEPRESSION", "MHLTH", "BPHIGH", "CSMOKING", "SLEEP"}
        mh_type = "Age-adjusted prevalence"
        places_mh = places_raw[
            places_raw["MeasureId"].isin(mh_ids) &
            (places_raw["DataValueTypeID"] == "AgeAdjPrv")
        ].copy()
        places_mh["GEOID"] = places_mh["LocationID"].str.zfill(5)
        places_mh = places_mh[places_mh["GEOID"].isin(target_geoids)].copy()
        places_mh["Data_Value"] = pd.to_numeric(places_mh["Data_Value"], errors="coerce")
        places_pivot = (
            places_mh.pivot_table(
                index=["GEOID", "Year"],
                columns="MeasureId",
                values="Data_Value",
                aggfunc="mean"
            )
            .reset_index()
            .rename(columns={
                "Year":       "year",
                "DEPRESSION": "pct_depression",
                "MHLTH":      "pct_poor_mental_health_days",
                "CSMOKING":   "pct_current_smoking",
                "BPHIGH":     "pct_high_bp",
                "SLEEP":      "pct_sleep_deprivation",
            })
        )
        places_pivot.columns.name = None
        places_pivot["year"] = pd.to_numeric(places_pivot["year"], errors="coerce").astype("Int64")
        places_pivot = places_pivot[places_pivot["year"].isin(YEARS)]
        places_pivot.to_csv(f"{OUTDIR}/cdc_places_outcomes.csv", index=False)
        n_dep = places_pivot["pct_depression"].notna().sum() if "pct_depression" in places_pivot.columns else 0
        print(f"  Saved: cdc_places_outcomes.csv  ({len(places_pivot):,} rows)")
        print(f"  Depression obs: {n_dep:,}")
        if "pct_depression" in places_pivot.columns:
            print(f"  Mean depression prevalence: {places_pivot['pct_depression'].mean():.2f}%")
    else:
        print(f"  PLACES HTTP {r.status_code}")
        places_pivot = pd.DataFrame()
except Exception as e:
    print(f"  PLACES download failed: {e}")
    places_pivot = pd.DataFrame()

# SVI: manual download note
print("\n  NOTE — CDC SVI (for control/heterogeneity variable):")
print("  The SVI CSV is no longer directly downloadable. Use the interactive form:")
print("  https://svi.cdc.gov/dataDownloads/data-download.html")
print("  Select: Year=2020, Geography=US, Level=County, Format=CSV")
print("  Save as: data/raw/SVI2020_US_county.csv")
print("  SVI_overall (RPL_THEMES) is the key variable — a percentile rank 0-1.")

# ─── 3. HRSA Health Professional Shortage Areas (HPSA) ───────────────────────
print("\n=== Downloading HRSA HPSA designations (Mental Health) ===")
HRSA_URL = "https://data.hrsa.gov/DataDownload/DD_Files/BCD_HPSA_FCT_DET_MH.csv"
try:
    r = requests.get(HRSA_URL, timeout=60, headers={"User-Agent":"Mozilla/5.0"})
    if r.status_code == 200:
        from io import StringIO
        hpsa_raw = pd.read_csv(StringIO(r.text), dtype=str)
        print(f"  HPSA raw columns: {list(hpsa_raw.columns[:10])}")
        # The HPSA file has county FIPS in various column names depending on vintage
        fips_col = None
        for c in hpsa_raw.columns:
            if "fips" in c.lower() or "county" in c.lower():
                fips_col = c
                break
        if fips_col:
            hpsa_raw[fips_col] = hpsa_raw[fips_col].str.zfill(5).str[:5]
            hpsa = hpsa_raw[[fips_col]].rename(columns={fips_col: "GEOID"})
            hpsa = hpsa[hpsa["GEOID"].isin(target_geoids)].drop_duplicates()
            hpsa["HPSA_mental_health"] = 1
            hpsa.to_csv(f"{OUTDIR}/hrsa_hpsa_covariates.csv", index=False)
            print(f"  Saved: hrsa_hpsa_covariates.csv  ({len(hpsa)} counties with MH HPSA designation)")
        else:
            print(f"  Could not identify FIPS column in: {list(hpsa_raw.columns[:15])}")
    else:
        print(f"  HRSA HTTP {r.status_code}")
except Exception as e:
    print(f"  HRSA download failed: {e}")
    hpsa = pd.DataFrame()

# ─── 4. FEMA fire disaster declarations ───────────────────────────────────────
# Working endpoint confirmed: FemaWebDisasterSummaries (v1)
print("\n=== Downloading FEMA fire disaster declarations ===")
FEMA_BASE = "https://www.fema.gov/api/open/v1/FemaWebDisasterSummaries"
fema_records = []
try:
    skip  = 0
    limit = 1000
    while True:
        url = f"{FEMA_BASE}?incidentType=Fire&limit={limit}&skip={skip}"
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            data = r.json()
            key = next((k for k in ["FemaWebDisasterSummaries","data","items","results"] if k in data), None)
            if key is None:
                print(f"  Unknown keys: {list(data.keys())}")
                break
            records = data[key]
            if not records:
                break
            fema_records.extend(records)
            if len(records) < limit:
                break
            skip += limit
        else:
            print(f"  FEMA API HTTP {r.status_code}")
            break

    if fema_records:
        fema_df = pd.DataFrame(fema_records)
        print(f"  FEMA records: {len(fema_df)}, columns: {list(fema_df.columns[:10])}")
        # Find county FIPS columns
        fips_col = None
        for c in fema_df.columns:
            if "fips" in c.lower() or "county" in c.lower():
                fips_col = c
                break
        year_col = None
        for c in fema_df.columns:
            if "year" in c.lower() or "date" in c.lower() and year_col is None:
                year_col = c
        if fips_col and year_col:
            fema_df["GEOID"] = fema_df[fips_col].astype(str).str.zfill(5)
            fema_df["decl_year"] = pd.to_datetime(fema_df[year_col], errors="coerce").dt.year
            fema_panel = fema_df[fema_df["GEOID"].isin(target_geoids) &
                                  fema_df["decl_year"].isin(YEARS)].copy()
            fema_panel = fema_panel.groupby(["GEOID","decl_year"]).size().reset_index(name="fema_fire_declarations")
            fema_panel = fema_panel.rename(columns={"decl_year":"year"})
            fema_panel.to_csv(f"{OUTDIR}/fema_declarations_covariates.csv", index=False)
            print(f"  Saved: fema_declarations_covariates.csv  ({len(fema_panel):,} county-years)")
        else:
            print(f"  Could not parse FEMA columns. Available: {list(fema_df.columns)}")
    else:
        print("  No FEMA records returned")
except Exception as e:
    print(f"  FEMA download failed: {e}")

# ─── 5. ACS via Census API (requires free key from api.census.gov/signup) ─────
print("\n=== ACS (Census API) ===")
CENSUS_KEY = "5e9b8c7b6f13e5d5f10b100ebf88eba8c778a442"  # Set your key here: https://api.census.gov/signup.html
if CENSUS_KEY:
    ACS_VARS = ["B19013_001E","B17001_002E","B17001_001E","B01003_001E",
                "B03002_003E","B03002_004E","B03002_012E","B03002_005E","B03002_001E"]
    ACS_YEARS = [y for y in YEARS if y <= 2022]
    chunks = []
    for state in sorted(panel["STATEFP"].dropna().unique()):
        for yr in ACS_YEARS:
            vars_str = ",".join(["NAME"] + ACS_VARS)
            url = (f"https://api.census.gov/data/{yr}/acs/acs5"
                   f"?get={vars_str}&for=county:*&in=state:{state}&key={CENSUS_KEY}")
            try:
                r = requests.get(url, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    df = pd.DataFrame(data[1:], columns=data[0])
                    df["GEOID"] = df["state"].str.zfill(2) + df["county"].str.zfill(3)
                    df["year"]  = yr
                    df = df[df["GEOID"].isin(target_geoids)]
                    if len(df) > 0:
                        chunks.append(df[["GEOID","year"] + [v for v in ACS_VARS if v in df.columns]])
            except Exception:
                pass
    if chunks:
        acs = pd.concat(chunks, ignore_index=True)
        for v in ACS_VARS:
            if v in acs.columns:
                acs[v] = pd.to_numeric(acs[v], errors="coerce").replace(-666666666, np.nan)
        acs["poverty_rate"]   = acs["B17001_002E"] / acs["B17001_001E"]
        acs["share_NH_black"] = acs["B03002_004E"] / acs["B03002_001E"]
        acs["share_hispanic"] = acs["B03002_012E"] / acs["B03002_001E"]
        acs["share_AIAN"]     = acs["B03002_005E"] / acs["B03002_001E"]
        acs = acs.rename(columns={"B19013_001E":"median_hh_income","B01003_001E":"population"})
        keep = ["GEOID","year","median_hh_income","poverty_rate","population",
                "share_NH_black","share_hispanic","share_AIAN"]
        acs[keep].to_csv(f"{OUTDIR}/acs_covariates.csv", index=False)
        print(f"  Saved: acs_covariates.csv  ({len(acs):,} rows)")
    else:
        print("  ACS download returned no data")
else:
    print("  CENSUS_KEY not set.")
    print("  1. Sign up at https://api.census.gov/signup.html (free, instant)")
    print("  2. Set CENSUS_KEY = 'your_key_here' in this script")
    print("  3. Re-run this script")

# ─── 6. Merge everything into panel_merged.csv ────────────────────────────────
print("\n=== Merging covariates into panel_merged.csv ===")
merged = panel.copy()

if len(laus) > 0:
    merged = merged.merge(laus, on=["GEOID","year"], how="left")
    print(f"  BLS LAUS: {merged['unemployment_rate'].notna().sum():,} obs merged")

if len(svi) > 0:
    merged = merged.merge(svi, on="GEOID", how="left")
    print(f"  CDC SVI: {merged['SVI_overall'].notna().sum():,} obs merged")

try:
    hpsa = pd.read_csv(f"{OUTDIR}/hrsa_hpsa_covariates.csv", dtype={"GEOID": str})
    merged = merged.merge(hpsa, on="GEOID", how="left")
    merged["HPSA_mental_health"] = merged["HPSA_mental_health"].fillna(0).astype(int)
    print(f"  HRSA HPSA: {merged['HPSA_mental_health'].sum():,} county-years with MH shortage designation")
except Exception:
    pass

try:
    fema_cov = pd.read_csv(f"{OUTDIR}/fema_declarations_covariates.csv", dtype={"GEOID": str})
    merged = merged.merge(fema_cov, on=["GEOID","year"], how="left")
    merged["fema_fire_declarations"] = merged["fema_fire_declarations"].fillna(0)
    print(f"  FEMA: {(merged['fema_fire_declarations']>0).sum():,} county-years with fire declarations")
except Exception:
    pass

try:
    acs_cov = pd.read_csv(f"{OUTDIR}/acs_covariates.csv", dtype={"GEOID": str})
    merged = merged.merge(acs_cov, on=["GEOID","year"], how="left")
    print(f"  ACS: {merged['median_hh_income'].notna().sum():,} obs merged")
except Exception:
    pass

try:
    places_cov = pd.read_csv(f"{OUTDIR}/cdc_places_outcomes.csv", dtype={"GEOID": str})
    places_cov["year"] = pd.to_numeric(places_cov["year"], errors="coerce").astype("Int64")
    merged = merged.merge(places_cov, on=["GEOID","year"], how="left")
    if "pct_depression" in merged.columns:
        print(f"  PLACES: {merged['pct_depression'].notna().sum():,} depression obs merged")
except Exception:
    pass

merged.to_csv(f"{OUTDIR}/panel_merged.csv", index=False)
print(f"\n  Final panel: {len(merged):,} rows × {len(merged.columns)} columns")
print(f"  Columns: {list(merged.columns)}")

# ─── 7. Summary statistics ────────────────────────────────────────────────────
print("\n=== Summary statistics (2011-2014 pre-treatment) ===")
pre = merged[merged["year"].between(2011, 2014)]
stat_vars = ["BP_NATIONAL_RANK","RUCC2013","BUILDINGS_FRACTION_DE","unemployment_rate"]
if "SVI_overall" in pre.columns:    stat_vars.append("SVI_overall")
if "HPSA_mental_health" in pre.columns: stat_vars.append("HPSA_mental_health")
if "median_hh_income" in pre.columns:  stat_vars.append("median_hh_income")

rows = []
for v in stat_vars:
    if v not in pre.columns: continue
    t = pre.loc[pre["treated"]==1, v]
    c = pre.loc[pre["treated"]==0, v]
    rows.append({
        "Variable":      v,
        "Treated mean":  round(t.mean(), 4),
        "Treated SD":    round(t.std(),  4),
        "Control mean":  round(c.mean(), 4),
        "Control SD":    round(c.std(),  4),
        "Diff (%)":      round(abs((t.mean()-c.mean())/t.mean()*100),1) if t.mean()!=0 else 0,
        "N_treated":     t.notna().sum(),
        "N_control":     c.notna().sum(),
    })
stats_df = pd.DataFrame(rows)
stats_df.to_csv(f"{OUTDIR}/summary_stats.csv", index=False)
print(stats_df.to_string(index=False))

print("""
=== REMAINING ACTIONS ===
1. Get Census API key (free):  https://api.census.gov/signup.html
   Then set CENSUS_KEY in download_covariates.py and re-run to add ACS variables.

2. CDC WONDER suicide/overdose mortality (county-level):
   Go to https://wonder.cdc.gov/cmf-icd10.html
   Select: group by county + year, ICD-10 codes X60-X84 (intentional self-harm)
   Export: Compressed Mortality File as tab-delimited .txt
   Save to: data/raw/cdc_wonder_suicide.txt
   Note: deaths <10 are suppressed — needs imputation strategy.

3. Medicaid T-MSIS (restricted data — START NOW):
   Submit application at https://resdac.org/cms-data/files/t-msis
   CMS processes in 6-12 months — the earlier this is submitted, the better.

4. EPA HMS wildfire smoke PM2.5:
   See https://www.epa.gov/hms for county-day smoke plume coverage.
   County-year aggregates are available from EPA's pre-processed files.
""")
