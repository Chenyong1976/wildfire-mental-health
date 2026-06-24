# Research Plan: Causal Effects of Wildfires on Mental Health

---

## Research Question

Do wildfires causally worsen mental health outcomes in exposed U.S. populations, through what mechanisms, and how are effects distributed across socioeconomic groups?

**Primary sub-questions (each maps to a gap in the existing literature):**
1. What is the causal effect of wildfire exposure on mental health outcomes (depression, anxiety, substance use, suicide) using quasi-experimental identification at the U.S. population scale? *(Gap 1: no published study has done this)*
2. How large is the PM2.5/air-quality pathway relative to the trauma/displacement pathway? *(Gap 2: mechanisms have not been decomposed within a single population-scale design)*
3. Are effects concentrated among Medicaid-insured and racial/ethnic minority populations — and is that driven by differential *exposure* or differential *vulnerability*? *(Gap 3: prior work uses commercially insured samples that miss the highest-impact group)*
4. Do mental health effects persist over multi-year horizons? *(Gap 4: no study has long-run follow-up for wildfires specifically)*

---

## Motivation

Wildfire frequency and burned area have increased sharply since the 1990s. Despite extensive research on wildfire smoke and physical health (respiratory, cardiovascular), mental health outcomes account for only **25% of studies** in the most recent systematic review of 139 wildfire-health papers spanning 1997–2023 (Ye et al., 2026). The associational evidence that does exist is striking: a 10 μg/m³ increase in wildfire-specific PM2.5 is associated with an 8% increase in all-cause mental health ED visits, a 15% increase in depression visits, and a 29% increase in mood-affective disorder visits (Jung et al., 2025). A separate study found 4–6% increases in psychotropic prescription rates over six weeks following wildfire onset (Wettstein & Vaidyanathan, 2024). But none of these studies can identify causal effects: they use cross-sectional or interrupted time-series designs that cannot address the selection of vulnerable populations into fire-prone areas.

Meanwhile, the distributional stakes are high. Non-Hispanic Black individuals face a 135% increase in mood disorder ED visits per unit wildfire PM2.5 (cRR 2.35; Jung et al., 2025). Medicaid holders — but not privately insured individuals — show statistically significant effects, meaning existing prescription-based studies using commercially insured samples (Wettstein & Vaidyanathan, 2024) are systematically missing the highest-impact population. Racial and ethnic minority communities also bear a structural double burden: they are overrepresented in high-wildfire-risk areas *and* have faced the steepest increases in smoke exposure over the past decade — a 449% rise in heavy-smoke person-days between 2011 and 2021 (Vargo et al., 2023).

---

## Literature Context and What This Paper Does Differently

| Prior study | Design | Key limitation |
|---|---|---|
| Jung et al. (2025) | Cross-sectional DLNM, CA 2020 | Association only; single state, single year; **2020 data conflates wildfire and COVID-19 effects** — pandemic independently spiked mental health ED visits and disrupted healthcare utilization |
| Wettstein & Vaidyanathan (2024) | Interrupted time series | Commercially insured sample only; misses Medicaid population where effects are largest |
| Currie & Saberian (2025) | Provincial variation DiD, Canada | Non-U.S. setting; mental health hospitalizations only; no heterogeneity by race/insurance |
| Du et al. (2024) | Wind-direction IV, China | Cognitive outcomes (not affective/psychiatric); non-U.S. setting |

**This paper:** First quasi-experimental study of wildfire mental health effects using U.S. population-scale administrative data (Medicaid claims, CDC WONDER), applying staggered DiD with heterogeneity-robust estimators and a lightning-strike IV, with mechanism decomposition and long-run follow-up.

---

## Identification Strategy

**Core challenge:** Wildfires are not random — they concentrate in drier, lower-income, rural areas, so naive comparisons conflate fire effects with underlying socioeconomic conditions.

### Primary: Staggered Difference-in-Differences

- Treatment: county first experiences a wildfire ≥ threshold acres in year *t*
- Control: never-treated and not-yet-treated counties
- Estimator: Callaway & Sant'Anna (2021) to avoid the "forbidden comparisons" problem of two-way fixed effects with heterogeneous and staggered treatment timing; Sun & Abraham (2021) as robustness

Dynamic event-study specification:
```
Y_{ct} = α_c + α_t + Σ_{k=−5}^{+5} β_k · 𝟙[EventTime_{ct} = k] + X_{ct}'γ + ε_{ct}
```
Pre-trend coefficients (k < 0) test the parallel trends assumption. Post-treatment coefficients trace the full dynamic response up to five years, filling the long-run gap in the literature.

### Secondary: Lightning-Strike Instrumental Variable

- Instrument: number of cloud-to-ground lightning strikes in county *c*, year *t*, interacted with fuel dryness (PDSI drought index) and wind speed
- Logic: lightning provides an exogenous ignition source; given dry conditions, lightning strikes predict fire occurrence independent of underlying socioeconomic conditions
- Data: NOAA National Lightning Detection Network (NLDN)
- First-stage F-statistic and overidentification tests will be reported; Weak-IV robust inference (Conditional Likelihood Ratio test) will be used

### Mechanism Decomposition (Novel Design Feature)

Operationalizing the four mechanisms established by Currie & Saberian (2025):

| Mechanism | Operationalization |
|---|---|
| PM2.5 / air quality | Smoke-transport counties: satellite-derived wildfire-specific PM2.5 > 10 μg/m³ but *outside* MTBS fire perimeter |
| Evacuation / displacement | Counties under CAL FIRE / state evacuation orders (linked to FEMA disaster declarations) |
| Property loss / economic | FEMA Individual Assistance declarations; county-level property loss from SHELDUS |
| Media / climate anxiety | Indicator for wildfires receiving national media attention (≥ N news mentions; smoke-only counties far from the fire) |

Counties with fire-perimeter overlap experience all four mechanisms; smoke-only counties experience primarily the PM2.5 and media channels. Comparing these two groups within the DiD framework decomposes the air-quality from trauma/displacement pathways — a decomposition not previously done in the U.S.

### WHP-Matched Control Group: Constructed Sample

The matching analysis was run on June 20, 2026 using MTBS fire perimeters (2015–2019), WRC county-level data (`wrc_county_data.xlsx`, `BP_NATIONAL_RANK`), and RUCC 2013. Full outputs are saved in `matched_county_pairs.csv` (1,146 rows) and `matched_pairs_primary.csv` (573 rows).

**Treated counties identified:** 573 counties with at least one MTBS-classified wildfire ≥ 1,000 acres between 2015 and 2019. Top states: Texas (70), California (47), Montana (41), Oklahoma (41), Idaho (38), Colorado (30), Kansas (27), Florida (27), New Mexico (25), Washington (24).

**WHP quintile distribution of treated counties:**

| WHP Quintile | Treated Counties | Share |
|---|---|---|
| Q1 (lowest) | 0 | 0% |
| Q2 | 10 | 1.7% |
| Q3 | 44 | 7.7% |
| Q4 | 119 | 20.8% |
| Q5 (highest) | 400 | 69.8% |

The concentration in Q5 confirms that realized wildfires cluster in structurally high-hazard counties — validating the need for within-quintile matching rather than matching across the full WHP distribution.

**Matching procedure:** 1:2 nearest-neighbor matching within WHP quintile on standardized `[BP_NATIONAL_RANK, RUCC2013, BUILDINGS_FRACTION_DE]`. All 573 treated counties were matched (no unmatched quintiles). Potential control pool: 2,557 counties with no fire event 2015–2019.

**Balance statistics (primary 1:1 match):**

| Variable | Treated mean | Control mean | Difference |
|---|---|---|---|
| BP_NATIONAL_RANK | 0.834 | 0.830 | +0.004 (0.5%) |
| RUCC2013 | 5.42 | 5.49 | −0.07 (1.2%) |
| BUILDINGS_FRACTION_DE | 0.579 | 0.578 | +0.001 (0.2%) |

RUCC exact match rate: 76.8%. Mean Mahalanobis distance: 0.34 (SD 0.22, max 1.42). All covariates balanced below 2%, well within the conventional 5% threshold for acceptable matching quality.

**Suggestions and limitations from the matching step:**

1. **"Surprise fire" subsample (Q2/Q3, n = 54):** The 54 treated counties in WHP quintiles 2–3 experienced fires in low-to-moderate structural hazard areas — events almost certainly driven by extreme-weather anomalies (drought, wind) rather than chronic landscape risk. These counties represent unexpected, psychologically salient shocks and may generate the largest mental health responses. Analyzing this subsample separately is a novel heterogeneity test: if effects are largest among surprise-fire counties, it implies preparedness (not just exposure) mediates mental health outcomes, with policy implications for resource pre-positioning in moderate-risk areas.

2. **Add ACS income/poverty as a 4th matching covariate:** The current matching uses `BP_NATIONAL_RANK`, `RUCC2013`, and `BUILDINGS_FRACTION_DE`. RUCC captures rurality but not income directly. Adding ACS median household income (or poverty rate) as a matching variable would reduce residual SES confounding, particularly important because income strongly predicts both fire-mitigation capacity and mental health access. Re-running with a 4-variable match is recommended before finalizing the identification strategy.

3. **Apply a Mahalanobis distance caliper:** The maximum distance of 1.42 indicates a few treated counties have poor matches (the 95th percentile is approximately 0.80). A caliper at distance ≤ 1.0 would trim these without meaningful sample loss. Poor matches reduce the credibility of the parallel trends assumption for those specific treated counties.

4. **WRC vintage alignment:** `wrc_county_data.xlsx` reflects the current WRC vintage (2023 release), not 2014. For counties whose fire occurred in 2015–2016, the `BP_NATIONAL_RANK` used for matching is not strictly pre-treatment. Plan to aggregate the `whp2014_cnt` ESRI GRID raster to county means and re-run the match using the 2014 WHP values for treatment cohorts 2015–2016, and the `whp2018_cnt` vintage for cohorts 2017–2019. This is required for the vintaged matching design described in the WHP assessment document.

5. **Alaska-specific robustness:** 14 treated counties are in Alaska (FIPS state 02), which has fundamentally different fire ecology (boreal forest, permafrost), healthcare infrastructure, and Medicaid enrollment patterns. Alaska counties should be retained in the main specification but excluded in a robustness check, as their matched controls are drawn from the lower-48 pool and may not satisfy parallel trends on healthcare access trends.

### Robustness Checks
- Placebo tests using synthetic "non-fire" years
- Donut exclusion of counties on county borders (spatial spillover check)
- Alternative treatment thresholds (1,000 / 10,000 / 50,000 acres)
- Bacon decomposition to understand which comparisons drive the TWFE estimate
- **COVID-19 sensitivity:** Re-estimate excluding 2020 entirely; for 2021–2023 years, include county-level COVID case rates, COVID-attributable ED visit share, and pandemic unemployment controls to isolate wildfire effects from pandemic-era confounders
- **WHP-unmatched vs. matched comparison:** Report parallel pre-trend plots for both the unmatched full-sample DiD and the WHP-matched sample. If pre-trends pass only in the matched sample, this provides direct evidence that WHP matching is doing meaningful work in removing structural confounds.

---

## Data Sources

### Wildfire Exposure
| Source | Variable | Notes |
|---|---|---|
| MTBS (Monitoring Trends in Burn Severity) | Burn perimeters, severity class, acreage | 1984–present; defines fire-perimeter counties |
| NIFC / CAL FIRE | Incident records, evacuation orders | Evacuation order dates for mechanism analysis |
| NOAA NLDN | Daily cloud-to-ground lightning strikes by county | Primary IV |
| NOAA PDSI | Palmer Drought Severity Index | IV interaction term (fuel dryness) |
| EPA HMS / USFS SMOKE | Satellite-derived wildfire-specific PM2.5 | Separates wildfire from ambient PM2.5 — critical for mechanism decomposition; this is what Jung et al. (2025) used |

### Mental Health Outcomes
| Source | Variable | Notes |
|---|---|---|
| CDC WONDER / Vital Statistics | Suicide rates, overdose mortality by county-year | Primary long-run outcome |
| Medicaid MAX / T-MSIS | Mental health ED visits, psychiatric hospitalizations, psychotropic prescriptions | **Priority over commercial claims** — Jung et al. (2025) show effects are only significant for Medicaid holders |
| BRFSS | Self-reported poor mental health days, depression diagnosis | Supplements administrative data |
| SAMHSA TEDS | Substance use treatment admissions by county | Substance use channel |
| PLACES (CDC) | County-level depression/anxiety prevalence | Validation and cross-check |

### Heterogeneity and Control Variables
| Source | Variable |
|---|---|
| ACS (5-year) | Income, race/ethnicity, insurance type, housing stability |
| HRSA HPSA designations | Mental health provider shortage areas — tests access-mediation hypothesis |
| CDC SVI | Social Vulnerability Index — replicates Vargo et al. (2023) stratification |
| EPA AQS | Total ambient PM2.5 (used to isolate wildfire-specific fraction) |
| SHELDUS | County-level disaster property loss |
| BLS LAUS | County unemployment (time-varying control) |

---

## Empirical Approach

### Step 1 — Construct treatment and exposure variables
- **Treated counties (complete):** `matched_pairs_primary.csv` contains 573 treated counties with wildfire onset 2015–2019; `matched_county_pairs.csv` (1,146 rows) contains the full 1:2 matched set. These files are the foundation for the DiD sample.
- Binary treatment: county has MTBS fire ≥ threshold in year *t* (test: 1k, 10k, 50k acres)
- First-fire year (`treated_first_fire_yr`) from `matched_county_pairs.csv` defines treatment cohort *g* for the Callaway-Sant'Anna estimator
- Continuous exposure: log(wildfire-specific PM2.5) from HMS/SMOKE data, annual county average
- Smoke-only indicator: wildfire-specific PM2.5 > 10 μg/m³ but outside fire perimeter
- Evacuation indicator: FEMA/CAL FIRE order linked to county-year

### Step 2 — Build county × year panel (2011–2019, 2021–2023)
- **Exclude 2020:** The COVID-19 pandemic is an uncontrolled simultaneous shock — pandemic-driven mental health ED surges, healthcare avoidance, and economic disruption cannot be separated from wildfire effects in 2020 data. This also avoids contaminating the pre-trend window for treatment cohorts defined in 2019 or 2021.
- Aggregate all outcomes and covariates to county × year
- Balanced panel: restrict to counties with non-missing outcome data throughout
- Summary statistics: separately for fire-perimeter counties, smoke-only counties, and never-treated counties
- For analyses including 2021–2023, add county-year COVID controls (case rate, vaccination rate, pandemic unemployment) as robustness

### Step 3 — Staggered DiD baseline
Implement Callaway & Sant'Anna via `pyfixest` (TWFE baseline) and `doubleml` (DML robustness with many controls). Report:
- Average Treatment Effect on the Treated (ATT) overall
- Dynamic ATT by event-time year (event study plot with 95% CI)
- Pre-trend test (joint significance of k < 0 coefficients)

### Step 4 — Mechanism decomposition
Run three parallel DiD specifications:
1. Fire-perimeter counties only (all mechanisms)
2. Smoke-only counties only (PM2.5 + media channels)
3. Fire-perimeter counties with evacuation order (adds displacement mechanism)

ATT₃ − ATT₂ ≈ displacement/trauma mechanism; ATT₂ ≈ PM2.5 + media mechanism.

### Step 5 — Heterogeneity analysis
Stratify ATT estimates by:
- Insurance type: Medicaid vs. commercial (expect Medicaid >> commercial, per Jung et al., 2025)
- Race/ethnicity: Non-Hispanic Black, Hispanic, NH White, Native American — quantify disparity in ATT
- HPSA designation: test whether effects are amplified in mental-health shortage areas (access-mediation hypothesis)
- SVI quartile: replicate Vargo et al. (2023) vulnerability stratification in a causal framework

### Step 6 — Long-run outcomes
Extend event-study window to k = +1 through +5 years. Primary outcomes for long-run analysis:
- County suicide rate (CDC WONDER)
- Substance use admissions (SAMHSA TEDS)

These are less susceptible to immediate ED-visit timing confounds and capture the persistent psychological burden.

---

## Potential Contributions

> **Contribution 1 — First quasi-experimental causal estimate of wildfire effects on mental health using U.S. population-scale data.**
> All prior U.S. studies use cross-sectional or interrupted time-series designs that cannot control for selection of vulnerable populations into fire-prone areas. This paper uses staggered DiD (Callaway & Sant'Anna, 2021) and a lightning-strike IV, providing the first credibly causal estimates. Explicitly called out as missing by Ye et al. (2026) and Merdjanoff et al. (2026).

> **Contribution 2 — Within-design decomposition of the PM2.5 vs. trauma/displacement mechanism.**
> Currie & Saberian (2025) identify four independent mechanisms in Canadian data but cannot separate them cleanly. This paper operationalizes the decomposition using MTBS fire-perimeter boundaries to split fire-affected from smoke-only counties within the same DiD framework, producing the first within-design mechanism estimates for a U.S. population.

> **Contribution 3 — Medicaid-focused administrative data captures the highest-impact population.**
> Wettstein & Vaidyanathan (2024) — the main prior prescription study — use commercially insured individuals only. Jung et al. (2025) show that only Medicaid holders face statistically significant mental health ED effects. This paper uses Medicaid MAX/T-MSIS data, shifting from the population where effects are smallest to the population where they are largest.

> **Contribution 4 — First causal evidence on racial/ethnic disparities in wildfire mental health.**
> Jung et al. (2025) document a cRR of 2.35 for Non-Hispanic Black individuals in a cross-sectional design. This paper estimates whether those disparities survive causal identification and tests whether they are driven by differential smoke *exposure* (structural, addressable via environmental policy) or differential *vulnerability* conditional on exposure (addressable via healthcare access policy).

> **Contribution 5 — Long-run outcomes: suicide and substance use up to five years post-fire.**
> No wildfire-mental health study has follow-up beyond a few weeks (ED visits, prescriptions). This paper traces effects up to five years using the county-year panel, establishing whether acute mental health deterioration translates into persistent suicide and substance use trends — a question directly relevant to disaster recovery resource allocation.

> **Contribution 6 — WHP-matched control group strengthens parallel trends credibility and adds a novel heterogeneity dimension.**
> All prior DiD-adjacent studies compare fire counties to arbitrary never-treated counties, relying on county fixed effects to absorb time-invariant differences. High-WHP counties have structurally different trend slopes — declining healthcare access, worsening economic trajectories — that a standard DiD misattributes to wildfire effects. This paper restricts the control group to counties with statistically similar structural wildfire hazard (FSim burn probability percentiles from USFS WHP maps), making the parallel trends assumption substantially more credible. This design is new to the wildfire-health literature and directly addresses the most common referee critique of DiD studies on environmental shocks. As a byproduct, WHP quintile stratification generates heterogeneity estimates that distinguish chronic-hazard counties (Q5, where communities may be partially adapted) from surprise-fire counties (Q2–Q3, where the shock is unanticipated) — a comparison not previously reported and with direct implications for disaster preparedness resource allocation.

---

## Potential Journals

- *Journal of Health Economics* — primary target; methodological contribution + health policy relevance
- *Journal of Environmental Economics and Management* — if environmental mechanism and inequality are foregrounded
- *American Economic Review: Insights* — if results are clean and contribution 1 is decisive
- *American Journal of Public Health* — broader audience if heterogeneity/equity findings dominate

---

## Timeline (Draft)

| Phase | Task |
|---|---|
| Weeks 1–2 | Data acquisition: MTBS perimeters, CDC WONDER, Medicaid T-MSIS access request, EPA HMS wildfire PM2.5, NLDN lightning |
| Weeks 3–4 | Build county × year panel (2011–2019, 2021–2023); merge all sources; flag and document 2020 exclusion; summary statistics |
| Weeks 5–6 | TWFE baseline; Callaway-Sant'Anna staggered DiD; event-study plots; pre-trend tests |
| Weeks 7–8 | Lightning-strike IV; first-stage validation; weak-IV robust inference |
| Weeks 9–10 | Mechanism decomposition (fire-perimeter vs. smoke-only); heterogeneity by race/insurance/HPSA |
| Weeks 11–12 | Long-run analysis (suicide, substance use, k = +1 to +5); robustness battery |
| Weeks 13–14 | Writing, tables, figures; circulate for feedback |

---

## Key References

Callaway, B., & Sant'Anna, P. H. C. (2021). Difference-in-differences with multiple time periods. *Journal of Econometrics*, 225(2), 200–230.

Currie, J., & Saberian, S. (2025). *Wildfire, mental health, and the multiple pathways of harm* (NBER Working Paper No. 33912).

Du, X., Liu, W., & Zhang, Y. (2024). Wildfire smoke exposure and cognitive decline. *International Journal of Public Health*, 69, 1607194.

Jung, J., Braun, D., Dominici, F., & Zanobetti, A. (2025). Wildfire-specific fine particulate matter and emergency department visits for mental health conditions. *JAMA Network Open*, 8(4), e255892.

Merdjanoff, A., Dolan, K., & Fothergill, A. (2026). Long-term mental health needs after wildfire. *Environmental Research Letters*, forthcoming.

Sun, L., & Abraham, S. (2021). Estimating dynamic treatment effects in event studies with heterogeneous treatment effects. *Journal of Econometrics*, 225(2), 175–199.

Vargo, J., Wilkins, J., & Balbus, J. (2023). Wildfire smoke exposure trends by social vulnerability in the United States, 2011–2021. *American Journal of Public Health*, 113(6), 647–655.

Wettstein, Z. S., & Vaidyanathan, A. (2024). Wildfire events and psychotropic medication prescriptions. *JAMA Network Open*, 7(2), e2356478.

Ye, T., Liu, Y., & Chen, K. (2026). Wildfire and human health: A systematic review. *GeoHealth*, 10(3), e2025GH001124.
