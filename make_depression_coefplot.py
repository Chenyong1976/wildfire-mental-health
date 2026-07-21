"""
Coefficient plot for Table 2 results:
Depression prevalence and poor mental health days, by threshold and specification.
Output: fig_depression_coefplot.png
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Data from results/did_2015_depression.csv and did_2015_cs_doseresponse.csv ──

# Binary treatment estimates
BIN = {
    'depression': [
        {'label': 'T1  (≥1,000 ac)', 'beta': 2.7579, 'se': 0.9438, 'p': 0.00447, 'n': 90},
        {'label': 'T2  (≥5,000 ac)', 'beta': 0.5456, 'se': 0.7838, 'p': 0.48912, 'n': 64},
        {'label': 'T3  (≥25,000 ac)','beta': 1.3499, 'se': 1.1475, 'p': 0.25101, 'n': 30},
    ],
    'pmh': [
        {'label': 'T1  (≥1,000 ac)', 'beta': 1.6337, 'se': 0.5053, 'p': 0.00175, 'n': 90},
        {'label': 'T2  (≥5,000 ac)', 'beta': 0.2686, 'se': 0.3547, 'p': 0.45205, 'n': 64},
        {'label': 'T3  (≥25,000 ac)','beta': 0.5795, 'se': 0.4104, 'p': 0.17081, 'n': 30},
    ],
}

# Dose-response estimates (T1 only, log(1+PctBurned) among treated)
DR = {
    'depression': {'beta': 1.1802, 'se': 0.4958, 'p': 0.01990, 'n': 79},
    'pmh':        {'beta': 0.1976, 'se': 0.2690, 'p': 0.46509, 'n': 79},
}

def stars(p):
    if p < 0.01: return '***'
    if p < 0.05: return '**'
    if p < 0.10: return '*'
    return ''


def ci95(se):
    return 1.96 * se


COLORS = {
    'T1': '#1a6faf',   # blue
    'T2': '#888888',   # medium gray
    'T3': '#bbbbbb',   # light gray
    'DR': '#c0392b',   # red for dose-response
}

fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=False)
fig.subplots_adjust(wspace=0.38)

panel_keys  = ['depression', 'pmh']
panel_titles = ['Panel A: Depression Prevalence (%)', 'Panel B: Poor Mental Health Days (%)']
xlabels      = ['Percentage-point effect (2019)', 'Percentage-point effect (2019)']

for ax, key, title, xlabel in zip(axes, panel_keys, panel_titles, xlabels):
    rows   = BIN[key]
    dr_row = DR[key]

    # y positions: binary estimates at 3, 2, 1; dose-response at -0.2 (below separator)
    y_bin = [3, 2, 1]
    y_dr  = -0.25

    colors_bin = [COLORS['T1'], COLORS['T2'], COLORS['T3']]

    for i, (row, ypos, col) in enumerate(zip(rows, y_bin, colors_bin)):
        b, se = row['beta'], row['se']
        ci    = ci95(se)
        ax.errorbar(b, ypos, xerr=ci, fmt='o', color=col,
                    markersize=7, capsize=4, capthick=1.5,
                    linewidth=1.5, zorder=3)
        s = stars(row['p'])
        if s:
            ax.text(b + ci + 0.06, ypos, s, va='center', ha='left',
                    fontsize=10, color=col, fontweight='bold')

    # Thin separator line
    ax.axhline(0.45, color='#cccccc', linewidth=0.8, linestyle='--')
    ax.text(-0.05, 0.45, '  dose-response (T1)', va='center', ha='left',
            fontsize=8, color='#555555', style='italic',
            transform=ax.get_yaxis_transform())

    # Dose-response estimate
    b_dr = dr_row['beta']
    ci_dr = ci95(dr_row['se'])
    ax.errorbar(b_dr, y_dr, xerr=ci_dr, fmt='D', color=COLORS['DR'],
                markersize=6, capsize=4, capthick=1.5,
                linewidth=1.5, zorder=3, markerfacecolor='white',
                markeredgewidth=2)
    s_dr = stars(dr_row['p'])
    if s_dr:
        ax.text(b_dr + ci_dr + 0.04, y_dr, s_dr, va='center', ha='left',
                fontsize=10, color=COLORS['DR'], fontweight='bold')

    ax.axvline(0, color='black', linewidth=0.9, linestyle='--', zorder=2)

    ax.set_yticks(y_bin + [y_dr])
    ax.set_yticklabels(
        [r['label'] for r in rows] + ['log(1+PctBurned)'],
        fontsize=9.5
    )
    ax.set_ylim(-1.0, 3.8)

    ax.set_xlabel(xlabel, fontsize=9.5)
    ax.set_title(title, fontsize=10.5, fontweight='bold', pad=6)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.tick_params(axis='x', labelsize=9)

# Shared legend
dot_t1  = mpatches.Patch(color=COLORS['T1'], label='T1 binary (filled circle)')
dot_t2  = mpatches.Patch(color=COLORS['T2'], label='T2 binary')
dot_t3  = mpatches.Patch(color=COLORS['T3'], label='T3 binary')
dot_dr  = mpatches.Patch(color=COLORS['DR'], label='T1 dose-resp (open diamond)')
fig.legend(handles=[dot_t1, dot_t2, dot_t3, dot_dr],
           loc='lower center', ncol=4, fontsize=8.5,
           frameon=False, bbox_to_anchor=(0.5, -0.06))

out = r'C:\Users\chenyon\Research Paper 2026(1)\fig_depression_coefplot.png'
fig.savefig(out, dpi=200, bbox_inches='tight')
plt.close(fig)

import os
print(f'Saved: {out}')
print(f'  Size: {os.path.getsize(out)//1024} KB')
