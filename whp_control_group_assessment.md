# Assessment: Using Wildfire Hazard Potential to Construct Control Groups

---

## 1. What the Data Contains

The local `raw.zip` archive includes four distinct WHP/WRC datasets that can be used for control group construction:

| File | Content | Use |
|---|---|---|
| `wrc_county_data.xlsx` — Counties sheet | Pre-aggregated county-level WHP metrics for all 3,145 U.S. counties | **Primary matching variable** — merge directly on FIPS GEOID |
| `WHP/Data/whp2020_cls_conus.tif` | 2020 5-class classified WHP raster, 270m, CONUS | Spatial aggregation / robustness |
| `WHP/Data/whp2014_cnt/` | 2014 continuous WHP raster (ESRI GRID) | Pre-treatment matching for early study years |
| `WHP/Data/whp2018_cnt/` | 2018 continuous WHP raster (ESRI GRID) | Pre-treatment matching for later study years |

**Key county-level variables from `wrc_county_data.xlsx`:**

| Variable | Definition | Range |
|---|---|---|
| `BP_NATIONAL_RANK` | Percentile rank of the county's mean annual burn probability within the nation, derived from FSim large-fire simulations | 0–1 |
| `RISK_NATIONAL_RANK` | Percentile rank of mean Risk to Potential Structures (RPS = burn probability × fire intensity × structure vulnerability) | 0–1 |
| `BUILDINGS_FRACTION_ME` | Share of county buildings in Minimal Exposure WHP zone | 0–1 |
| `BUILDINGS_FRACTION_IE` | Share of county buildings in Indirect Exposure WHP zone | 0–1 |
| `BUILDINGS_FRACTION_DE` | Share of county buildings in Direct Exposure WHP zone | 0–1 |

**Critical property:** `BP_NATIONAL_RANK` is derived from FSim, a physics-based fire simulation model using LANDFIRE fuel/vegetation data and historical weather statistics — not from historical fire occurrence. It captures a county's structural, landscape-level wildfire risk independent of whether fires have actually occurred there. This makes it a valid pre-treatment covariate for matching that is not contaminated by reverse causality.

---

## 2. The Core Methodological Problem It Solves

### Why standard DiD controls are insufficient

The staggered DiD in the base research plan compares counties that experience wildfire onset to never-treated or not-yet-treated counties using county and year fixed effects. County fixed effects control for time-invariant differences (e.g., a county being in California vs. Ohio). But they do not control for **differential pre-trends** arising from structural wildfire risk.

Counties with high wildfire hazard potential are systematically different from low-hazard counties in ways that predict *mental health trend slopes*, not just levels:

- Higher rurality → declining access to mental health providers over time
- Lower incomes and economic base → worsening economic stress trends
- Drier, hotter climates → increasing heat-related health burden over time
- Western geography → differential exposure to other environmental and economic shocks

If high-WHP counties (which are more likely to eventually experience fires) have worsening mental health trends even absent wildfires, a standard DiD will overestimate the causal effect of fire by attributing pre-existing divergence to the treatment. The pre-trend plot may *appear* parallel if the study window is short, but the underlying confound operates at the slope level over longer panels.

### What WHP matching does

Using `BP_NATIONAL_RANK` to restrict the control group to counties with **similar structural wildfire risk** but which happened not to experience a fire in the treatment year converts the identification assumption from:

> *"In the absence of wildfire, treated and control counties would have followed parallel mental health trends"*

to the stronger:

> *"Among counties with equal probability of experiencing a wildfire (as measured by physics-based simulation), those that realized a fire and those that did not would have followed parallel mental health trends absent the fire"*

The second assumption is substantially more credible because it equates treated and control units on the structural dimensions (rurality, dryness, vegetation type, economic base) that drive both fire incidence and independent mental health trends.

---

## 3. Implementation Approaches

### Approach A — WHP-Matched Staggered DiD (Primary)

**Step 1:** Define WHP quintile for each county using `BP_NATIONAL_RANK` (Q1: 0–0.2, ..., Q5: 0.8–1.0).

**Step 2:** For each county experiencing wildfire onset in year *t*, restrict the control group to counties in the **same WHP quintile** that did not experience a fire in year *t*.

**Step 3:** Estimate the Callaway & Sant'Anna (2021) ATT within this matched control set.

**Advantage:** The parallel trends assumption now needs to hold only within WHP quintile — a much narrower comparison that equates structural fire risk. Pre-trend tests (event-study k < 0 leads) will be more likely to pass within quintile than across the full sample.

**Vintage selection:** Use `whp2014_cnt` quintiles for treatment years 2011–2015 and `whp2018_cnt` quintiles for treatment years 2016–2023, to ensure the WHP measure is pre-treatment and not contaminated by post-fire vegetation changes captured in later LANDFIRE updates. The `whp2020_cls_conus.tif` is used only as a structural landscape characterization (for the RD running variable) — **not** for outcome-year matching, given that 2020 is excluded from the analysis panel due to COVID-19 confounding. Treatment cohorts defined in 2019 or 2021 use the 2018 vintage for their pre-treatment WHP assignment.

---

### Approach B — Continuous WHP Covariate (Robustness)

Include `BP_NATIONAL_RANK` and `BP_NATIONAL_RANK²` as time-invariant county-level controls in the DiD regression:

```
Y_{ct} = α_c + α_t + Σ_k β_k · D_{c,t-k} + φ₁·BP_c + φ₂·BP_c² + X_{ct}'γ + ε_{ct}
```

This absorbs any residual confounding from structural wildfire risk without restricting the control group. Report as a robustness table alongside the main WHP-matched estimates.

---

### Approach C — WHP Class Boundary Regression Discontinuity

The 5-class WHP map (`whp2020_cls_conus.tif`) creates **sharp administrative boundaries** between risk categories that can be exploited for an RD design.

**Design:**
- Running variable: county mean continuous WHP score (aggregated from the 270m raster using the county shapefile `tl_2020_us_county.zip`)
- Threshold: the cutoff between "High" and "Very High" WHP classes (the most policy-relevant boundary)
- Outcome: actual wildfire incidence (binary, from MTBS)

**First-stage intuition:** Counties just above the "Very High" threshold should have materially higher realized fire rates than counties just below it, conditional on the running variable being smooth through the boundary. If fire incidence jumps discontinuously at the threshold, this provides an RD-based estimate of the mental health effect of moving from "High" to "Very High" structural wildfire risk.

**This is a distinct contribution from the DiD:** The DiD estimates the effect of *realized* fire conditional on WHP class; the RD estimates the effect of *marginally higher structural risk* on long-run mental health — a different quantity of interest, relevant for understanding cumulative burden in chronic wildfire zones.

---

### Approach D — Strengthened Lightning IV via WHP Interaction

The lightning-strike IV from the base research plan becomes substantially more powerful when interacted with WHP:

```
Fire_{ct} = π₀ + π₁·(Lightning_{ct} × BUILDINGS_FRACTION_DE_c) + π₂·X_{ct} + ν_{ct}
```

**Logic:** A lightning strike in a county where 80% of buildings are in the Direct Exposure zone is far more likely to ignite a catastrophic fire than a strike in a county where 5% of buildings are exposed. The interaction of strike density with `BUILDINGS_FRACTION_DE` creates a stronger first-stage instrument, reducing the weak-instrument concern and improving precision.

**Exclusion restriction:** `BUILDINGS_FRACTION_DE` is a time-invariant structural characteristic of the landscape; interacted with weather-driven lightning strikes, the combined instrument is plausibly exogenous to mental health trends.

---

## 4. Heterogeneity by WHP Class (New Contribution)

Beyond control group construction, WHP enables a new heterogeneity analysis not in the existing literature:

**Do mental health effects differ by county WHP class?**

- **High-WHP counties** (Q5): Communities in extreme fire hazard zones may be better adapted — fire awareness, evacuation infrastructure, community mental health resources shaped by years of fire risk. A realized fire may be less surprising and traumatic.
- **Medium-WHP counties** (Q3): Communities with moderate risk that experience an unexpected large fire may face greater psychological disruption precisely because the event is unanticipated.
- **Low-WHP counties** (Q1–Q2): In these counties, fire occurrence is nearly entirely explained by extreme weather anomalies (drought, wind) — the fire is a pure shock, potentially generating the largest mental health response.

This heterogeneity test is novel in the literature and has direct policy implications: if effects are largest in medium- or low-WHP counties, disaster mental health resources should be pre-positioned in "surprise" risk areas, not just the highest-hazard zones.

---

## 5. Falsification Tests Enabled by WHP

The WHP data enables two falsification tests that strengthen causal interpretation:

**Test 1 — Within-class pre-trends:** Show that mental health pre-trends (k = −5 to k = −1 in the event study) are parallel between treated and WHP-matched control counties, but *not* parallel in an unmatched comparison that includes low-WHP controls. This demonstrates that WHP matching is doing meaningful work and that the confounding it addresses is quantitatively important.

**Test 2 — "Near-miss" counties:** Identify counties in the top WHP quintile (Q5) that did NOT experience a major wildfire during the study period. If confounding from structural wildfire risk drives the DiD estimates, these near-miss counties should show mental health trends similar to treated counties (both are high-WHP). If the DiD estimates are genuinely causal, near-miss counties should look like control counties. Formally, estimate a "placebo treatment" DiD assigning random "fire years" to high-WHP counties that never had fires — coefficients should be statistically indistinguishable from zero.

---

## 6. Contribution to the Existing Literature

The WHP-based control group construction addresses a gap that all prior studies share but none have closed:

| Methodological problem | Prior work | This paper |
|---|---|---|
| Selection of high-risk counties into treatment | County FEs control levels, not slopes; high-WHP counties have structurally different mental health trends | WHP quintile matching equates structural risk between treated and control units |
| Parallel trends assumption credibility | Tested but not guaranteed in unmatched DiD; fails visually in many environmental studies | Within-WHP-class parallel trends are substantially more credible; pre-trend tests become a real validation rather than a formality |
| Weak IV in fire occurrence models | Lightning alone has limited first-stage power in flat/humid geographies | Lightning × `BUILDINGS_FRACTION_DE` interaction provides a geography-calibrated instrument with stronger first-stage performance |
| No dose-response or heterogeneity by risk class | Effects averaged across all fire counties regardless of structural risk context | WHP quintile–stratified ATTs reveal whether effects are driven by high-hazard or surprise-fire counties |

**The specific claim this enables in the abstract:** *"We address the selection problem by restricting comparisons to counties with statistically similar structural wildfire hazard — as measured by FSim burn probability simulations — that differed only in whether a fire was realized. This design produces the first credibly causal estimates of wildfire effects on mental health for a U.S. population."*

---

## 7. Data Workflow

```
raw.zip
├── wrc_county_data.xlsx [Counties sheet]
│   └── BP_NATIONAL_RANK, RISK_NATIONAL_RANK, BUILDINGS_FRACTION_DE
│   → Merge on GEOID (5-digit FIPS) to county-year panel
│   → Quintile-assign counties → define within-quintile control groups
│
├── WHP/Data/whp2014_cnt/ + whp2018_cnt/
│   → Aggregate continuous raster to county mean using tl_2020_us_county.zip
│   → Use vintage-appropriate WHP for treatment year (2014 for pre-2016, 2018 for 2016+)
│   → Running variable for RD design (Approach C)
│
├── WHP/Data/whp2020_cls_conus.tif
│   → Class boundary mapping for RD threshold identification
│
└── mtbs_perims/ [already extracted in raw.zip]
    → Treatment variable: county × year fire occurrence / acreage
    → Also distinguishes fire-perimeter counties from smoke-only counties
    → Panel years: 2011–2019, 2021–2023 (2020 excluded — COVID-19 confound)
```

**Implementation note:** The `wrc_county_data.xlsx` Counties sheet already provides county-level WHP summaries ready for direct merge on FIPS GEOID — no raster processing is required for the primary matching approach. Raster processing is needed only for the continuous running variable in the RD design (Approach C).

---

## 8. Limitations of the WHP Approach

1. **WHP is time-invariant (or infrequently updated):** The archive has 2014, 2018, and 2020 vintages. For a study panel running 2011–2023, using a single vintage introduces measurement error in the pre-treatment WHP for early years. Mitigated by using the 2014 vintage for early treatment cohorts.

2. **WHP is a landscape characteristic, not a forecast:** The USFS explicitly notes that WHP is not a wildfire outlook or forecast and does not incorporate fuel moisture or seasonal weather. A year with anomalous drought conditions can produce fires in counties with moderate WHP. This is a feature (not a bug) for the IV design — it creates exogenous variation in realized fire conditional on structural risk — but means the WHP-matched DiD control group includes counties that face structurally similar hazard but may differ in specific-year weather.

3. **WHP does not capture community preparedness:** Two counties with identical WHP may differ in evacuation infrastructure, community fire education, and pre-positioned mental health resources — all of which affect the mental health response to fire. These are not controlled by WHP matching but can be partially addressed by including HPSA designations and FEMA preparedness grant data as covariates.

4. **County-level aggregation loses spatial variation:** The WHP raster is at 270m resolution; county aggregation via `BP_NATIONAL_RANK` averages over considerable within-county heterogeneity. The `BUILDINGS_FRACTION_DE` partially preserves this by capturing the share of buildings in the highest-risk zone, but a finer spatial unit (ZIP code or census tract) would be more precise if the mental health outcome data support it.
