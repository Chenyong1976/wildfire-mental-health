"""
Download multi-year CDC PLACES depression and poor mental health days.

Four vintages cover: 2018, 2019, 2020, 2022, 2023
(2020 will be excluded to match panel; 2011-2017 not available from PLACES)
"""
import warnings; warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np
import requests
from io import StringIO

OUTDIR = r"C:\Users\chenyon\Research Paper 2026(1)"
panel  = pd.read_csv(f"{OUTDIR}/panel_skeleton.csv", dtype={"GEOID": str})
panel["GEOID"] = panel["GEOID"].str.zfill(5)
target = set(panel["GEOID"].unique())

VINTAGES = {
    "swc5-untb": "2023-2022",   # current:  years 2022, 2023
    "duw2-7jbt": "2020-2019",   # 2022 rel: years 2019, 2020
    "pqpp-u99h": "2019-2018",   # 2021 rel: years 2018, 2019
}

MH_MEASURES = {"DEPRESSION", "MHLTH"}

all_chunks = []

for did, label in VINTAGES.items():
    print(f"\nDownloading PLACES {label} ({did})...")
    try:
        r = requests.get(
            f"https://data.cdc.gov/api/views/{did}/rows.csv?accessType=DOWNLOAD",
            timeout=180
        )
        if r.status_code != 200:
            print(f"  HTTP {r.status_code} — skipping")
            continue

        df = pd.read_csv(StringIO(r.text), dtype={"LocationID": str, "Year": str})

        # Normalize column names (some vintages differ slightly)
        df.columns = [c.strip() for c in df.columns]
        mid_col  = next((c for c in df.columns if c in ("MeasureId","MeasureID","measureid")), None)
        type_col = next((c for c in df.columns if c in ("DataValueTypeID","DataValueTypeid")), None)
        val_col  = next((c for c in df.columns if c in ("Data_Value","DataValue")), None)
        loc_col  = next((c for c in df.columns if c in ("LocationID","locationid","FIPS")), None)
        yr_col   = next((c for c in df.columns if c in ("Year","year","YEAR")), None)

        if not all([mid_col, val_col, loc_col, yr_col]):
            print(f"  Missing required cols — found: {list(df.columns[:10])}")
            continue

        # Filter to MH measures + age-adjusted prevalence
        mask = df[mid_col].isin(MH_MEASURES)
        if type_col:
            mask &= df[type_col].isin({"AgeAdjPrv", "Age-adjusted prevalence"})
        sub = df[mask].copy()

        sub["GEOID"] = sub[loc_col].astype(str).str.zfill(5)
        sub["year"]  = pd.to_numeric(sub[yr_col], errors="coerce").astype("Int64")
        sub["value"] = pd.to_numeric(sub[val_col], errors="coerce")
        sub["measure"] = sub[mid_col]

        sub = sub[sub["GEOID"].isin(target)][["GEOID","year","measure","value"]]
        print(f"  Rows after filter: {len(sub)}, years: {sorted(sub['year'].dropna().unique().tolist())}")
        all_chunks.append(sub)

    except Exception as e:
        print(f"  ERROR: {e}")

if not all_chunks:
    print("\nNo PLACES data downloaded.")
else:
    combined = pd.concat(all_chunks, ignore_index=True)
    # Deduplicate (2019 appears in two vintages — keep mean)
    combined = combined.groupby(["GEOID","year","measure"])["value"].mean().reset_index()

    # Pivot to wide
    pivot = combined.pivot_table(
        index=["GEOID","year"], columns="measure", values="value", aggfunc="mean"
    ).reset_index()
    pivot.columns.name = None
    rename = {"DEPRESSION": "pct_depression", "MHLTH": "pct_poor_mh_days"}
    pivot = pivot.rename(columns=rename)

    # Exclude 2020 to match panel design
    pivot = pivot[pivot["year"] != 2020]

    pivot.to_csv(f"{OUTDIR}/places_mental_health.csv", index=False)
    print(f"\nSaved places_mental_health.csv: {len(pivot):,} county-years")
    print(f"Years covered: {sorted(pivot['year'].dropna().unique().tolist())}")

    # Coverage summary
    avail = pivot.merge(panel[["GEOID","treated"]].drop_duplicates(), on="GEOID", how="left")
    for col in ["pct_depression", "pct_poor_mh_days"]:
        if col not in avail.columns:
            continue
        t_n = avail.loc[avail["treated"]==1, col].notna().sum()
        c_n = avail.loc[avail["treated"]==0, col].notna().sum()
        t_m = avail.loc[avail["treated"]==1, col].mean()
        c_m = avail.loc[avail["treated"]==0, col].mean()
        print(f"\n{col}:")
        print(f"  Treated: {t_n:,} obs, mean={t_m:.2f}%")
        print(f"  Control: {c_n:,} obs, mean={c_m:.2f}%")
        print(f"  Diff:    {t_m-c_m:+.3f} pp ({abs((t_m-c_m)/t_m*100):.1f}%)")

    # Merge into panel_merged.csv
    print("\nMerging into panel_merged.csv...")
    merged = pd.read_csv(f"{OUTDIR}/panel_merged.csv", dtype={"GEOID": str})
    merged["GEOID"] = merged["GEOID"].str.zfill(5)
    # Drop old PLACES columns if present
    for col in ["pct_depression","pct_poor_mh_days","pct_poor_mental_health_days"]:
        if col in merged.columns:
            merged.drop(columns=[col], inplace=True)
    pivot["year"] = pivot["year"].astype(int)
    merged = merged.merge(pivot, on=["GEOID","year"], how="left")
    merged.to_csv(f"{OUTDIR}/panel_merged.csv", index=False)
    dep_obs = merged["pct_depression"].notna().sum() if "pct_depression" in merged.columns else 0
    print(f"panel_merged.csv: {len(merged):,} rows x {len(merged.columns)} cols")
    print(f"Depression obs in panel: {dep_obs:,} ({dep_obs/len(merged):.1%} coverage)")
