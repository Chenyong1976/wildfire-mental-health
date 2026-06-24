import warnings; warnings.filterwarnings('ignore')
import pandas as pd, numpy as np

OUTDIR = r'C:\Users\chenyon\Research Paper 2026(1)'

panel = pd.read_csv(f'{OUTDIR}/panel_merged.csv', dtype={'GEOID': str})
panel['GEOID'] = panel['GEOID'].str.zfill(5)

# Merge HRSA HPSA (time-invariant flag)
hpsa = pd.read_csv(f'{OUTDIR}/hrsa_hpsa_covariates.csv', dtype={'GEOID': str})
hpsa['GEOID'] = hpsa['GEOID'].str.zfill(5)
if 'HPSA_mental_health' in panel.columns:
    panel.drop(columns=['HPSA_mental_health'], inplace=True)
panel = panel.merge(hpsa, on='GEOID', how='left')
panel['HPSA_mental_health'] = panel['HPSA_mental_health'].fillna(0).astype(int)
panel.to_csv(f'{OUTDIR}/panel_merged.csv', index=False)

print("=== PANEL SUMMARY ===")
print(f"Total obs: {len(panel):,}")
print(f"Columns ({len(panel.columns)}): {list(panel.columns)}")

pre = panel[panel['year'].between(2011, 2014)].copy()
vars_to_check = ['BP_NATIONAL_RANK','RUCC2013','BUILDINGS_FRACTION_DE','unemployment_rate','HPSA_mental_health']

print("\n=== PRE-TREATMENT BALANCE (2011-2014) ===")
fmt = "{:<30} {:>10} {:>10} {:>8}"
print(fmt.format("Variable", "Treated", "Control", "Diff %"))
print("-" * 62)
for v in vars_to_check:
    if v not in pre.columns:
        continue
    t_m = pre.loc[pre['treated']==1, v].mean()
    c_m = pre.loc[pre['treated']==0, v].mean()
    pct = abs((t_m - c_m) / t_m * 100) if t_m != 0 else 0
    print(fmt.format(v, f"{t_m:.4f}", f"{c_m:.4f}", f"{pct:.1f}%"))

print("\n=== HPSA COVERAGE ===")
t_obs = (panel['treated'] == 1).sum()
c_obs = (panel['treated'] == 0).sum()
t_hpsa = (panel.loc[panel['treated']==1, 'HPSA_mental_health'] == 1).sum()
c_hpsa = (panel.loc[panel['treated']==0, 'HPSA_mental_health'] == 1).sum()
print(f"Treated in MH shortage area: {t_hpsa:,}/{t_obs:,} = {t_hpsa/t_obs:.1%}")
print(f"Control in MH shortage area: {c_hpsa:,}/{c_obs:,} = {c_hpsa/c_obs:.1%}")

print("\n=== COHORT DISTRIBUTION ===")
cohorts = panel[panel['treated']==1].drop_duplicates('GEOID').groupby('cohort_g')['GEOID'].count()
print(cohorts.to_string())

print("\n=== UNEMPLOYMENT RATE BY YEAR (treated vs control) ===")
ur = panel.groupby(['year','treated'])['unemployment_rate'].mean().unstack()
ur.columns = ['Control', 'Treated']
print(ur.round(2).to_string())

# Update summary stats file
rows = []
for v in vars_to_check:
    if v not in pre.columns: continue
    t = pre.loc[pre['treated']==1, v]
    c = pre.loc[pre['treated']==0, v]
    t_m, c_m = t.mean(), c.mean()
    pct = abs((t_m-c_m)/t_m*100) if t_m != 0 else 0
    rows.append({"Variable": v, "Treated_mean": round(t_m,4), "Treated_SD": round(t.std(),4),
                 "Control_mean": round(c_m,4), "Control_SD": round(c.std(),4),
                 "Diff_pct": round(pct,1), "N_treated": t.notna().sum(), "N_control": c.notna().sum()})
pd.DataFrame(rows).to_csv(f'{OUTDIR}/summary_stats.csv', index=False)
print("\nSaved summary_stats.csv")
