"""
Wildfire distribution 2015-2019 across Western US states.
Produces:
  figures/west_fire_map.png          — county-level choropleth by cohort year
  figures/west_fire_by_state_year.png — stacked bar: treated counties per state/year
  figures/west_fire_acres_year.png   — total acres burned per year
  figures/west_fire_size_dist.png    — fire size distribution by state
"""
import warnings; warnings.filterwarnings('ignore')
import zipfile, os
import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap
import matplotlib.ticker as mticker

BASE   = r"C:\Users\chenyon\Research Paper 2026(1)\data\raw"
OUTDIR = r"C:\Users\chenyon\Research Paper 2026(1)"
FIGDIR = r"C:\Users\chenyon\Research Paper 2026(1)\figures"
os.makedirs(FIGDIR, exist_ok=True)

WESTERN_FIPS = ['04','06','08','16','30','32','35','41','49','53','56']
STATE_NAMES  = {
    '04':'Arizona','06':'California','08':'Colorado','16':'Idaho',
    '30':'Montana','32':'Nevada','35':'New Mexico','41':'Oregon',
    '49':'Utah','53':'Washington','56':'Wyoming'
}
COHORT_COLORS = {
    2015:'#d73027', 2016:'#f46d43', 2017:'#fdae61',
    2018:'#4575b4', 2019:'#313695'
}

# ── Load counties shapefile ───────────────────────────────────────────────────
counties_dir = f"{BASE}/counties"
if not os.path.isdir(counties_dir):
    with zipfile.ZipFile(f"{BASE}/tl_2020_us_county.zip") as z:
        z.extractall(counties_dir)
counties = gpd.read_file(counties_dir).to_crs("EPSG:5070")
counties["GEOID"]   = counties["GEOID"].astype(str).str.zfill(5)
counties["STATEFP"] = counties["STATEFP"].astype(str).str.zfill(2)
west = counties[counties["STATEFP"].isin(WESTERN_FIPS)].copy()
states_west = west.dissolve(by="STATEFP").reset_index()

# ── Load matched fire data ────────────────────────────────────────────────────
mp = pd.read_csv(f"{OUTDIR}/matched_county_pairs.csv", dtype={"treated_GEOID": str})
mp = mp[mp["match_rank"] == 1].copy()
mp["treated_GEOID"]  = mp["treated_GEOID"].str.zfill(5)
mp["treated_STATE"]  = mp["treated_STATE"].astype(str).str.zfill(2)
mp["state_name"]     = mp["treated_STATE"].map(STATE_NAMES)
mp["total_acres"]    = pd.to_numeric(mp["treated_total_acres"], errors="coerce")
mp["first_fire_yr"]  = pd.to_numeric(mp["treated_first_fire_yr"], errors="coerce").astype("Int64")

# Western treated counties only
mp_west = mp[mp["treated_STATE"].isin(WESTERN_FIPS)].copy()
print(f"Western treated counties: {len(mp_west)}")
print(mp_west["first_fire_yr"].value_counts().sort_index())

# ── Merge geodata ─────────────────────────────────────────────────────────────
geo = west.merge(
    mp_west[["treated_GEOID","first_fire_yr","total_acres","treated_WHP_quintile"]],
    left_on="GEOID", right_on="treated_GEOID", how="left"
)
geo["status"] = geo["first_fire_yr"].apply(
    lambda x: str(int(x)) if pd.notna(x) else "Control"
)

# ────────────────────────────────────────────────────────────────────────────
# FIGURE 1 — Choropleth map: county fire status by first-fire year
# ────────────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(1, 1, figsize=(14, 10))

# Base: all western counties light gray
west.plot(ax=ax, color="#e8e8e8", edgecolor="#bbbbbb", linewidth=0.3)

# Treated counties by cohort year
for yr, color in COHORT_COLORS.items():
    sub = geo[geo["first_fire_yr"] == yr]
    if len(sub) > 0:
        sub.plot(ax=ax, color=color, edgecolor="#555555", linewidth=0.4, alpha=0.9)

# State boundaries
states_west.boundary.plot(ax=ax, color="black", linewidth=1.2)

# State labels
for _, row in states_west.iterrows():
    centroid = row.geometry.centroid
    name = STATE_NAMES.get(row["STATEFP"], "")
    ax.annotate(name, xy=(centroid.x, centroid.y),
                ha='center', va='center', fontsize=7.5,
                color='#222222', fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.2', fc='white', alpha=0.5, ec='none'))

# Legend
legend_patches = [
    mpatches.Patch(color="#e8e8e8", label="Control (never-treated)", ec="#bbbbbb")
] + [
    mpatches.Patch(color=COHORT_COLORS[yr], label=f"First fire: {yr}")
    for yr in sorted(COHORT_COLORS)
]
ax.legend(handles=legend_patches, loc="lower left", fontsize=10,
          framealpha=0.9, title="Fire cohort", title_fontsize=10)

ax.set_title("Western US Wildfire-Affected Counties, 2015–2019\n"
             "MTBS wildfires ≥1,000 acres; colored by first fire year",
             fontsize=14, fontweight='bold', pad=12)
ax.axis("off")
plt.tight_layout()
plt.savefig(f"{FIGDIR}/west_fire_map.png", dpi=180, bbox_inches="tight")
plt.close()
print("Saved: west_fire_map.png")

# ────────────────────────────────────────────────────────────────────────────
# FIGURE 2 — Stacked bar: treated counties per state × year
# ────────────────────────────────────────────────────────────────────────────
state_yr = (mp_west.groupby(["state_name","first_fire_yr"])
            .size().reset_index(name="n_counties"))
state_yr["first_fire_yr"] = state_yr["first_fire_yr"].astype(int)

# State order by total treated counties
state_order = (state_yr.groupby("state_name")["n_counties"]
               .sum().sort_values(ascending=False).index.tolist())

pivot = (state_yr.pivot(index="state_name", columns="first_fire_yr", values="n_counties")
         .reindex(state_order).fillna(0))

fig, ax = plt.subplots(figsize=(13, 6))
bottom = np.zeros(len(pivot))
bars = []
for yr in sorted(COHORT_COLORS):
    if yr in pivot.columns:
        vals = pivot[yr].values
        b = ax.bar(pivot.index, vals, bottom=bottom,
                   color=COHORT_COLORS[yr], label=str(yr),
                   edgecolor="white", linewidth=0.5)
        bars.append(b)
        bottom += vals

# Total labels on top
for i, total in enumerate(bottom):
    if total > 0:
        ax.text(i, total + 0.3, str(int(total)),
                ha='center', va='bottom', fontsize=9, fontweight='bold')

ax.set_xlabel("State", fontsize=12)
ax.set_ylabel("Number of treated counties", fontsize=12)
ax.set_title("Wildfire-Affected Counties by State and Year (Western US, 2015–2019)\n"
             "MTBS wildfires ≥1,000 acres", fontsize=13, fontweight='bold')
ax.legend(title="First fire year", fontsize=10, title_fontsize=10)
ax.set_ylim(0, bottom.max() * 1.15)
ax.grid(axis="y", alpha=0.3)
ax.spines[['top','right']].set_visible(False)
plt.xticks(rotation=30, ha='right', fontsize=10)
plt.tight_layout()
plt.savefig(f"{FIGDIR}/west_fire_by_state_year.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: west_fire_by_state_year.png")

# ────────────────────────────────────────────────────────────────────────────
# FIGURE 3 — Total acres burned per year (Western US)
# ────────────────────────────────────────────────────────────────────────────
acres_yr = (mp_west.groupby("first_fire_yr")["total_acres"]
            .agg(["sum","mean","count"]).reset_index())
acres_yr.columns = ["year","total_acres","mean_acres","n_counties"]
acres_yr["year"] = acres_yr["year"].astype(int)
acres_yr["total_M"] = acres_yr["total_acres"] / 1e6

fig, ax1 = plt.subplots(figsize=(9, 5))
colors_bar = [COHORT_COLORS[y] for y in acres_yr["year"]]
bars = ax1.bar(acres_yr["year"], acres_yr["total_M"],
               color=colors_bar, edgecolor="white", linewidth=0.8, width=0.6)
for bar, val in zip(bars, acres_yr["total_M"]):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
             f"{val:.2f}M", ha='center', va='bottom', fontsize=10, fontweight='bold')

ax2 = ax1.twinx()
ax2.plot(acres_yr["year"], acres_yr["n_counties"], color="black",
         marker="o", linewidth=2, markersize=7, label="# counties", zorder=5)
for x, y in zip(acres_yr["year"], acres_yr["n_counties"]):
    ax2.annotate(str(int(y)), (x, y), textcoords="offset points",
                 xytext=(0, 8), ha='center', fontsize=9)

ax1.set_xlabel("Year", fontsize=12)
ax1.set_ylabel("Total acres burned (millions)", fontsize=12, color="#c0392b")
ax2.set_ylabel("Number of treated counties", fontsize=12)
ax1.tick_params(axis='y', colors="#c0392b")
ax1.set_title("Annual Wildfire Extent and Frequency — Western US, 2015–2019\n"
              "Bars = total acres (M); Line = number of counties first affected",
              fontsize=12, fontweight='bold')
ax1.set_xticks(acres_yr["year"])
ax1.grid(axis="y", alpha=0.25)
ax1.spines[['top']].set_visible(False)
ax2.spines[['top']].set_visible(False)
plt.tight_layout()
plt.savefig(f"{FIGDIR}/west_fire_acres_year.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: west_fire_acres_year.png")

# ────────────────────────────────────────────────────────────────────────────
# FIGURE 4 — Fire size distribution by state (box + strip)
# ────────────────────────────────────────────────────────────────────────────
mp_west2 = mp_west.dropna(subset=["total_acres","state_name"]).copy()
mp_west2["log_acres"] = np.log10(mp_west2["total_acres"].clip(lower=1))

state_order2 = (mp_west2.groupby("state_name")["total_acres"]
                .median().sort_values(ascending=False).index.tolist())

fig, ax = plt.subplots(figsize=(13, 6))
data_by_state = [mp_west2[mp_west2["state_name"]==s]["log_acres"].values
                 for s in state_order2]
bp = ax.boxplot(data_by_state, positions=range(len(state_order2)),
                widths=0.5, patch_artist=True,
                boxprops=dict(facecolor="#4575b4", alpha=0.6),
                medianprops=dict(color="black", linewidth=2),
                whiskerprops=dict(linewidth=1.2),
                flierprops=dict(marker='o', markersize=3, alpha=0.4, color="#d73027"))

# Jittered strip overlay
for i, s in enumerate(state_order2):
    vals = mp_west2[mp_west2["state_name"]==s]["log_acres"].values
    jitter = np.random.uniform(-0.18, 0.18, len(vals))
    ax.scatter(i + jitter, vals, alpha=0.35, s=18, color="#d73027", zorder=3)

# Y-axis: convert log10 back to readable labels
yticks = [3, 3.699, 4, 4.699, 5, 5.699, 6]
ylabels = ["1k", "5k", "10k", "50k", "100k", "500k", "1M"]
ax.set_yticks(yticks)
ax.set_yticklabels(ylabels, fontsize=10)
ax.set_xticks(range(len(state_order2)))
ax.set_xticklabels(state_order2, rotation=30, ha='right', fontsize=10)
ax.set_ylabel("Total acres burned (log scale)", fontsize=12)
ax.set_title("Distribution of Wildfire Size by State — Western US, 2015–2019\n"
             "Each point = one treated county; box = IQR; line = median",
             fontsize=12, fontweight='bold')
ax.grid(axis="y", alpha=0.3)
ax.spines[['top','right']].set_visible(False)
plt.tight_layout()
plt.savefig(f"{FIGDIR}/west_fire_size_dist.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved: west_fire_size_dist.png")

# ────────────────────────────────────────────────────────────────────────────
# SUMMARY STATISTICS
# ────────────────────────────────────────────────────────────────────────────
print("\n=== WESTERN US FIRE SUMMARY (2015-2019) ===")
print(f"Total treated counties: {len(mp_west)}")

print("\n--- By year ---")
print(mp_west["first_fire_yr"].value_counts().sort_index().to_string())

print("\n--- By state (total counties | total acres | median acres) ---")
state_sum = (mp_west.groupby("state_name").agg(
    n_counties=("treated_GEOID","count"),
    total_acres=("total_acres","sum"),
    median_acres=("total_acres","median"),
    mean_acres=("total_acres","mean")
).sort_values("n_counties", ascending=False))
for s, r in state_sum.iterrows():
    print(f"  {s:<15} {int(r.n_counties):>3} counties | "
          f"total {r.total_acres/1e6:>5.2f}M ac | "
          f"median {r.median_acres:>8,.0f} ac")

print("\n--- Acres distribution (all Western treated) ---")
print(f"  Mean:   {mp_west['total_acres'].mean():>10,.0f} ac")
print(f"  Median: {mp_west['total_acres'].median():>10,.0f} ac")
print(f"  p75:    {mp_west['total_acres'].quantile(.75):>10,.0f} ac")
print(f"  p90:    {mp_west['total_acres'].quantile(.90):>10,.0f} ac")
print(f"  Max:    {mp_west['total_acres'].max():>10,.0f} ac")

print("\n--- Size tiers ---")
tiers = [(0,5000,"<5,000 ac"),(5000,25000,"5k-25k ac"),
         (25000,100000,"25k-100k ac"),(100000,1e9,">=100k ac")]
for lo, hi, lab in tiers:
    n = ((mp_west["total_acres"]>=lo)&(mp_west["total_acres"]<hi)).sum()
    print(f"  {lab:<15}: {n:>3} counties ({n/len(mp_west):.1%})")

print("\n--- WHP quintile (Western treated) ---")
print(mp_west["treated_WHP_quintile"].value_counts().sort_index().to_string())
