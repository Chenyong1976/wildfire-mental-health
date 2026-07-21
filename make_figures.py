"""
Generate Figure 1 (2x3 event-study grid) and Figure 2 (2x2 metro/nonmetro grid).
Outputs: fig_eventstudy.pdf/.png, fig_rucc.pdf/.png
"""
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os
import warnings
warnings.filterwarnings('ignore')

RESULTS_DIR = r"C:\Users\chenyon\Research Paper 2026(1)\results"
OUT_DIR     = r"C:\Users\chenyon\Research Paper 2026(1)"

# ── Typography / style ────────────────────────────────────────────────────────
plt.rcParams.update({
    'font.family':        'serif',
    'font.size':          9,
    'axes.spines.top':    False,
    'axes.spines.right':  False,
    'axes.linewidth':     0.7,
    'xtick.major.size':   3,
    'ytick.major.size':   3,
    'xtick.major.width':  0.7,
    'ytick.major.width':  0.7,
    'xtick.minor.visible': False,
    'ytick.minor.visible': False,
    'figure.dpi':         150,
    'savefig.dpi':        300,
})

C_DOT  = '#1a1a2e'   # filled point estimate dot
C_CI   = '#7090a8'   # CI line
C_ZERO = '#bbbbbb'   # y=0 dashed line
C_VLINE= '#cccccc'   # vertical pre/post separator
SHADE  = '#f2f2f2'   # pre-period shading


def plot_panel(ax, df, title='', ylabel='', note_clip=False):
    """
    Plot one event-study panel.
    df must have columns: event_time, estimate, ci_lo, ci_hi
    """
    # Background shading for pre-treatment window
    ax.axvspan(-4.55, -0.5, color=SHADE, zorder=0, linewidth=0)

    # Reference lines
    ax.axhline(0,    color=C_ZERO,  linewidth=0.85, linestyle='--', zorder=1)
    ax.axvline(-0.5, color=C_VLINE, linewidth=0.85, linestyle=':',  zorder=1)

    for _, row in df.sort_values('event_time').iterrows():
        t   = row['event_time']
        est = row['estimate']
        lo  = row['ci_lo']
        hi  = row['ci_hi']
        cap = 0.07

        # CI vertical bar
        ax.plot([t, t], [lo, hi], color=C_CI, linewidth=1.1, zorder=2,
                solid_capstyle='butt')
        # Caps
        ax.plot([t - cap, t + cap], [lo, lo], color=C_CI, linewidth=0.9, zorder=2)
        ax.plot([t - cap, t + cap], [hi, hi], color=C_CI, linewidth=0.9, zorder=2)
        # Filled dot
        ax.scatter([t], [est], color=C_DOT, s=20, zorder=3,
                   edgecolors='white', linewidths=0.4)

    # Reference year (k=-1) shown as hollow circle at 0
    ax.scatter([-1], [0], facecolors='white', edgecolors=C_DOT,
               s=20, linewidths=0.9, zorder=4)

    ax.set_xlim(-4.55, 4.55)
    ax.set_xticks(range(-4, 5))
    ax.set_xticklabels(
        [str(x) if x != -1 else '' for x in range(-4, 5)],
        fontsize=7.5
    )
    # Label ref separately so it doesn't crowd
    ax.text(-1, ax.get_ylim()[0] - (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.12,
            'ref', ha='center', va='top', fontsize=6.5, color='#666666')

    ax.tick_params(labelsize=7.5)
    ax.set_xlabel('Event time (k = year − 2015)', fontsize=8, labelpad=4)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=8.5, labelpad=4)
    if title:
        ax.set_title(title, fontsize=9, pad=5, fontweight='normal')

    if note_clip:
        ax.text(0.97, 0.03, 'CIs clipped', transform=ax.transAxes,
                ha='right', va='bottom', fontsize=6.0, color='#888888',
                style='italic')


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 1 — 2 × 3: suicide/overdose × T1/T2/T3
# ═══════════════════════════════════════════════════════════════════════════════
df = pd.read_csv(os.path.join(RESULTS_DIR, 'did_2015_eventstudy.csv'))

THRESHOLDS = [
    ('T1_moderate_1k',     'T1: $\\geq$1,000 ac\n(81 treated / 12 control)'),
    ('T2_large_5k',        'T2: $\\geq$5,000 ac\n(42 treated / 24 control)'),
    ('T3_verylarge_25k',   'T3: $\\geq$25,000 ac\n(17 treated / 14 control)'),
]
OUTCOMES = [
    ('ihs_suicide_rate',  'IHS suicide rate\n(per 100,000)'),
    ('ihs_overdose_rate', 'IHS overdose rate\n(per 100,000)'),
]
PANEL_LBL = list('abcdef')

fig1, axes = plt.subplots(2, 3, figsize=(7.2, 5.2),
                          constrained_layout=True)

for ri, (out_key, out_lbl) in enumerate(OUTCOMES):
    for ci, (thr_key, thr_lbl) in enumerate(THRESHOLDS):
        ax  = axes[ri, ci]
        sub = df[(df['threshold'] == thr_key) &
                 (df['outcome']   == out_key)].copy()

        plot_panel(
            ax,
            sub,
            title  = thr_lbl if ri == 0 else '',
            ylabel = out_lbl  if ci == 0 else '',
        )

        # Adjust y-axis after plotting so the ref label doesn't get clipped
        ylo, yhi = ax.get_ylim()
        ax.set_ylim(ylo - (yhi - ylo) * 0.08, yhi + (yhi - ylo) * 0.05)

        # Panel letter
        ax.text(0.03, 0.97, '(' + PANEL_LBL[ri * 3 + ci] + ')',
                transform=ax.transAxes, fontsize=8,
                va='top', ha='left', fontweight='bold')

for ext in ('pdf', 'png'):
    fig1.savefig(os.path.join(OUT_DIR, f'fig_eventstudy.{ext}'),
                 bbox_inches='tight')
print('Figure 1 saved (fig_eventstudy.pdf / .png)')
plt.close(fig1)


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 2 — 2 × 2: suicide/overdose × metro/nonmetro (T1 only)
# ═══════════════════════════════════════════════════════════════════════════════
df2 = pd.read_csv(os.path.join(RESULTS_DIR, 'did_2015_rucc_heterogeneity.csv'))
df2_t1 = df2[df2['threshold'].str.startswith('T1_moderate_1k')].copy()

GROUPS = [
    ('metro',    'Metropolitan (RUCC 1–3)'),
    ('nonmetro', 'Non-metropolitan (RUCC 4–9)'),
]
PANEL_LBL2 = list('abcd')
CLIP_VAL = 2.5   # clip nonmetro CIs beyond ±2.5 IHS units

fig2, axes2 = plt.subplots(2, 2, figsize=(6.5, 5.0),
                           constrained_layout=True)

for ri, (out_key, out_lbl) in enumerate(OUTCOMES):
    for ci, (grp_key, grp_lbl) in enumerate(GROUPS):
        ax  = axes2[ri, ci]
        sub = df2_t1[(df2_t1['rucc_group'] == grp_key) &
                     (df2_t1['outcome']    == out_key)].copy()

        need_clip = grp_key == 'nonmetro'
        if need_clip:
            sub['ci_lo'] = sub['ci_lo'].clip(lower=-CLIP_VAL)
            sub['ci_hi'] = sub['ci_hi'].clip(upper=CLIP_VAL)

        plot_panel(
            ax,
            sub,
            title     = grp_lbl if ri == 0 else '',
            ylabel    = out_lbl  if ci == 0 else '',
            note_clip = need_clip,
        )

        # Adjust y-axis margin for ref label
        ylo, yhi = ax.get_ylim()
        ax.set_ylim(ylo - (yhi - ylo) * 0.08, yhi + (yhi - ylo) * 0.05)

        # Mark significant k=+4 nonmetro suicide point with star
        if grp_key == 'nonmetro' and out_key == 'ihs_suicide_rate':
            k4_row = sub[sub['event_time'] == 4]
            if not k4_row.empty:
                k4_y = k4_row['ci_hi'].values[0]
                ax.text(4, k4_y + 0.05, '*', ha='center', va='bottom',
                        fontsize=10, color='#b03030', fontweight='bold')

        ax.text(0.03, 0.97, '(' + PANEL_LBL2[ri * 2 + ci] + ')',
                transform=ax.transAxes, fontsize=8,
                va='top', ha='left', fontweight='bold')

for ext in ('pdf', 'png'):
    fig2.savefig(os.path.join(OUT_DIR, f'fig_rucc.{ext}'),
                 bbox_inches='tight')
print('Figure 2 saved (fig_rucc.pdf / .png)')
plt.close(fig2)

print('Done.')
