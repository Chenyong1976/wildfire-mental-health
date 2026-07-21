"""
Generate fig_common_support.png — common support covariate overlap figure.
Uses only csv module to avoid numpy/pandas version conflicts.
"""
import csv
import os
import sys

# Use Agg backend (no display needed)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

BASE = r"C:\Users\chenyon\Research Paper 2026(1)"
CSV_PATH = os.path.join(BASE, "matched_2015_T1_moderate_1k.csv")
OUT_PNG  = os.path.join(BASE, "fig_common_support.png")

# ── Read data ─────────────────────────────────────────────────────────────────
treated_whp      = []
control_whp      = []
treated_rucc     = []
control_rucc     = []
treated_suicide  = []
control_suicide  = []
whp_quintile     = []
mah_dist         = []

with open(CSV_PATH, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # WHP rank
        tw = float(row['treated_WHP_rank'])
        cw = float(row['control_WHP_rank'])
        treated_whp.append(tw)
        control_whp.append(cw)

        # RUCC
        tr = float(row['treated_RUCC'])
        cr = float(row['control_RUCC'])
        treated_rucc.append(tr)
        control_rucc.append(cr)

        # Pre-treatment suicide rate
        ts = float(row['treated_pre_suicide'])
        cs_val = float(row['control_pre_suicide'])
        treated_suicide.append(ts)
        control_suicide.append(cs_val)

        # WHP quintile (for scatter coloring)
        whp_quintile.append(int(row['treated_WHP_quintile']))

        # Mahalanobis distance
        mah_dist.append(float(row['mahalanobis_dist']))

# ── Summary statistics ────────────────────────────────────────────────────────
t_min = min(treated_whp)
t_max = max(treated_whp)
c_min = min(control_whp)
c_max = max(control_whp)

# Overlap proportion: fraction of treated range covered by control range
overlap_low  = max(t_min, c_min)
overlap_high = min(t_max, c_max)
treated_range = t_max - t_min if t_max != t_min else 1.0
overlap_prop = max(0.0, (overlap_high - overlap_low) / treated_range)

mean_mah = sum(mah_dist) / len(mah_dist) if mah_dist else float('nan')

print("=" * 60)
print("Common Support Summary Statistics")
print("=" * 60)
print(f"WHP rank range for treated:  [{t_min:.4f}, {t_max:.4f}]")
print(f"WHP rank range for control:  [{c_min:.4f}, {c_max:.4f}]")
print(f"Overlap proportion:          {overlap_prop:.4f}")
print(f"Mean Mahalanobis distance:   {mean_mah:.6f}")
print("=" * 60)

# ── Build 2×2 figure ─────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(12, 9))

QUINTILE_COLORS = {1: '#1f77b4', 2: '#ff7f0e', 3: '#2ca02c',
                   4: '#d62728', 5: '#9467bd'}

# ---------- Top-left: WHP Rank histogram ----------
ax = axes[0, 0]
ax.hist(treated_whp, bins=25, alpha=0.6, color='steelblue',
        label='Treated', edgecolor='none')
ax.hist(control_whp,  bins=25, alpha=0.6, color='darkorange',
        label='Control', edgecolor='none')
for q in [0.2, 0.4, 0.6, 0.8]:
    ax.axvline(q, color='gray', linestyle='--', linewidth=0.9, alpha=0.7)
ax.set_xlabel("WHP National Rank", fontsize=11)
ax.set_ylabel("County Count",      fontsize=11)
ax.set_title("WHP Rank Distribution", fontsize=12, fontweight='bold')
ax.legend(fontsize=10)

# ---------- Top-right: Scatter treated vs control WHP rank by quintile ----------
ax = axes[0, 1]
for q in sorted(set(whp_quintile)):
    xs = [treated_whp[i] for i in range(len(whp_quintile)) if whp_quintile[i] == q]
    ys = [control_whp[i]  for i in range(len(whp_quintile)) if whp_quintile[i] == q]
    ax.scatter(xs, ys, color=QUINTILE_COLORS.get(q, 'gray'),
               alpha=0.6, s=20, label=f'Quintile {q}')
# 45-degree reference line
all_vals = treated_whp + control_whp
lo, hi = min(all_vals), max(all_vals)
ax.plot([lo, hi], [lo, hi], 'k--', linewidth=1.0, alpha=0.7)
ax.set_xlabel("Treated WHP Rank",        fontsize=11)
ax.set_ylabel("Matched Control WHP Rank", fontsize=11)
ax.set_title("Matched Pair WHP Ranks", fontsize=12, fontweight='bold')
ax.legend(fontsize=9, markerscale=1.5)

# ---------- Bottom-left: RUCC histogram ----------
ax = axes[1, 0]
rucc_bins = [x - 0.5 for x in range(1, 12)]
ax.hist(treated_rucc, bins=rucc_bins, alpha=0.6, color='steelblue',
        label='Treated', edgecolor='white', linewidth=0.3)
ax.hist(control_rucc,  bins=rucc_bins, alpha=0.6, color='darkorange',
        label='Control', edgecolor='white', linewidth=0.3)
ax.set_xlabel("RUCC Score", fontsize=11)
ax.set_ylabel("County Count", fontsize=11)
ax.set_title("RUCC Distribution", fontsize=12, fontweight='bold')
ax.legend(fontsize=10)

# ---------- Bottom-right: Pre-treatment suicide rate histogram ----------
ax = axes[1, 1]
ax.hist(treated_suicide, bins=20, alpha=0.6, color='steelblue',
        label='Treated', edgecolor='none')
ax.hist(control_suicide,  bins=20, alpha=0.6, color='darkorange',
        label='Control', edgecolor='none')
ax.set_xlabel("Pre-Treatment Suicide Rate (IHS)", fontsize=11)
ax.set_ylabel("County Count",                     fontsize=11)
ax.set_title("Pre-Treatment Suicide Rate",        fontsize=12, fontweight='bold')
ax.legend(fontsize=10)

# ── Overall title and layout ─────────────────────────────────────────────────
plt.tight_layout()
plt.savefig(OUT_PNG, dpi=150, bbox_inches='tight')
plt.close()

size_kb = os.path.getsize(OUT_PNG) / 1024
print(f"Saved: {OUT_PNG}  ({size_kb:.1f} KB)")
