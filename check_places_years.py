import warnings; warnings.filterwarnings('ignore')
import requests, pandas as pd
from io import StringIO

OUTDIR = r"C:\Users\chenyon\Research Paper 2026(1)"
panel  = pd.read_csv(f"{OUTDIR}/panel_skeleton.csv", dtype={"GEOID": str})
panel["GEOID"] = panel["GEOID"].str.zfill(5)
target = set(panel["GEOID"].unique())
YEARS  = list(range(2011, 2020)) + list(range(2021, 2024))

# Try multi-year PLACES datasets
ids = {
    "swc5-untb": "current (2023)",
    "qnzd-25i4": "multi-year trend",
    "duw2-7jbt": "2022 release",
    "pqpp-u99h": "2021 release",
}

for did, label in ids.items():
    try:
        r = requests.get(
            f"https://data.cdc.gov/api/views/{did}/rows.csv?accessType=DOWNLOAD",
            timeout=60
        )
        if r.status_code == 200:
            df = pd.read_csv(StringIO(r.text), dtype=str, nrows=5000)
            years = []
            for c in ["Year", "year", "YEAR", "YearStart", "YearEnd"]:
                if c in df.columns:
                    years = df[c].dropna().unique().tolist()[:10]
                    break
            mids = []
            for c in ["MeasureId", "measureid", "MEASUREID", "Category"]:
                if c in df.columns:
                    mids = df[c].dropna().unique().tolist()[:15]
                    break
            print(f"\n{label} ({did})")
            print(f"  Cols: {list(df.columns[:8])}")
            print(f"  Years: {years}")
            print(f"  Measure IDs: {mids}")
    except Exception as e:
        print(f"\n{label}: ERROR {e}")

# NCHS FTP
print("\n=== NCHS FTP mortality files ===")
try:
    r = requests.get(
        "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/DVS/mortality/",
        timeout=15
    )
    print(f"NCHS FTP: HTTP {r.status_code}")
    if r.status_code == 200:
        import re
        files = re.findall(r"href=\"([^\"]+)\"", r.text)
        data_files = [f for f in files if any(f.endswith(x) for x in [".zip", ".ZIP", ".gz"])]
        print(f"Data files found: {data_files[:15]}")
except Exception as e:
    print(f"NCHS FTP: {e}")
