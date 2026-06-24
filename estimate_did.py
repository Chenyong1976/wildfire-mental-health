"""
Step 3: Staggered DiD Estimation
Estimators:
  - Manual TWFE event study with pre-constructed dummies (event_time in [-4, +6])
  - Gardner (2021) did2s for overall ATT via pyfixest.event_study(att=True)
  - Cohort-specific DiD vs. never-treated controls
Outcomes: suicide rate, overdose rate (IHS per 100k), depression (PLACES 2x2)
"""
import warnings; warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

import pyfixest as ppf

OUTDIR = r"C:\Users\chenyon\Research Paper 2026(1)"
FIGDIR = r"C:\Users\chenyon\Research Paper 2026(1)\figures"
YEARS  = list(range(2011, 2020))
os.makedirs(FIGDIR, exist_ok=True)

# ── Load and prepare ─────────────────────────────────────────────────
df = pd.read_csv(f"{OUTDIR}/panel_analysis.csv", dtype={"GEOID": str})
df["GEOID"] = df["GEOID"].str.zfill(5)
df["county_id"] = df["GEOID"].map(
    {g: i+1 for i, g in enumerate(sorted(df["GEOID"].unique()))}
).astype(int)
df["cohort_g"] = pd.to_numeric(df["cohort_g"], errors="coerce").fillna(0).astype(int)

# Impute county_pop via ffill/bfill within county
df = df.sort_values(["county_id","year"])
df["county_pop"] = (df.groupby("county_id")["county_pop"]
                      .transform(lambda x: x.ffill().bfill()))
df["county_pop"] = df["county_pop"].fillna(
    df.groupby(["STATEFP","year"])["county_pop"].transform("median")).fillna(1)

# Outcome variables
df["suicide_rate"]  = df["suicide_deaths"]  / df["county_pop"] * 100_000
df["overdose_rate"] = df["overdose_deaths"] / df["county_pop"] * 100_000
df["ihs_suicide"]   = np.arcsinh(df["suicide_rate"])
df["ihs_overdose"]  = np.arcsinh(df["overdose_rate"])
df["log_pop"]       = np.log(df["county_pop"].clip(lower=1))

for col in ["unemployment_rate", "HPSA_mental_health"]:
    df[col] = df[col].fillna(df[col].median())

df_reg = df[df["year"].isin(YEARS)].sort_values(["county_id","year"]).reset_index(drop=True)

# Event time: year - cohort for treated, NaN for never-treated
df_reg["event_time"] = np.where(
    df_reg["cohort_g"] > 0,
    df_reg["year"] - df_reg["cohort_g"],
    np.nan
)

print(f"Sample: {len(df_reg):,} obs | {df_reg['county_id'].nunique()} counties")
print(f"Treated: {(df_reg['cohort_g']>0).sum()//12} | Control: {(df_reg['cohort_g']==0).sum()//12}")
print(f"Cohorts: {df_reg[df_reg['cohort_g']>0].drop_duplicates('county_id')['cohort_g'].value_counts().sort_index().to_dict()}")


def tidy_feols(fit):
    """Return standardized tidy DataFrame: term, estimate, se, conf_low, conf_high, pvalue."""
    df = fit.tidy().reset_index()
    renames = {}
    for c in df.columns:
        cl = c.lower().strip()
        if cl in ("coefficient","term","index","variable"):
            renames[c] = "term"
        elif cl == "estimate":
            renames[c] = "estimate"
        elif "std" in cl and "err" in cl:
            renames[c] = "se"
        elif "2.5" in c:
            renames[c] = "conf_low"
        elif "97.5" in c:
            renames[c] = "conf_high"
        elif "p" in cl and "val" in cl:
            renames[c] = "pvalue"
    return df.rename(columns=renames)


# ── Build event-time dummies for manual TWFE event study ─────────────
# Window: [-4, +6], excluding -1 (reference) and +5 (year 2020 for 2015 cohort)
# Controls have event_time = NaN → their dummies = 0 → they contribute to FE only
ET_WINDOW = [-4, -3, -2, 0, 1, 2, 3, 4]  # 2011-2019 panel; max post = +4 (2015 cohort in 2019)

for l in ET_WINDOW:
    col = f"et_{l}" if l >= 0 else f"et_neg{abs(l)}"
    df_reg[col] = ((df_reg["event_time"] == l) & df_reg["event_time"].notna()).astype(float)

et_cols    = [f"et_neg{abs(l)}" if l < 0 else f"et_{l}" for l in ET_WINDOW]
et_pre     = [c for c in et_cols if c.startswith("et_neg")]
et_post    = [c for c in et_cols if not c.startswith("et_neg")]
et_formula = " + ".join(et_cols)
controls   = "unemployment_rate + HPSA_mental_health"

print(f"\nEvent-time dummies: {et_cols}")
print(f"Event-time distribution:")
for l, c in zip(ET_WINDOW, et_cols):
    n = df_reg[c].sum()
    print(f"  l={l:+d} ({c}): {int(n):,} obs")


# ── TWFE event study function ────────────────────────────────────────
def run_twfe_event_study(yname, df_in=None):
    data = df_in if df_in is not None else df_reg
    fml  = f"{yname} ~ {et_formula} + {controls} | county_id + year"
    fit  = ppf.feols(fml, data=data, vcov={"CRV1": "county_id"})
    tidy = tidy_feols(fit)
    # Filter to event-time rows only
    event_rows = tidy[tidy["term"].isin(et_cols)].copy()
    # Map column name back to event time integer
    label_to_l = {c: l for l, c in zip(ET_WINDOW, et_cols)}
    event_rows["l"] = event_rows["term"].map(label_to_l)
    # Add reference period (l=-1, coeff=0 by construction)
    ref = pd.DataFrame({"term": ["et_neg1"], "estimate": [0.], "se": [0.],
                        "conf_low": [0.], "conf_high": [0.], "pvalue": [1.], "l": [-1]})
    event_rows = pd.concat([event_rows, ref], ignore_index=True).sort_values("l")
    return event_rows, fit


def plot_event_study(coef_df, title, ylabel, outfile):
    df_p = coef_df.dropna(subset=["l","estimate"]).sort_values("l")
    df_p["l"] = df_p["l"].astype(int)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axvspan(df_p["l"].min()-0.5, -0.5, alpha=0.04, color="steelblue")
    ax.axvspan(-0.5, df_p["l"].max()+0.5, alpha=0.04, color="orange")

    # Separate pre/post for coloring
    pre  = df_p[df_p["l"] <  0]
    post = df_p[df_p["l"] >= 0]
    for subset, color, label in [(pre,"steelblue","Pre-treatment"), (post,"darkorange","Post-treatment")]:
        ax.errorbar(subset["l"], subset["estimate"],
                    yerr=[subset["estimate"]-subset["conf_low"],
                          subset["conf_high"]-subset["estimate"]],
                    fmt="o", color=color, capsize=4, ms=6, lw=1.5, label=label)

    ax.axhline(0, color="black", lw=0.8, ls="--")
    ax.axvline(-0.5, color="red", lw=1.2, ls=":", alpha=0.7)
    ax.set_xlabel("Event time (years relative to first wildfire)", fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.set_xticks(sorted(df_p["l"].unique()))
    plt.tight_layout()
    plt.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {os.path.basename(outfile)}")
    return df_p


# ── Main estimation loop ─────────────────────────────────────────────
outcomes = [
    ("ihs_suicide",  "Suicide (IHS per-100k rate)",  "suicide"),
    ("ihs_overdose", "Overdose (IHS per-100k rate)", "overdose"),
]

for yname, ylabel, tag in outcomes:
    print(f"\n{'='*60}")
    print(f"OUTCOME: {ylabel}")
    print("="*60)

    # ── TWFE event study ───────────────────────────────────────
    print("  TWFE event study...")
    try:
        es_df, fit_twfe = run_twfe_event_study(yname)
        print(f"  {len(es_df)} event-time coefficients:")
        for _, row in es_df.sort_values("l").iterrows():
            p = row.get("pvalue", np.nan)
            stars = "***" if p<0.01 else "**" if p<0.05 else "*" if p<0.1 else ""
            print(f"    l={int(row['l']):+3d}: {row['estimate']:+.4f} "
                  f"(SE={row['se']:.4f}) {stars}")

        # Pre-trend test
        pre = es_df[es_df["l"] < -1]
        if len(pre) > 0 and "se" in pre.columns and (pre["se"] > 0).all():
            t2 = (pre["estimate"] / pre["se"])**2
            print(f"  Pre-trend chi2({len(pre)}) = {t2.sum():.3f}  (informal joint test)")

        # Plot
        df_plot = plot_event_study(
            es_df,
            title=f"Event Study: {ylabel}\nWildfire Counties vs. WHP-Matched Controls (TWFE)",
            ylabel=ylabel,
            outfile=f"{FIGDIR}/event_study_{tag}.png",
        )
        es_df.to_csv(f"{OUTDIR}/event_study_{tag}.csv", index=False)
    except Exception as e:
        print(f"  TWFE ERROR: {e}")
        import traceback; traceback.print_exc()

    # ── Overall ATT (Gardner did2s) ────────────────────────────
    print("  did2s overall ATT...")
    try:
        att_res = ppf.event_study(
            data=df_reg, yname=yname, idname="county_id", tname="year",
            gname="cohort_g",
            xfml="unemployment_rate + HPSA_mental_health + log_pop",
            cluster="county_id", estimator="did2s", att=True,
        )
        att_tidy = tidy_feols(att_res)
        att_row = att_tidy[att_tidy.get("term", pd.Series(dtype=str)).astype(str)
                           .str.contains("ATT|treat|post|did|1", case=False, na=False)]
        if len(att_row) == 0:
            att_row = att_tidy.head(1)
        r = att_row.iloc[0]
        p = r.get("pvalue", np.nan)
        stars = "***" if p<0.01 else "**" if p<0.05 else "*" if p<0.1 else ""
        print(f"  Overall ATT = {r['estimate']:+.4f}  SE={r['se']:.4f}  p={p:.4f} {stars}")
        att_tidy.to_csv(f"{OUTDIR}/overall_att_{tag}.csv", index=False)
    except Exception as e:
        print(f"  did2s ATT ERROR: {e}")


# ── Depression 2x2 DiD ────────────────────────────────────────────────
print(f"\n{'='*60}")
print("OUTCOME: Depression prevalence (CDC PLACES, 2019 vs 2023)")
print("="*60)
df_pl = df_reg[df_reg["pct_depression"].notna() & df_reg["year"].isin([2019,2023])].copy()
print(f"  N = {len(df_pl):,} obs, {df_pl['county_id'].nunique()} counties")
df_pl["post"]           = (df_pl["year"] == 2023).astype(int)
df_pl["treated_by2019"] = ((df_pl["cohort_g"]>0) & (df_pl["cohort_g"]<=2019)).astype(int)
df_pl["did_term"]       = df_pl["treated_by2019"] * df_pl["post"]
try:
    fit_pl = ppf.feols(
        "pct_depression ~ did_term + unemployment_rate + log_pop | county_id + year",
        data=df_pl, vcov={"CRV1": "county_id"},
    )
    pl_t = tidy_feols(fit_pl)
    r = pl_t[pl_t["term"] == "did_term"].iloc[0]
    stars = "***" if r["pvalue"]<0.01 else "**" if r["pvalue"]<0.05 else "*" if r["pvalue"]<0.1 else ""
    print(f"  ATT = {r['estimate']:+.4f} pp  SE={r['se']:.4f}  p={r['pvalue']:.4f} {stars}")
    print(f"  Interpretation: wildfire-exposed counties gained {r['estimate']:+.2f} pp depression")
    print(f"  relative to matched controls, 2019 to 2023 (4-8 yrs post fire depending on cohort)")
    pl_t.to_csv(f"{OUTDIR}/places_depression_2x2.csv", index=False)
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback; traceback.print_exc()


# ── Cohort-specific ATT: suicide ─────────────────────────────────────
print(f"\n{'='*60}")
print("COHORT-SPECIFIC ATT (post-treatment avg) - Suicide vs. never-treated")
print("="*60)
cohort_rows = []
for g in [2015, 2016, 2017, 2018, 2019]:
    sub = df_reg[(df_reg["cohort_g"]==g) | (df_reg["cohort_g"]==0)].copy()
    sub["post_g"] = ((sub["cohort_g"]==g) & (sub["year"]>=g)).astype(int)
    n_t = (sub["cohort_g"]==g).sum() // 12
    try:
        fit_g = ppf.feols(
            f"ihs_suicide ~ post_g + {controls} | county_id + year",
            data=sub, vcov={"CRV1": "county_id"},
        )
        t = tidy_feols(fit_g)
        r = t[t["term"]=="post_g"].iloc[0]
        stars = "***" if r["pvalue"]<0.01 else "**" if r["pvalue"]<0.05 else "*" if r["pvalue"]<0.1 else ""
        print(f"  g={g} (n={n_t}): ATT={r['estimate']:+.4f}  SE={r['se']:.4f}  p={r['pvalue']:.3f} {stars}")
        cohort_rows.append({"cohort":g,"n":n_t,"att":r["estimate"],"se":r["se"],"pvalue":r["pvalue"]})
    except Exception as e:
        print(f"  g={g}: {e}")
if cohort_rows:
    pd.DataFrame(cohort_rows).to_csv(f"{OUTDIR}/cohort_att_suicide.csv", index=False)


# ── Cohort-specific ATT: overdose ────────────────────────────────────
print(f"\n{'='*60}")
print("COHORT-SPECIFIC ATT (post-treatment avg) - Overdose vs. never-treated")
print("="*60)
for g in [2015, 2016, 2017, 2018, 2019]:
    sub = df_reg[(df_reg["cohort_g"]==g) | (df_reg["cohort_g"]==0)].copy()
    sub["post_g"] = ((sub["cohort_g"]==g) & (sub["year"]>=g)).astype(int)
    n_t = (sub["cohort_g"]==g).sum() // 12
    try:
        fit_g = ppf.feols(
            f"ihs_overdose ~ post_g + {controls} | county_id + year",
            data=sub, vcov={"CRV1": "county_id"},
        )
        t = tidy_feols(fit_g)
        r = t[t["term"]=="post_g"].iloc[0]
        stars = "***" if r["pvalue"]<0.01 else "**" if r["pvalue"]<0.05 else "*" if r["pvalue"]<0.1 else ""
        print(f"  g={g} (n={n_t}): ATT={r['estimate']:+.4f}  SE={r['se']:.4f}  p={r['pvalue']:.3f} {stars}")
    except Exception as e:
        print(f"  g={g}: {e}")


# ── Heterogeneity: surprise-fire vs. chronic ──────────────────────────
print(f"\n{'='*60}")
print("HETEROGENEITY: Surprise-fire (WHP Q2-Q3) vs. Chronic (Q4-Q5)")
print("="*60)
het_rows = []
for subgroup, label in [(1,"Surprise (Q2-Q3)"), (0,"Chronic (Q4-Q5)")]:
    sub_ids = df_reg[(df_reg["cohort_g"]>0) & (df_reg["surprise_fire"]==subgroup)]["county_id"].unique()
    sub = df_reg[df_reg["county_id"].isin(sub_ids) | (df_reg["cohort_g"]==0)].copy()
    sub["post_h"] = (sub["county_id"].isin(sub_ids)
                     & (sub["year"] >= sub["cohort_g"])
                     & (sub["cohort_g"] > 0)).astype(int)
    n_t = len(sub_ids)
    for yname, ytag in [("ihs_suicide","suicide"), ("ihs_overdose","overdose")]:
        try:
            fit_h = ppf.feols(
                f"{yname} ~ post_h + {controls} | county_id + year",
                data=sub, vcov={"CRV1": "county_id"},
            )
            t = tidy_feols(fit_h)
            r = t[t["term"]=="post_h"].iloc[0]
            stars = "***" if r["pvalue"]<0.01 else "**" if r["pvalue"]<0.05 else "*" if r["pvalue"]<0.1 else ""
            print(f"  {label} (n={n_t}), {ytag}: ATT={r['estimate']:+.4f}  SE={r['se']:.4f}  p={r['pvalue']:.3f} {stars}")
            het_rows.append({"subgroup":label,"n":n_t,"outcome":ytag,
                             "att":r["estimate"],"se":r["se"],"pvalue":r["pvalue"]})
        except Exception as e:
            print(f"  {label}, {ytag}: {e}")
if het_rows:
    pd.DataFrame(het_rows).to_csv(f"{OUTDIR}/heterogeneity_results.csv", index=False)


print(f"\n{'='*60}")
print("STEP 3 COMPLETE")
print(f"Figures: {FIGDIR}")
print(f"Outputs: event_study_*.csv, overall_att_*.csv, places_depression_2x2.csv")
print(f"         cohort_att_suicide.csv, heterogeneity_results.csv")
print("="*60)
