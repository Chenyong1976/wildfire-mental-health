# Literature Review: Causal Effects of Wildfires on Mental Health

---

## 1. Overview

The empirical literature on wildfires and mental health is growing rapidly but remains methodologically nascent. Physical health consequences of wildfire smoke — respiratory illness, cardiovascular hospitalizations, mortality — have received sustained attention since the 1990s, but mental health outcomes account for only 25% of studies in the most recent systematic review of 139 wildfire-health papers spanning 1997–2023 (Ye et al., 2026). The evidence that does exist has accelerated in quality since 2022, with the strongest recent studies successfully isolating wildfire-specific PM2.5 from ambient pollution and decomposing the total wildfire effect into distinct causal pathways. However, no published study has applied a classic difference-in-differences, regression discontinuity, or instrumental variables design specifically to wildfire mental health outcomes at the U.S. population scale — a gap this paper addresses directly.

---

## 2. Mental Health Outcomes: What the Evidence Shows

### 2.1 Depression, Anxiety, and Mood Disorders

The most methodologically advanced evidence on acute wildfire-related mental health outcomes comes from Jung et al. (2025), who analyzed 86,588 emergency department (ED) visits in California during the July–December 2020 wildfire season. Using a cross-sectional distributed-lag nonlinear model (DLNM) that isolates wildfire-specific PM2.5 from total ambient PM2.5, they find that a 10 μg/m³ increase in wildfire-specific PM2.5 was associated with an 8% increase in all-cause mental health ED visits (cumulative risk ratio [cRR] 1.08, 95% CI 1.03–1.12), a 15% increase in depression ED visits (cRR 1.15, 95% CI 1.02–1.30), and a 29% increase in mood-affective disorder ED visits (cRR 1.29, 95% CI 1.09–1.54). Effects for depression and mood disorders persisted for up to seven days post-exposure; anxiety effects were significant for four days. The study is the first to isolate wildfire-specific from total PM2.5, which resolves a prior discrepancy in the literature: several earlier studies using total PM2.5 found null or attenuated effects, likely because wildfire and non-wildfire PM2.5 have different chemical compositions and neuroinflammatory mechanisms.

**Critical limitation — COVID-19 confounding:** The study period (July–December 2020) coincides with an acute phase of the COVID-19 pandemic. COVID-19 independently caused large increases in mental health ED visits, altered healthcare-seeking behavior (both avoidance and pandemic-related acute presentations), and produced economic and social disruption that affect depression and anxiety independent of air quality. While Jung et al. (2025) isolate wildfire-specific PM2.5 from ambient PM2.5, the DLNM design cannot separate wildfire-driven ED visits from pandemic-driven ED visits occurring on the same days. The observed effect sizes — particularly the 29% increase in mood-affective disorder visits — may therefore overstate the wildfire-specific effect. The generalizability of these estimates to non-pandemic wildfire years is unknown. Studies using pre-2020 data (Wettstein & Vaidyanathan, 2024, covering 2011–2018; Currie & Saberian, 2025, covering 2006–2018) avoid this confound entirely.

### 2.2 Psychotropic Medication Use

Wettstein and Vaidyanathan (2024) provide complementary evidence using prescription data from 7.1 million commercially insured individuals across 25 large California wildfire events between 2011 and 2018. Applying an interrupted time-series design with Poisson generalized linear models, they find that wildfire onset was followed by significant increases in antidepressant prescriptions (RR 1.04, 95% CI 1.01–1.07), anxiolytic prescriptions (RR 1.05, 95% CI 1.02–1.09), and mood stabilizer prescriptions (RR 1.06, 95% CI 1.01–1.13) over a six-week post-fire window. Crucially, sensitivity analyses controlling continuously for daily temperature, ambient air pollution, and binary extreme weather event indicators produced "persistent and similar" results, indicating that mechanisms beyond air quality — including community disruption, financial stress, and social dislocation — independently drive the prescription increase. An important limitation is that the sample is commercially insured, which skews toward higher-SES individuals; the largest effects likely appear in the Medicaid population not captured here.

### 2.3 Anxiety, Substance Use, and Hospitalization

Using Canadian administrative mental health hospitalization data from 2006–2018, Currie and Saberian (2025) decompose the total wildfire effect on mental health hospitalizations into four independent pathways: local PM2.5 exposure, evacuation orders, direct fire damage costs, and wildfire-related social media activity as a proxy for national media-driven climate anxiety. All four pathways independently affect mental health hospitalizations. The largest impacts are on anxiety and substance abuse hospitalizations. Critically, controlling for the additional pathways does little to diminish the estimated PM2.5 coefficient, establishing that these mechanisms are additive rather than substitutes. The paper also documents a media-spillover effect: wildfire events receiving national attention worsen mental health outcomes in distant populations beyond what is explained by local air quality — evidence of a climate anxiety channel that pure smoke-exposure designs would miss entirely. (Note: This is an NBER working paper as of June 2025 and has not yet been peer-reviewed.)

### 2.4 Cognitive Outcomes (Neurological Mechanism Evidence)

Du et al. (2024) provide the strongest quasi-experimental identification in the wildfire-brain-health literature, exploiting exogenous variation in daily wind direction to compare cognitive outcomes in Chinese adults exposed to upwind versus non-upwind wildfires. In a sample of approximately 6,700 individuals from the China Family Panel Studies (2014, 2018), a 10-unit increase in upwind wildfires reduced word test scores by 0.235 SD (t = −3.582, p < 0.01) and math scores by 0.236 SD (t = −2.383), with robustness checks using a ventilation coefficient instrumental variable. While cognitive outcomes differ from the affective and psychiatric outcomes central to this paper, the Du et al. design demonstrates that the wind-direction identification strategy is a credible approach for isolating smoke-exposure effects, and the magnitude of cognitive impacts corroborates the neuroinflammatory pathway linking wildfire PM2.5 to mental health deterioration.

### 2.5 PTSD and Long-Term Outcomes

Evidence on PTSD following wildfire exposure is predominantly from clinical and retrospective survey designs. The literature suggests elevated PTSD prevalence in the months following wildfire events, but specific effect size estimates did not survive adversarial verification in this review's fact-checking process, and the most widely cited ranges come from scoping reviews rather than primary studies. Long-term outcome data — defined as follow-up beyond 18 months — are essentially absent for wildfires specifically, representing a major gap. By contrast, the hurricane and flood disaster literature has documented PTSD persistence for a decade or more post-event (e.g., studies of Hurricane Katrina survivors), though these findings do not transfer cleanly to wildfires given different exposure profiles and post-disaster reconstruction timelines (Merdjanoff et al., 2026).

---

## 3. Identification Strategies in Prior Work

The existing wildfire mental health literature relies almost exclusively on cross-sectional and interrupted time-series designs, which establish associations but cannot rule out confounding from the selection of high-risk populations into fire-prone areas or from co-occurring events.

**Cross-sectional DLNM (Jung et al., 2025):** The most methodologically advanced associational design. Separates wildfire-specific from total PM2.5 using satellite-derived wildfire-smoke estimates, and uses distributed-lag modeling to trace effects over days. The design controls for day-of-week and long-run county trends, but faces two compounding limitations: it cannot address selection of vulnerable populations into high-smoke areas, and its 2020 study period introduces COVID-19 as an uncontrolled simultaneous shock — pandemic-driven mental health ED surges and healthcare disruption are observationally indistinguishable from wildfire-driven effects within the DLNM framework.

**Interrupted time-series (Wettstein & Vaidyanathan, 2024):** Compares six weeks before and after wildfire onset within a patient cohort. Controls for secular trends and co-occurring environmental variables, but is vulnerable to other contemporaneous shocks occurring at fire onset (e.g., power shutoffs, evacuation-related economic disruption).

**Provincial variation DiD (Currie & Saberian, 2025):** Exploits variation in wildfire timing across Canadian provinces and years to compare hospitalization rates, using province and year fixed effects. Approximates a quasi-experimental design, though fire incidence is not fully exogenous to local economic conditions.

**Wind-direction IV (Du et al., 2024):** The closest to a clean causal design in the broader literature. Uses daily wind direction as an instrument for smoke exposure, comparing areas in the upwind versus downwind path of active fires. This instrument is plausibly exogenous (wind direction is determined by meteorological conditions) and relevant (upwind placement strongly predicts smoke exposure). The design is adapted for a Chinese setting and applied to cognitive outcomes, not mental health in the U.S.

**What is missing:** No published study applies staggered difference-in-differences with heterogeneity-robust estimators (e.g., Callaway & Sant'Anna, 2021; Sun & Abraham, 2021), geographic regression discontinuity, or a lightning-strike instrumental variable to U.S. wildfire mental health outcomes at the population level. This absence is explicitly identified as a gap by both Ye et al. (2026) and Merdjanoff et al. (2026).

---

## 4. Mechanisms

The literature has converged on four distinct causal pathways from wildfire events to mental health harm:

**PM2.5/neuroinflammatory pathway:** Wildfire-specific particulate matter triggers systemic inflammation and crosses the blood-brain barrier, activating neuroinflammatory cascades associated with depression, anxiety, and mood dysregulation. This pathway operates within hours to days and accounts for the acute ED visit and prescription effects documented above. Jung et al. (2025) and Du et al. (2024) provide the most direct evidence.

**Evacuation and displacement pathway:** Forced evacuation disrupts social support networks, removes individuals from stable housing, and imposes acute logistical stress. Currie and Saberian (2025) find that evacuation orders independently increase mental health hospitalizations after controlling for PM2.5, establishing the displacement mechanism as separate from and additive to the air quality channel.

**Economic loss and property damage pathway:** Direct property loss and the financial uncertainty of post-fire rebuilding generate sustained economic stress, which has strong independent associations with depression and anxiety in the broader disaster literature. Currie and Saberian (2025) find local fire damage costs are an independent predictor of hospitalization, separate from both smoke exposure and evacuation.

**Media-mediated climate anxiety pathway:** Wildfire events generate national media coverage that elevates generalized climate anxiety in geographically distant populations. Currie and Saberian (2025) proxy this channel using wildfire-related social media activity and find significant mental health impacts in populations beyond the direct fire zone, conditional on local air quality. This mechanism is theoretically important because it implies that the population affected by any given wildfire event substantially exceeds the population in the physical exposure zone — a point with significant implications for measuring the total welfare cost of wildfires.

---

## 5. Heterogeneity by Race, Income, and Insurance Access

Some of the most striking findings in the recent literature concern the unequal distribution of wildfire mental health burdens across demographic groups.

**Race and ethnicity:** Jung et al. (2025) stratify their California ED visit analysis by race and find that Non-Hispanic Black individuals experienced a cRR of 2.35 (95% CI 1.56–3.53) for mood-affective disorder ED visits per 10 μg/m³ wildfire PM2.5 — more than double the overall average — while Hispanic individuals experienced a cRR of 1.30 (95% CI 1.06–1.59) for depression ED visits. These disparities are consistent with lower baseline access to mental health care, greater occupational outdoor exposure, higher rates of housing instability, and reduced adaptive capacity.

**Insurance and SES:** From the same dataset, Jung et al. (2025) find that only Medicaid holders — not privately insured individuals — experienced statistically significant increases in mental health and depression ED visits at later lags. This pattern is consistent with Medicaid populations having greater pre-existing mental health burden and fewer resources to mitigate smoke exposure (e.g., air filtration, remote relocation). The Wettstein and Vaidyanathan (2024) commercially insured prescription study likely *underestimates* true population-level effects precisely because it excludes the Medicaid population where impacts are concentrated.

**Structural exposure inequity:** Beyond differential harm from equal exposure, minority communities are more likely to be disproportionately exposed in the first place. Davies et al. (2018) analyzed over 70,000 U.S. census tracts and found that Native Americans are nearly six times as likely as expected to reside in tracts with both high wildfire hazard potential and high adaptive capacity deficits — the most dangerous combination of risk and vulnerability. Vargo et al. (2023) document that between 2011 and 2021, census tracts in the highest Social Vulnerability Index tertile experienced a 358% increase in heavy wildfire smoke days (from 0.92 to 4.21 days/year); within that group, the racial/ethnic minority and limited English proficiency component showed the largest increase of any subgroup — a 449% increase in heavy-smoke person-days, exceeding all other SVI dimensions.

---

## 6. Gaps in the Literature and This Paper's Contributions

The literature review reveals five systematic gaps that this paper is positioned to address:

**Gap 1 — Absence of quasi-experimental identification for U.S. mental health outcomes.** No published study has applied staggered DiD, an IV approach, or geographic RDD to wildfire mental health outcomes using U.S. population-scale administrative data. The existing causal designs (Du et al., 2024; Currie & Saberian, 2025) are applied to non-U.S. settings and/or non-affective outcomes. This paper applies Callaway and Sant'Anna (2021) staggered DiD and a lightning-strike IV to county-year panels of suicide rates, mental health ED visits, and psychotropic prescription rates.

**Gap 2 — Failure to disentangle smoke from trauma/displacement.** No study using population-scale administrative data separately estimates the PM2.5-mediated mechanism from the displacement and property-loss mechanisms within a single design. This paper operationalizes this distinction by separating counties with active fire perimeter overlap from counties exposed only to smoke transport, allowing within-design decomposition of the two primary pathways.

**Gap 3 — Commercially insured samples miss the most affected population.** The Wettstein and Vaidyanathan (2024) result — drawn entirely from a commercially insured sample — is likely a lower bound on true effects. This paper uses Medicaid claims and CDC WONDER vital statistics data, which capture the lower-SES and uninsured population where effects appear largest.

**Gap 4 — Heterogeneity mechanisms are undocumented.** While Jung et al. (2025) document racial disparities in effect size, the mechanisms driving those disparities — differential exposure versus differential vulnerability versus differential access — are not identified. This paper tests whether effects are amplified in Health Professional Shortage Areas (HPSAs), which would implicate mental health care access as a mediating mechanism.

**Gap 5 — Long-term outcomes are unmeasured.** Existing studies follow outcomes for at most a few weeks (ED visits, prescriptions). This paper exploits the county-year structure of the panel to trace effects up to five years post-fire, providing first evidence on long-run depression and suicide trends in wildfire-affected communities.

**Gap 6 — COVID-19 confounding in the most-cited recent evidence.** The most methodologically refined study (Jung et al., 2025) uses July–December 2020 data — a period when COVID-19 was simultaneously driving mental health ED surges, disrupting healthcare utilization, and causing economic shocks that independently affect depression and anxiety. This means the study's effect size estimates cannot be cleanly attributed to wildfire exposure alone. This paper avoids the problem by using a panel that excludes 2020, with estimates drawn from pre-pandemic (2011–2019) and post-acute-pandemic (2021–2023) years. For the 2021–2023 window, COVID controls (case rates, vaccination rates, pandemic unemployment) are included as robustness. This design yields the first wildfire mental health estimates that are not conflated with pandemic-era confounders.

---

## 7. References

Currie, J., & Saberian, S. (2025). *Wildfire, mental health, and the multiple pathways of harm* (NBER Working Paper No. 33912). National Bureau of Economic Research.

Davies, I. P., Haugo, R. D., Robertson, J. C., & Levin, P. S. (2018). The unequal vulnerability of communities of color to wildfire. *PLOS ONE*, 13(11), e0205825. https://pmc.ncbi.nlm.nih.gov/articles/PMC6214520/

Du, X., Liu, W., & Zhang, Y. (2024). Wildfire smoke exposure and cognitive decline: Quasi-experimental evidence from wind direction. *International Journal of Public Health*, 69, 1607194. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11266011/

Jung, J., Braun, D., Dominici, F., & Zanobetti, A. (2025). Wildfire-specific fine particulate matter and emergency department visits for mental health conditions. *JAMA Network Open*, 8(4), e255892. https://pmc.ncbi.nlm.nih.gov/articles/PMC11971671/

Merdjanoff, A., Dolan, K., & Fothergill, A. (2026). Long-term mental health needs after wildfire: Gaps in evidence and implications for recovery planning. *Environmental Research Letters*, forthcoming. https://iopscience.iop.org/article/10.1088/1748-9326/ae6d16

Vargo, J., Wilkins, J., & Balbus, J. (2023). Wildfire smoke exposure trends by social vulnerability in the United States, 2011–2021. *American Journal of Public Health*, 113(6), 647–655. https://pmc.ncbi.nlm.nih.gov/articles/PMC10262248/

Wettstein, Z. S., & Vaidyanathan, A. (2024). Wildfire events and psychotropic medication prescriptions among insured adults in California. *JAMA Network Open*, 7(2), e2356478. https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10897744/

Ye, T., Liu, Y., & Chen, K. (2026). Wildfire and human health: A systematic review and research agenda. *GeoHealth*, 10(3), e2025GH001124. https://pmc.ncbi.nlm.nih.gov/articles/PMC12914487/

---

*Methodology note: This literature review was produced using a multi-agent deep-research workflow (108 agents, 25 sources fetched, 90 claims extracted, 25 adversarially verified at 3-vote majority, 15 confirmed). Ten claims were killed by the verification process and are not cited above. Sources designated "unreliable" by the fetcher (failed to load or contained no extractable claims) are excluded.*
