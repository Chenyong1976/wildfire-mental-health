import warnings; warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np

mp = pd.read_csv('matched_county_pairs.csv', dtype={'treated_GEOID': str})
mp = mp[mp['match_rank'] == 1].copy()
mp['treated_total_acres'] = pd.to_numeric(mp['treated_total_acres'], errors='coerce')

fips_state = {
    '01':'Alabama','04':'Arizona','05':'Arkansas','06':'California',
    '08':'Colorado','09':'Connecticut','10':'Delaware','11':'DC',
    '12':'Florida','13':'Georgia','16':'Idaho','17':'Illinois',
    '18':'Indiana','19':'Iowa','20':'Kansas','21':'Kentucky',
    '22':'Louisiana','23':'Maine','24':'Maryland','25':'Massachusetts',
    '26':'Michigan','27':'Minnesota','28':'Mississippi','29':'Missouri',
    '30':'Montana','31':'Nebraska','32':'Nevada','33':'New Hampshire',
    '34':'New Jersey','35':'New Mexico','36':'New York','37':'North Carolina',
    '38':'North Dakota','39':'Ohio','40':'Oklahoma','41':'Oregon',
    '42':'Pennsylvania','44':'Rhode Island','45':'South Carolina',
    '46':'South Dakota','47':'Tennessee','48':'Texas','49':'Utah',
    '50':'Vermont','51':'Virginia','53':'Washington','54':'West Virginia',
    '55':'Wisconsin','56':'Wyoming'
}
mp['state_name'] = mp['treated_STATE'].astype(str).str.zfill(2).map(fips_state)

west  = ['California','Oregon','Washington','Idaho','Montana','Wyoming','Colorado',
         'Nevada','Utah','Arizona','New Mexico']
south = ['Texas','Oklahoma','Arkansas','Louisiana','Mississippi','Alabama','Georgia',
         'Florida','South Carolina','North Carolina','Virginia','West Virginia',
         'Kentucky','Tennessee']
mw    = ['Minnesota','Wisconsin','Michigan','Iowa','Illinois','Indiana','Ohio',
         'Missouri','North Dakota','South Dakota','Nebraska','Kansas']
ne    = ['Maine','New Hampshire','Vermont','Massachusetts','Rhode Island',
         'Connecticut','New York','New Jersey','Pennsylvania','Maryland',
         'Delaware','DC']

mp['region'] = 'Other'
mp.loc[mp['state_name'].isin(west),  'region'] = 'West'
mp.loc[mp['state_name'].isin(south), 'region'] = 'South'
mp.loc[mp['state_name'].isin(mw),    'region'] = 'Midwest'
mp.loc[mp['state_name'].isin(ne),    'region'] = 'Northeast'

print("=== TREATED COUNTIES: 2015-2019 WILDFIRE SUMMARY ===")
print(f"Total treated counties: {len(mp)}")

print("\n--- First-fire year (cohort) ---")
print(mp['treated_first_fire_yr'].value_counts().sort_index().to_string())

print("\n--- Regional distribution ---")
print(mp['region'].value_counts().to_string())

print("\n--- Top 15 states ---")
print(mp['state_name'].value_counts().head(15).to_string())

print("\n--- WHP quintile ---")
print(mp['treated_WHP_quintile'].value_counts().sort_index().to_string())
print(f"  Surprise-fire (Q2-Q3): {(mp['treated_WHP_quintile'].isin([2,3])).sum()}")
print(f"  Chronic (Q4-Q5):       {(mp['treated_WHP_quintile'].isin([4,5])).sum()}")
print(f"  Q1 (lowest hazard):    {(mp['treated_WHP_quintile']==1).sum()}")

print("\n--- RUCC 2013 distribution ---")
rucc_labels = {1:'Metro large',2:'Metro medium',3:'Metro small',
               4:'Nonmetro adj lg metro',5:'Nonmetro adj small metro',
               6:'Nonmetro adj micro',7:'Nonmetro not adj micro',
               8:'Nonmetro adj rural',9:'Nonmetro most rural'}
rucc_cnt = mp['treated_RUCC'].value_counts().sort_index()
for code, cnt in rucc_cnt.items():
    print(f"  RUCC {int(code)} ({rucc_labels.get(int(code),'?')}): {cnt}")

print("\n--- Fire size (total acres per county) ---")
print(f"  Mean:    {mp['treated_total_acres'].mean():>12,.0f} acres")
print(f"  Median:  {mp['treated_total_acres'].median():>12,.0f} acres")
print(f"  p75:     {mp['treated_total_acres'].quantile(0.75):>12,.0f} acres")
print(f"  p90:     {mp['treated_total_acres'].quantile(0.90):>12,.0f} acres")
print(f"  Max:     {mp['treated_total_acres'].max():>12,.0f} acres")
q1 = (mp['treated_total_acres'] < 5000).sum()
q2 = ((mp['treated_total_acres'] >= 5000) & (mp['treated_total_acres'] < 25000)).sum()
q3 = ((mp['treated_total_acres'] >= 25000) & (mp['treated_total_acres'] < 100000)).sum()
q4 = (mp['treated_total_acres'] >= 100000).sum()
print(f"  < 5,000 ac:          {q1} counties ({q1/len(mp):.1%})")
print(f"  5,000-25,000 ac:     {q2} counties ({q2/len(mp):.1%})")
print(f"  25,000-100,000 ac:   {q3} counties ({q3/len(mp):.1%})")
print(f"  >= 100,000 ac:       {q4} counties ({q4/len(mp):.1%})")

print("\n--- Pre-2015 fire history ---")
print(f"  Had prior wildfire (<=2014): {mp['treated_pre_fire'].sum()} ({mp['treated_pre_fire'].mean():.1%})")
print(f"  No prior wildfire:           {(mp['treated_pre_fire']==0).sum()} ({(mp['treated_pre_fire']==0).mean():.1%})")

print("\n--- Acres by region ---")
reg_acres = mp.groupby('region')['treated_total_acres'].agg(['count','mean','sum'])
reg_acres.columns = ['n_counties','mean_acres','total_acres']
reg_acres = reg_acres.sort_values('n_counties', ascending=False)
for idx, row in reg_acres.iterrows():
    print(f"  {idx:<12}: {int(row['n_counties']):>3} counties | mean {row['mean_acres']:>10,.0f} ac | total {row['total_acres']:>14,.0f} ac")

print("\n--- Top 10 counties by total acres burned ---")
top10 = mp.nlargest(10, 'treated_total_acres')[
    ['treated_NAME','state_name','treated_first_fire_yr','treated_total_acres','treated_WHP_quintile']
]
for _, r in top10.iterrows():
    print(f"  {r['treated_NAME']:<20} {str(r['state_name']):<14} {int(r['treated_first_fire_yr'])}  {r['treated_total_acres']:>12,.0f} ac  Q{int(r['treated_WHP_quintile'])}")
