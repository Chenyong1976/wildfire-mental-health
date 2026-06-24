"""
Download outcome variables — Sources 1 and 2:

  Source 1: CDC WONDER Compressed Mortality File (D76)
            - Suicide:  ICD-10 X60-X84 (intentional self-harm)
            - Overdose: ICD-10 X40-X49, X60-X65, Y10-Y15
            - County × year, 2011-2019 and 2021-2023

  Source 2: CDC PLACES
            - Depression prevalence (age-adjusted %)
            - Poor mental health days (age-adjusted %)
            - County × year, most recent available
"""

import warnings; warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np
import requests
import time
import os
from io import StringIO

OUTDIR = r"C:\Users\chenyon\Research Paper 2026(1)"
YEARS  = list(range(2011, 2020)) + list(range(2021, 2024))

panel = pd.read_csv(f"{OUTDIR}/panel_skeleton.csv", dtype={"GEOID": str})
panel["GEOID"] = panel["GEOID"].str.zfill(5)
target_geoids  = set(panel["GEOID"].unique())
target_states  = set(panel["STATEFP"].dropna().astype(str).str.zfill(2).unique())

# ─── Utility: WONDER API query ────────────────────────────────────────────────
WONDER_URL = "https://wonder.cdc.gov/controller/datarequest/D76"

def wonder_query(icd_codes_str, label, year_start, year_end):
    """
    Query CDC WONDER D76 (compressed mortality, ICD-10) for county-year counts.
    Returns a DataFrame with columns: GEOID, year, state_fips, deaths, population, crude_rate
    Suppressed cells (< 10 deaths) are returned as NaN.
    """
    # Build year list param (D76.V1 = year)
    years = [str(y) for y in range(year_start, year_end + 1) if y != 2020]
    year_param = " ".join(years)

    params = {
        "accept_datause_restrictions": "true",
        # Grouping: B_1 = county, B_2 = year
        "B_1": "D76.V9-county",
        "B_2": "D76.V1",
        "B_3": "*None*",
        "B_4": "*None*",
        # Year selection
        "F_D76.V1": year_param,
        "V_D76.V1": year_param,
        # Cause of death (ICD-10 underlying)
        "F_D76.V2": icd_codes_str,
        "I_D76.V2": icd_codes_str,
        "O_ucd_default": "D76.V2",
        # All ages, all sexes, all races
        "V_D76.V3": "*All*",
        "V_D76.V4": "*All*",
        "V_D76.V6": "*All*",
        "V_D76.V7": "*All*",
        "V_D76.V8": "*All*",
        # Measures
        "M_1": "D76.M1",   # Deaths
        "M_2": "D76.M2",   # Population
        "M_3": "D76.M3",   # Crude rate
        # Output format
        "O_show_totals": "false",
        "O_show_zeros":  "true",
        "O_show_suppressed": "true",
        "action-Send": "Send",
    }

    try:
        r = requests.post(WONDER_URL, data=params, timeout=120,
                          headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        if r.status_code != 200:
            print(f"  {label}: HTTP {r.status_code}")
            return pd.DataFrame()

        # WONDER returns tab-delimited text; skip header notes
        lines = r.text.split("\n")
        # Find data start (header row contains "County" or "Notes")
        data_start = 0
        for i, line in enumerate(lines):
            if line.startswith('"Notes"') or line.startswith("Notes"):
                # Notes section at end — trim here
                lines = lines[:i]
                break
            if "County" in line and "Deaths" in line:
                data_start = i
                break

        if data_start == 0:
            # Try to find first data line
            for i, line in enumerate(lines):
                parts = line.split("\t")
                if len(parts) >= 4 and parts[0].strip('"').isdigit():
                    data_start = i - 1
                    break

        data_text = "\n".join(lines[data_start:])
        df = pd.read_csv(StringIO(data_text), sep="\t", dtype=str)
        df.columns = [c.strip().strip('"') for c in df.columns]

        print(f"  {label}: {len(df)} rows, columns: {list(df.columns[:8])}")
        return df

    except Exception as e:
        print(f"  {label}: ERROR — {e}")
        return pd.DataFrame()


def parse_wonder_df(df, geoid_col, year_col, deaths_col, pop_col, rate_col):
    """Standardize column names and parse suppressed cells."""
    rename = {}
    for src, dst in [(geoid_col,"raw_fips"),(year_col,"year"),(deaths_col,"deaths"),
                     (pop_col,"population"),(rate_col,"crude_rate")]:
        if src in df.columns:
            rename[src] = dst
    df = df.rename(columns=rename)

    # FIPS: WONDER county codes are "SS999" format — state FIPS + county FIPS
    if "raw_fips" in df.columns:
        df["GEOID"] = df["raw_fips"].astype(str).str.strip().str.zfill(5)
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"].astype(str).str.strip(), errors="coerce")
    if "deaths" in df.columns:
        df["deaths"] = df["deaths"].astype(str).str.strip().replace(
            {"Suppressed": np.nan, "Missing": np.nan, "Not Applicable": np.nan}
        )
        df["deaths"] = pd.to_numeric(df["deaths"], errors="coerce")
    if "population" in df.columns:
        df["population"] = pd.to_numeric(
            df["population"].astype(str).str.replace(",","").str.strip(), errors="coerce"
        )
    if "crude_rate" in df.columns:
        df["crude_rate"] = df["crude_rate"].astype(str).str.strip().replace(
            {"Suppressed": np.nan, "Unreliable": np.nan, "Not Applicable": np.nan}
        )
        df["crude_rate"] = pd.to_numeric(df["crude_rate"], errors="coerce")
    return df


# ─── Source 1a: CDC WONDER — Suicide (X60–X84) ───────────────────────────────
print("=== Source 1a: CDC WONDER — Suicide (ICD-10 X60-X84) ===")
suicide_codes = " ".join([f"X{i}" for i in range(60, 85)])
df_suicide = wonder_query(suicide_codes, "Suicide", 2011, 2023)

if len(df_suicide) > 0:
    print(f"  Raw columns: {list(df_suicide.columns)}")
    # Identify columns — WONDER returns: County Code, County, Year Code, Year, Deaths, Population, Crude Rate
    fips_c  = next((c for c in df_suicide.columns if "County Code" in c or "County" in c and "Code" in c), None)
    year_c  = next((c for c in df_suicide.columns if "Year Code" in c or c == "Year Code"), None)
    if year_c is None:
        year_c = next((c for c in df_suicide.columns if "Year" in c), None)
    death_c = next((c for c in df_suicide.columns if "Deaths" in c), None)
    pop_c   = next((c for c in df_suicide.columns if "Population" in c), None)
    rate_c  = next((c for c in df_suicide.columns if "Crude" in c or "Rate" in c), None)

    print(f"  Mapped: FIPS={fips_c}, Year={year_c}, Deaths={death_c}, Pop={pop_c}, Rate={rate_c}")

    if all(c is not None for c in [fips_c, year_c, death_c]):
        suicide_df = parse_wonder_df(df_suicide, fips_c, year_c, death_c, pop_c or "", rate_c or "")
        suicide_df = suicide_df[
            suicide_df["GEOID"].isin(target_geoids) &
            suicide_df["year"].isin(YEARS)
        ][["GEOID","year","deaths","population","crude_rate"]].rename(columns={
            "deaths":     "suicide_deaths",
            "population": "suicide_pop",
            "crude_rate": "suicide_crude_rate"
        })
        suicide_df.to_csv(f"{OUTDIR}/wonder_suicide.csv", index=False)
        n_obs  = len(suicide_df)
        n_supp = suicide_df["suicide_deaths"].isna().sum()
        n_zero = (suicide_df["suicide_deaths"] == 0).sum()
        print(f"  Saved wonder_suicide.csv: {n_obs:,} county-years")
        print(f"  Suppressed (<10 deaths): {n_supp:,} ({n_supp/n_obs:.1%})")
        print(f"  Zero deaths:             {n_zero:,} ({n_zero/n_obs:.1%})")
        print(f"  Mean suicide rate (per 100k): {suicide_df['suicide_crude_rate'].mean():.2f}")
    else:
        print("  Could not map required columns — see raw columns above")
        df_suicide.to_csv(f"{OUTDIR}/wonder_suicide_raw.csv", index=False)
        print("  Saved raw to wonder_suicide_raw.csv for inspection")
else:
    print("  No data returned — WONDER may require browser login for first use")
    print("  Manual fallback: https://wonder.cdc.gov/cmf-icd10.html")
    print("  Select: Group by County + Year, ICD-10 X60-X84, years 2011-2019 and 2021-2023")
    print("  Export as tab-delimited .txt -> save as data/raw/wonder_suicide.txt")


# ─── Source 1b: CDC WONDER — Drug Overdose (X40-X49, X60-X65, Y10-Y15) ──────
print("\n=== Source 1b: CDC WONDER — Drug Overdose ===")
overdose_codes = " ".join(
    [f"X{i}" for i in range(40, 50)] +
    [f"X{i}" for i in range(60, 66)] +
    [f"Y{i}" for i in range(10, 16)]
)
df_overdose = wonder_query(overdose_codes, "Overdose", 2011, 2023)

if len(df_overdose) > 0:
    fips_c  = next((c for c in df_overdose.columns if "County Code" in c), None)
    year_c  = next((c for c in df_overdose.columns if "Year Code" in c), None)
    if year_c is None:
        year_c = next((c for c in df_overdose.columns if "Year" in c), None)
    death_c = next((c for c in df_overdose.columns if "Deaths" in c), None)
    pop_c   = next((c for c in df_overdose.columns if "Population" in c), None)
    rate_c  = next((c for c in df_overdose.columns if "Crude" in c or "Rate" in c), None)

    if all(c is not None for c in [fips_c, year_c, death_c]):
        overdose_df = parse_wonder_df(df_overdose, fips_c, year_c, death_c, pop_c or "", rate_c or "")
        overdose_df = overdose_df[
            overdose_df["GEOID"].isin(target_geoids) &
            overdose_df["year"].isin(YEARS)
        ][["GEOID","year","deaths","population","crude_rate"]].rename(columns={
            "deaths":     "overdose_deaths",
            "population": "overdose_pop",
            "crude_rate": "overdose_crude_rate"
        })
        overdose_df.to_csv(f"{OUTDIR}/wonder_overdose.csv", index=False)
        n_supp = overdose_df["overdose_deaths"].isna().sum()
        print(f"  Saved wonder_overdose.csv: {len(overdose_df):,} county-years")
        print(f"  Suppressed: {n_supp:,} ({n_supp/len(overdose_df):.1%})")
    else:
        df_overdose.to_csv(f"{OUTDIR}/wonder_overdose_raw.csv", index=False)
        print("  Saved raw to wonder_overdose_raw.csv")
else:
    print("  No data returned")
    print("  Manual fallback: use same WONDER interface, codes X40-X49, X60-X65, Y10-Y15")


# ─── Source 2: CDC PLACES ─────────────────────────────────────────────────────
print("\n=== Source 2: CDC PLACES (depression + poor mental health days) ===")
PLACES_URL = "https://data.cdc.gov/api/views/swc5-untb/rows.csv?accessType=DOWNLOAD"
try:
    r = requests.get(PLACES_URL, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code == 200:
        places_raw = pd.read_csv(StringIO(r.text), dtype={"LocationID": str})

        # Age-adjusted prevalence for mental health measures
        mh_ids = {"DEPRESSION", "MHLTH"}
        places_mh = places_raw[
            places_raw["MeasureId"].isin(mh_ids) &
            (places_raw["DataValueTypeID"] == "AgeAdjPrv")
        ].copy()
        places_mh["GEOID"] = places_mh["LocationID"].str.zfill(5)
        places_mh = places_mh[places_mh["GEOID"].isin(target_geoids)]
        places_mh["Data_Value"] = pd.to_numeric(places_mh["Data_Value"], errors="coerce")

        places_pivot = (
            places_mh.pivot_table(
                index=["GEOID", "Year"],
                columns="MeasureId",
                values="Data_Value",
                aggfunc="mean"
            )
            .reset_index()
        )
        places_pivot.columns.name = None
        places_pivot = places_pivot.rename(columns={
            "Year":       "year",
            "DEPRESSION": "pct_depression",
            "MHLTH":      "pct_poor_mh_days"
        })
        places_pivot["year"] = pd.to_numeric(places_pivot["year"], errors="coerce").astype(int)
        places_pivot = places_pivot[places_pivot["year"].isin(YEARS)]
        places_pivot.to_csv(f"{OUTDIR}/places_mental_health.csv", index=False)

        years_avail = sorted(places_pivot["year"].unique())
        print(f"  Saved places_mental_health.csv: {len(places_pivot):,} county-years")
        print(f"  Years available: {years_avail}")
        if "pct_depression" in places_pivot.columns:
            t_m = places_pivot.merge(panel[["GEOID","treated"]].drop_duplicates(),on="GEOID",how="left")
            print(f"  Depression (treated counties): {t_m.loc[t_m['treated']==1,'pct_depression'].mean():.2f}%")
            print(f"  Depression (control counties): {t_m.loc[t_m['treated']==0,'pct_depression'].mean():.2f}%")
    else:
        print(f"  PLACES HTTP {r.status_code}")
except Exception as e:
    print(f"  PLACES error: {e}")


# ─── Merge outcomes into panel ────────────────────────────────────────────────
print("\n=== Merging outcomes into panel_merged.csv ===")
merged = pd.read_csv(f"{OUTDIR}/panel_merged.csv", dtype={"GEOID": str})
merged["GEOID"] = merged["GEOID"].str.zfill(5)
before_cols = len(merged.columns)

for fname, key_col, label in [
    ("wonder_suicide.csv",  "suicide_deaths",   "CDC WONDER suicide"),
    ("wonder_overdose.csv", "overdose_deaths",  "CDC WONDER overdose"),
    ("places_mental_health.csv", "pct_depression", "CDC PLACES depression"),
]:
    fpath = f"{OUTDIR}/{fname}"
    if os.path.exists(fpath):
        df = pd.read_csv(fpath, dtype={"GEOID": str})
        df["GEOID"] = df["GEOID"].str.zfill(5)
        if "year" in df.columns:
            df["year"] = pd.to_numeric(df["year"], errors="coerce").astype(int)
        merged = merged.merge(df, on=["GEOID","year"], how="left")
        if key_col in merged.columns:
            print(f"  {label}: {merged[key_col].notna().sum():,} non-null obs")

merged.to_csv(f"{OUTDIR}/panel_merged.csv", index=False)
print(f"\n  panel_merged.csv: {len(merged):,} rows x {len(merged.columns)} cols (+{len(merged.columns)-before_cols} new)")
print(f"  New columns: {[c for c in merged.columns if c not in ['GEOID','year','NAME','STATEFP','WHP_quintile','first_fire_yr','BP_NATIONAL_RANK','RUCC2013','BUILDINGS_FRACTION_DE','treated','match_set','event_time','cohort_g','post','surprise_fire','unemployment_rate','HPSA_mental_health']]}")


# ─── Summary: outcome coverage ────────────────────────────────────────────────
print("\n=== Outcome coverage by treatment status ===")
outcome_cols = [c for c in merged.columns if any(x in c for x in
    ["suicide","overdose","depression","mh_days","pct_poor"])]
if outcome_cols:
    pre = merged[merged["year"].between(2011, 2014)]
    fmt = "{:<35} {:>10} {:>10} {:>12}"
    print(fmt.format("Outcome", "Treated obs", "Control obs", "Overall mean"))
    print("-"*70)
    for col in outcome_cols:
        if col not in merged.columns: continue
        t_n  = merged.loc[merged["treated"]==1, col].notna().sum()
        c_n  = merged.loc[merged["treated"]==0, col].notna().sum()
        mean = merged[col].mean()
        print(fmt.format(col, str(t_n), str(c_n), f"{mean:.3f}" if pd.notna(mean) else "—"))
