#!/usr/bin/env Rscript
# Step 3: Callaway-Sant'Anna (2021) DiD + fixest Sun-Abraham event study
# Reads panel_analysis.csv, exports coefficient CSVs and PNG figures

suppressPackageStartupMessages({
  library(did)
  library(fixest)
  library(dplyr)
  library(readr)
  library(ggplot2)
})

OUTDIR <- "C:/Users/chenyon/Research Paper 2026(1)"
FIGDIR <- file.path(OUTDIR, "figures")
dir.create(FIGDIR, showWarnings = FALSE)

cat("========================================\n")
cat("Step 3: Staggered DiD (R)\n")
cat("========================================\n\n")

# ── Load data ─────────────────────────────────────────────────────────
df <- read_csv(file.path(OUTDIR, "panel_analysis.csv"),
               col_types = cols(GEOID = col_character()),
               show_col_types = FALSE)

# Impute county_pop via fill within county
df <- df |>
  arrange(GEOID, year) |>
  group_by(GEOID) |>
  mutate(
    county_pop = zoo::na.locf(county_pop, na.rm = FALSE),
    county_pop = zoo::na.locf(county_pop, fromLast = TRUE, na.rm = FALSE),
    county_pop = ifelse(is.na(county_pop), 1, county_pop)
  ) |>
  ungroup()

# Outcome variables
df <- df |>
  mutate(
    suicide_rate  = suicide_deaths  / county_pop * 1e5,
    overdose_rate = overdose_deaths / county_pop * 1e5,
    ihs_suicide   = asinh(suicide_rate),
    ihs_overdose  = asinh(overdose_rate),
    log_pop       = log(pmax(county_pop, 1)),
    unemployment_rate   = ifelse(is.na(unemployment_rate),
                                 median(unemployment_rate, na.rm=TRUE),
                                 unemployment_rate),
    HPSA_mental_health  = ifelse(is.na(HPSA_mental_health), 0, HPSA_mental_health),
    cohort_g      = ifelse(is.na(cohort_g) | cohort_g == 0, 0, as.integer(cohort_g)),
    county_id     = as.integer(factor(GEOID))
  )

# Panel years (no 2020)
YEARS <- 2011:2019
df <- df |> filter(year %in% YEARS)

cat(sprintf("Sample: %d obs | %d counties (%d treated, %d control)\n",
            nrow(df), n_distinct(df$GEOID),
            n_distinct(df$GEOID[df$cohort_g > 0]),
            n_distinct(df$GEOID[df$cohort_g == 0])))

cohort_sizes <- df |> filter(cohort_g > 0) |>
  distinct(GEOID, cohort_g) |> count(cohort_g)
cat("Cohorts:\n"); print(cohort_sizes)


# ── Helper: stars from p-value ───────────────────────────────────────
stars <- function(p) {
  ifelse(p < 0.001, "***", ifelse(p < 0.01, "**", ifelse(p < 0.05, "*",
         ifelse(p < 0.1, ".", ""))))
}


# ── 0. TWFE event study ──────────────────────────────────────────────
cat("\n========================================\n")
cat("0. TWFE event study — fixest::feols()\n")
cat("========================================\n")

# Event-time window: [-4,-3,-2,0,1,2,3,4]; reference = -1
# 2011-2019 panel; max post = +4 (2015 cohort in 2019)
ET_WINDOW <- c(-4, -3, -2, 0, 1, 2, 3, 4)

# Build event-time dummies (controls get 0)
for (l in ET_WINDOW) {
  cname <- if (l < 0) paste0("et_neg", abs(l)) else paste0("et_", l)
  df[[cname]] <- as.numeric(!is.na(df$cohort_g) & df$cohort_g > 0 &
                             !is.na(df$event_time) & df$event_time == l)
}
et_cols <- sapply(ET_WINDOW, function(l)
  if (l < 0) paste0("et_neg", abs(l)) else paste0("et_", l))
et_formula_str <- paste(et_cols, collapse = " + ")

run_twfe_es <- function(yname, label, tag) {
  cat(sprintf("\n-- %s --\n", label))
  fml <- as.formula(sprintf(
    "%s ~ %s + unemployment_rate + HPSA_mental_health | county_id + year",
    yname, et_formula_str
  ))
  fit <- tryCatch(
    feols(fml, data = df, cluster = ~county_id),
    error = function(e) { cat("  feols ERROR:", conditionMessage(e), "\n"); NULL }
  )
  if (is.null(fit)) return(invisible(NULL))

  cf <- coef(fit); se_v <- se(fit); pv <- pvalue(fit); ci <- confint(fit)
  l_vals <- ET_WINDOW
  col_names <- et_cols

  es_df <- data.frame(
    l         = c(l_vals, -1L),
    estimate  = c(cf[col_names], 0),
    se        = c(se_v[col_names], 0),
    conf_low  = c(ci[col_names, 1], 0),
    conf_high = c(ci[col_names, 2], 0),
    pvalue    = c(pv[col_names], 1),
    estimator = "TWFE",
    outcome   = tag,
    row.names = NULL
  )
  es_df <- es_df[order(es_df$l), ]

  # Pre-trend test (chi2 on pre-treatment dummies)
  pre_cols <- et_cols[ET_WINDOW < 0]
  pre_chi2 <- sum((cf[pre_cols] / se_v[pre_cols])^2, na.rm = TRUE)
  cat(sprintf("  Pre-trend chi2(%d) = %.3f\n", length(pre_cols), pre_chi2))

  cat("  TWFE event-study:\n")
  stars <- function(p) ifelse(p<0.001,"***",ifelse(p<0.01,"**",ifelse(p<0.05,"*",ifelse(p<0.1,".","  "))))
  for (i in seq_len(nrow(es_df))) {
    r <- es_df[i, ]
    cat(sprintf("    l=%+3d: %+.4f (SE=%.4f) %s\n",
                r$l, r$estimate, r$se, stars(r$pvalue)))
  }
  write_csv(es_df, file.path(OUTDIR, sprintf("twfe_event_study_%s.csv", tag)))

  # Plot
  p <- ggplot(es_df, aes(x = l, y = estimate,
              color = ifelse(l < 0, "Pre-treatment", "Post-treatment"))) +
    annotate("rect", xmin = min(es_df$l)-0.5, xmax = -0.5,
             ymin = -Inf, ymax = Inf, fill = "steelblue", alpha = 0.05) +
    annotate("rect", xmin = -0.5, xmax = max(es_df$l)+0.5,
             ymin = -Inf, ymax = Inf, fill = "orange", alpha = 0.05) +
    geom_hline(yintercept = 0, linetype = "dashed", linewidth = 0.5) +
    geom_vline(xintercept = -0.5, linetype = "dotted", color = "red", linewidth = 0.8) +
    geom_errorbar(aes(ymin = conf_low, ymax = conf_high), width = 0.25) +
    geom_point(size = 3) +
    scale_color_manual(values = c("Pre-treatment"="steelblue","Post-treatment"="darkorange"),
                       name = NULL) +
    scale_x_continuous(breaks = es_df$l) +
    labs(title    = sprintf("Event Study: %s\nTWFE, Never-Treated Controls (CONUS 2011-2019)", label),
         subtitle = "95% CI, cluster-robust SE by county; reference period l = -1",
         x = "Event time (years relative to first wildfire)", y = label) +
    theme_bw(base_size = 12) +
    theme(plot.title = element_text(face = "bold"), legend.position = "bottom")
  ggsave(file.path(FIGDIR, sprintf("event_study_%s.png", tag)),
         p, width = 10, height = 5.5, dpi = 150)
  cat(sprintf("  Saved: event_study_%s.png\n", tag))
  invisible(es_df)
}

twfe_suicide  <- run_twfe_es("ihs_suicide",  "Suicide (IHS per-100k)",  "suicide")
twfe_overdose <- run_twfe_es("ihs_overdose", "Overdose (IHS per-100k)", "overdose")


# ── 1. Callaway-Sant'Anna (2021) ─────────────────────────────────────
cat("\n========================================\n")
cat("1. Callaway-Sant'Anna (2021) — did package\n")
cat("========================================\n")

run_cs2021 <- function(yname, label, tag) {
  cat(sprintf("\n-- %s --\n", label))
  y <- df[[yname]]

  # att_gt: ATT(g, t) for each cohort × calendar-time cell
  out <- tryCatch(
    att_gt(
      yname        = yname,
      tname        = "year",
      idname       = "county_id",
      gname        = "cohort_g",
      xformla      = ~ unemployment_rate,
      data         = as.data.frame(df),
      control_group        = "nevertreated",
      anticipation         = 0,
      base_period          = "universal",
      allow_unbalanced_panel = TRUE,
      est_method           = "reg",
      clustervars          = "county_id",
      bstrap               = TRUE,
      biters               = 499,
      pl                   = FALSE,
      print_details        = FALSE
    ),
    error = function(e) { cat("  att_gt ERROR:", conditionMessage(e), "\n"); NULL }
  )
  if (is.null(out)) return(invisible(NULL))

  # Aggregate: calendar-time event study (by relative time)
  es <- tryCatch(
    aggte(out, type = "dynamic", na.rm = TRUE),
    error = function(e) { cat("  aggte ERROR:", conditionMessage(e), "\n"); NULL }
  )

  # Aggregate: overall ATT
  att_overall <- tryCatch(
    aggte(out, type = "simple", na.rm = TRUE),
    error = function(e) NULL
  )

  if (!is.null(att_overall)) {
    cat(sprintf("  Overall ATT = %+.4f  SE = %.4f  p = %.4f %s\n",
                att_overall$overall.att,
                att_overall$overall.se,
                2 * pnorm(-abs(att_overall$overall.att / att_overall$overall.se)),
                stars(2 * pnorm(-abs(att_overall$overall.att / att_overall$overall.se)))))
  }

  if (!is.null(es)) {
    # Extract event-study coefficients
    es_df <- data.frame(
      l         = es$egt,
      estimate  = es$att.egt,
      se        = es$se.egt,
      conf_low  = es$att.egt - 1.96 * es$se.egt,
      conf_high = es$att.egt + 1.96 * es$se.egt,
      pvalue    = 2 * pnorm(-abs(es$att.egt / es$se.egt)),
      estimator = "CS2021",
      outcome   = tag
    )
    cat("  Event-study ATT(l):\n")
    for (i in seq_len(nrow(es_df))) {
      r <- es_df[i,]
      cat(sprintf("    l=%+3d: %+.4f (SE=%.4f) %s\n",
                  r$l, r$estimate, r$se, stars(r$pvalue)))
    }

    # Save CSV
    write_csv(es_df, file.path(OUTDIR, sprintf("cs2021_event_study_%s.csv", tag)))

    # Plot
    p <- ggplot(es_df, aes(x = l, y = estimate)) +
      annotate("rect", xmin = -4.5, xmax = -0.5, ymin = -Inf, ymax = Inf,
               fill = "steelblue", alpha = 0.05) +
      annotate("rect", xmin = -0.5, xmax = max(es_df$l) + 0.5, ymin = -Inf, ymax = Inf,
               fill = "orange", alpha = 0.05) +
      geom_hline(yintercept = 0, linetype = "dashed", linewidth = 0.5) +
      geom_vline(xintercept = -0.5, linetype = "dotted", color = "red", linewidth = 0.8) +
      geom_errorbar(aes(ymin = conf_low, ymax = conf_high), width = 0.25,
                    color = ifelse(es_df$l < 0, "steelblue", "darkorange")) +
      geom_point(size = 3,
                 color = ifelse(es_df$l < 0, "steelblue", "darkorange")) +
      scale_x_continuous(breaks = es_df$l) +
      labs(
        title    = sprintf("Event Study: %s\nCallaway-Sant'Anna (2021), Never-Treated Controls", label),
        subtitle = "95% CI, cluster-robust SE by county; reference period l = -1",
        x        = "Event time (years relative to first wildfire)",
        y        = label
      ) +
      theme_bw(base_size = 12) +
      theme(plot.title = element_text(face = "bold"))

    ggsave(file.path(FIGDIR, sprintf("cs2021_event_study_%s.png", tag)),
           p, width = 10, height = 5.5, dpi = 150)
    cat(sprintf("  Saved: cs2021_event_study_%s.png\n", tag))
  }

  # Cohort-specific ATTs
  att_cohort <- tryCatch(
    aggte(out, type = "group", na.rm = TRUE),
    error = function(e) NULL
  )
  if (!is.null(att_cohort)) {
    coh_df <- data.frame(
      cohort    = att_cohort$egt,
      att       = att_cohort$att.egt,
      se        = att_cohort$se.egt,
      pvalue    = 2 * pnorm(-abs(att_cohort$att.egt / att_cohort$se.egt)),
      outcome   = tag
    )
    cat("  Cohort-specific ATT(g):\n")
    for (i in seq_len(nrow(coh_df))) {
      r <- coh_df[i,]
      cat(sprintf("    g=%d: %+.4f (SE=%.4f) p=%.3f %s\n",
                  r$cohort, r$att, r$se, r$pvalue, stars(r$pvalue)))
    }
    write_csv(coh_df, file.path(OUTDIR, sprintf("cs2021_cohort_att_%s.csv", tag)))
  }

  invisible(list(att_gt = out, es = es, overall = att_overall))
}

res_suicide  <- run_cs2021("ihs_suicide",  "Suicide (IHS per-100k)",  "suicide")
res_overdose <- run_cs2021("ihs_overdose", "Overdose (IHS per-100k)", "overdose")


# ── 2. Sun-Abraham (2021) via fixest ─────────────────────────────────
cat("\n========================================\n")
cat("2. Sun-Abraham (2021) — fixest::sunab()\n")
cat("========================================\n")

run_sunab <- function(yname, label, tag) {
  cat(sprintf("\n-- %s --\n", label))

  fml <- as.formula(sprintf(
    "%s ~ sunab(cohort_g, year) + unemployment_rate + HPSA_mental_health | county_id + year",
    yname
  ))

  fit <- tryCatch(
    feols(fml, data = df, cluster = ~county_id),
    error = function(e) { cat("  feols ERROR:", conditionMessage(e), "\n"); NULL }
  )
  if (is.null(fit)) return(invisible(NULL))

  # iplot gives event-study coefficients
  cf <- coef(fit)
  se_v <- se(fit)
  pv   <- pvalue(fit)
  ci   <- confint(fit)

  # Extract sunab event-time terms
  nm <- names(cf)
  is_sunab <- grepl("^year::", nm)

  es_df <- data.frame(
    term      = nm[is_sunab],
    l         = as.integer(sub("^year::([-0-9]+).*", "\\1", nm[is_sunab])),
    estimate  = cf[is_sunab],
    se        = se_v[is_sunab],
    conf_low  = ci[is_sunab, 1],
    conf_high = ci[is_sunab, 2],
    pvalue    = pv[is_sunab],
    estimator = "SunAbraham2021",
    outcome   = tag,
    row.names = NULL
  )
  es_df <- es_df[order(es_df$l),]

  # Add reference period at l=-1
  ref_row <- data.frame(term="ref", l=-1L, estimate=0, se=0,
                        conf_low=0, conf_high=0, pvalue=1,
                        estimator="SunAbraham2021", outcome=tag)
  es_df <- rbind(es_df, ref_row) |> arrange(l)

  cat("  Sun-Abraham event-study ATT(l):\n")
  for (i in seq_len(nrow(es_df))) {
    r <- es_df[i,]
    cat(sprintf("    l=%+3d: %+.4f (SE=%.4f) %s\n",
                r$l, r$estimate, r$se, stars(r$pvalue)))
  }
  write_csv(es_df, file.path(OUTDIR, sprintf("sunab_event_study_%s.csv", tag)))

  # Plot
  p <- ggplot(es_df, aes(x = l, y = estimate,
              color = ifelse(l < 0, "Pre-treatment", "Post-treatment"))) +
    annotate("rect", xmin = min(es_df$l)-0.5, xmax = -0.5,
             ymin = -Inf, ymax = Inf, fill = "steelblue", alpha = 0.05) +
    annotate("rect", xmin = -0.5, xmax = max(es_df$l)+0.5,
             ymin = -Inf, ymax = Inf, fill = "orange", alpha = 0.05) +
    geom_hline(yintercept = 0, linetype = "dashed", linewidth = 0.5) +
    geom_vline(xintercept = -0.5, linetype = "dotted", color = "red", linewidth = 0.8) +
    geom_errorbar(aes(ymin = conf_low, ymax = conf_high), width = 0.25) +
    geom_point(size = 3) +
    scale_color_manual(values = c("Pre-treatment"="steelblue","Post-treatment"="darkorange"),
                       name = NULL) +
    scale_x_continuous(breaks = es_df$l) +
    labs(
      title    = sprintf("Event Study: %s\nSun-Abraham (2021), Never-Treated Controls", label),
      subtitle = "95% CI, cluster-robust SE by county; reference period l = -1",
      x        = "Event time (years relative to first wildfire)",
      y        = label
    ) +
    theme_bw(base_size = 12) +
    theme(plot.title = element_text(face = "bold"), legend.position = "bottom")

  ggsave(file.path(FIGDIR, sprintf("sunab_event_study_%s.png", tag)),
         p, width = 10, height = 5.5, dpi = 150)
  cat(sprintf("  Saved: sunab_event_study_%s.png\n", tag))

  invisible(es_df)
}

sa_suicide  <- run_sunab("ihs_suicide",  "Suicide (IHS per-100k)",  "suicide")
sa_overdose <- run_sunab("ihs_overdose", "Overdose (IHS per-100k)", "overdose")


# ── 3. Depression: 2x2 DiD (PLACES 2019 vs 2023) ────────────────────
cat("\n========================================\n")
cat("3. Depression prevalence (CDC PLACES, 2019 vs 2023)\n")
cat("========================================\n")

df_pl <- df |>
  filter(!is.na(pct_depression), year %in% c(2019, 2023)) |>
  mutate(
    post           = as.integer(year == 2023),
    treated_by2019 = as.integer(cohort_g > 0 & cohort_g <= 2019),
    did_term       = treated_by2019 * post
  )
cat(sprintf("  N = %d obs, %d counties\n", nrow(df_pl), n_distinct(df_pl$GEOID)))

fit_pl <- tryCatch(
  feols(pct_depression ~ did_term + unemployment_rate + log_pop | county_id + year,
        data = df_pl, cluster = ~county_id),
  error = function(e) { cat("  ERROR:", conditionMessage(e), "\n"); NULL }
)

if (!is.null(fit_pl)) {
  cf  <- coef(fit_pl)["did_term"]
  se_ <- se(fit_pl)["did_term"]
  pv  <- pvalue(fit_pl)["did_term"]
  cat(sprintf("  ATT = %+.4f pp  SE = %.4f  p = %.4f %s\n",
              cf, se_, pv, stars(pv)))
  cat("  Interpretation: wildfire-exposed counties gained", round(cf, 2),
      "pp depression prevalence\n")
  cat("  relative to matched controls (2019 to 2023)\n")

  pl_df <- data.frame(term="did_term", estimate=cf, se=se_, pvalue=pv,
                      conf_low=cf-1.96*se_, conf_high=cf+1.96*se_,
                      row.names=NULL)
  write_csv(pl_df, file.path(OUTDIR, "places_depression_2x2.csv"))
}


# ── 4. Heterogeneity: surprise-fire vs. chronic ──────────────────────
cat("\n========================================\n")
cat("4. Heterogeneity: Surprise-fire vs. Chronic\n")
cat("========================================\n")

het_rows <- list()
for (sg in c(1, 0)) {
  label_h <- if (sg == 1) "Surprise-fire (WHP Q2-Q3)" else "Chronic (WHP Q4-Q5)"
  sub_ids <- df |> filter(cohort_g > 0, surprise_fire == sg) |>
    distinct(county_id) |> pull()
  sub <- df |> filter(county_id %in% sub_ids | cohort_g == 0) |>
    mutate(post_h = as.integer(county_id %in% sub_ids &
                               year >= cohort_g & cohort_g > 0))
  n_t <- length(sub_ids)
  for (yn in c("ihs_suicide","ihs_overdose")) {
    ytag <- sub("ihs_","",yn)
    fml_h <- as.formula(sprintf(
      "%s ~ post_h + unemployment_rate + HPSA_mental_health + log_pop | county_id + year", yn))
    fit_h <- tryCatch(feols(fml_h, data=sub, cluster=~county_id),
                      error=function(e) NULL)
    if (!is.null(fit_h)) {
      cf_ <- coef(fit_h)["post_h"]
      se_ <- se(fit_h)["post_h"]
      pv_ <- pvalue(fit_h)["post_h"]
      cat(sprintf("  %s (n=%d), %s: ATT=%+.4f  SE=%.4f  p=%.3f %s\n",
                  label_h, n_t, ytag, cf_, se_, pv_, stars(pv_)))
      het_rows[[length(het_rows)+1]] <- data.frame(
        subgroup=label_h, n=n_t, outcome=ytag,
        att=cf_, se=se_, pvalue=pv_, row.names=NULL)
    }
  }
}
if (length(het_rows) > 0) {
  write_csv(do.call(rbind, het_rows), file.path(OUTDIR, "heterogeneity_results.csv"))
}


# ── 5. Summary table ─────────────────────────────────────────────────
cat("\n========================================\n")
cat("SUMMARY — Key results\n")
cat("========================================\n")

# CS2021 overall ATTs
for (tag in c("suicide","overdose")) {
  f <- file.path(OUTDIR, sprintf("cs2021_cohort_att_%s.csv", tag))
  if (file.exists(f)) {
    coh <- read_csv(f, show_col_types=FALSE)
    # Weighted average ATT (cohort-size weights)
    n_vec <- cohort_sizes$n
    g_vec <- cohort_sizes$cohort_g
    att_w <- sum(coh$att[match(g_vec, coh$cohort)] * n_vec, na.rm=TRUE) / sum(n_vec)
    cat(sprintf("  CS2021 overall ATT (%s, cohort-weighted): %+.4f\n", tag, att_w))
  }
}

cat(sprintf("\n  Depression 2x2 DiD: see places_depression_2x2.csv\n"))
cat("\nAll outputs saved to:", OUTDIR, "\n")
cat("Figures saved to:    ", FIGDIR, "\n")
cat("\nDone.\n")
