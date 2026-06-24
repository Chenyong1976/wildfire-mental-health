#!/usr/bin/env Rscript
# Robustness: CS2021 across three fire-size treatment thresholds
# T1: >= 1,000 ac (Moderate+, current baseline)
# T2: >= 5,000 ac (Large+)
# T3: >= 25,000 ac (Very Large)
# Outputs: robustness_firesize_att.csv + overlay event-study figures

suppressPackageStartupMessages({
  library(did)
  library(fixest)
  library(dplyr)
  library(readr)
  library(ggplot2)
  library(zoo)
})

OUTDIR <- "C:/Users/chenyon/Research Paper 2026(1)"
FIGDIR <- file.path(OUTDIR, "figures")
dir.create(FIGDIR, showWarnings = FALSE)

stars <- function(p) ifelse(p<0.001,"***",ifelse(p<0.01,"**",ifelse(p<0.05,"*",ifelse(p<0.1,".","  "))))

# Threshold registry
THRESHOLDS <- list(
  list(tag   = "T1_moderate_1k",
       label = "Moderate+ (>=1,000 ac)",
       file  = "panel_robustness_T1_moderate_1k.csv",
       color = "#2166ac"),
  list(tag   = "T2_large_5k",
       label = "Large+ (>=5,000 ac)",
       file  = "panel_robustness_T2_large_5k.csv",
       color = "#f4a582"),
  list(tag   = "T3_verylarge_25k",
       label = "Very Large (>=25,000 ac)",
       file  = "panel_robustness_T3_verylarge_25k.csv",
       color = "#d6604d")
)

# ── Shared data prep function ─────────────────────────────────────────────────
prep_panel <- function(df) {
  df |>
    arrange(GEOID, year) |>
    group_by(GEOID) |>
    mutate(
      county_pop = zoo::na.locf(county_pop, na.rm = FALSE),
      county_pop = zoo::na.locf(county_pop, fromLast = TRUE, na.rm = FALSE),
      county_pop = ifelse(is.na(county_pop), 1, county_pop)
    ) |>
    ungroup() |>
    mutate(
      suicide_rate  = suicide_deaths  / county_pop * 1e5,
      overdose_rate = overdose_deaths / county_pop * 1e5,
      ihs_suicide   = asinh(suicide_rate),
      ihs_overdose  = asinh(overdose_rate),
      unemployment_rate = ifelse(is.na(unemployment_rate),
                                  median(unemployment_rate, na.rm = TRUE),
                                  unemployment_rate),
      HPSA_mental_health = ifelse(is.na(HPSA_mental_health), 0, HPSA_mental_health),
      cohort_g  = ifelse(is.na(cohort_g) | cohort_g == 0, 0L, as.integer(cohort_g)),
      county_id = as.integer(factor(GEOID))
    ) |>
    filter(year %in% 2011:2019)
}

# ── Run CS2021 for one outcome ────────────────────────────────────────────────
run_cs <- function(df, outcome, tag, label) {
  ytag <- sub("ihs_", "", outcome)

  out <- tryCatch(
    att_gt(
      yname    = outcome, tname = "year", idname = "county_id", gname = "cohort_g",
      xformla  = ~unemployment_rate, data = as.data.frame(df),
      control_group          = "nevertreated",
      base_period            = "universal",
      allow_unbalanced_panel = TRUE,
      est_method             = "reg",
      clustervars            = "county_id",
      bstrap                 = TRUE,
      biters                 = 499,
      pl                     = FALSE,
      print_details          = FALSE
    ),
    error = function(e) { cat("    att_gt ERROR:", conditionMessage(e), "\n"); NULL }
  )
  if (is.null(out)) return(list(att = NULL, es = NULL))

  att_overall <- tryCatch(aggte(out, type = "simple",  na.rm = TRUE), error = function(e) NULL)
  es          <- tryCatch(aggte(out, type = "dynamic", na.rm = TRUE), error = function(e) NULL)

  att_row <- NULL
  if (!is.null(att_overall)) {
    p_val <- 2 * pnorm(-abs(att_overall$overall.att / att_overall$overall.se))
    att_row <- data.frame(
      threshold = label, tag = tag, outcome = ytag,
      n_treated = n_distinct(df$GEOID[df$cohort_g > 0]),
      n_control = n_distinct(df$GEOID[df$cohort_g == 0]),
      att       = att_overall$overall.att,
      se        = att_overall$overall.se,
      pvalue    = p_val,
      row.names = NULL
    )
    cat(sprintf("    %-10s ATT=%+.4f  SE=%.4f  p=%.3f %s\n",
                ytag, att_row$att, att_row$se, att_row$pvalue, stars(att_row$pvalue)))
  }

  es_df <- NULL
  if (!is.null(es)) {
    es_df <- data.frame(
      l         = es$egt,
      estimate  = es$att.egt,
      se        = es$se.egt,
      conf_low  = es$att.egt - 1.96 * es$se.egt,
      conf_high = es$att.egt + 1.96 * es$se.egt,
      pvalue    = 2 * pnorm(-abs(es$att.egt / es$se.egt)),
      threshold = label, tag = tag, outcome = ytag
    )
    # Add reference period l=-1
    ref <- data.frame(l = -1, estimate = 0, se = 0, conf_low = 0, conf_high = 0,
                      pvalue = 1, threshold = label, tag = tag, outcome = ytag)
    es_df <- rbind(es_df, ref) |> arrange(l)
    es_df <- es_df[es_df$l >= -4 & es_df$l <= 4, ]

    cat("    Event study (l):\n")
    for (i in seq_len(nrow(es_df))) {
      r <- es_df[i,]
      cat(sprintf("      l=%+3d: %+.4f (SE=%.4f) %s\n",
                  r$l, r$estimate, r$se, stars(r$pvalue)))
    }
  }

  list(att = att_row, es = es_df)
}

# ── Main loop over thresholds ─────────────────────────────────────────────────
all_att <- list()
all_es  <- list()

for (th in THRESHOLDS) {
  cat(sprintf("\n========================================\n"))
  cat(sprintf("THRESHOLD: %s\n", th$label))
  cat(sprintf("========================================\n"))

  fp <- file.path(OUTDIR, th$file)
  if (!file.exists(fp)) {
    cat("  FILE NOT FOUND:", fp, "\n")
    cat("  Run robustness_fire_size.py first.\n")
    next
  }

  df <- read_csv(fp, col_types = cols(GEOID = col_character()), show_col_types = FALSE)
  df <- prep_panel(df)

  n_t <- n_distinct(df$GEOID[df$cohort_g > 0])
  n_c <- n_distinct(df$GEOID[df$cohort_g == 0])
  cat(sprintf("  N: %d obs | %d treated | %d control\n", nrow(df), n_t, n_c))

  cohort_tab <- df |> filter(cohort_g > 0) |> distinct(GEOID, cohort_g) |> count(cohort_g)
  cat("  Cohorts:\n"); print(cohort_tab, n = 10)

  for (outcome in c("ihs_suicide", "ihs_overdose")) {
    cat(sprintf("\n  [%s]\n", sub("ihs_","",outcome)))
    res <- run_cs(df, outcome, th$tag, th$label)
    if (!is.null(res$att)) all_att[[length(all_att) + 1]] <- res$att
    if (!is.null(res$es))  all_es[[length(all_es)  + 1]] <- res$es
  }
}


# ── Save ATT comparison table ─────────────────────────────────────────────────
if (length(all_att) > 0) {
  att_df <- do.call(rbind, all_att)
  write_csv(att_df, file.path(OUTDIR, "robustness_firesize_att.csv"))

  cat("\n========================================\n")
  cat("ROBUSTNESS COMPARISON TABLE\n")
  cat("========================================\n")
  fmt <- "  %-32s %-10s n=%-4d ATT=%+.4f  SE=%.4f  p=%.3f %s\n"
  for (i in seq_len(nrow(att_df))) {
    r <- att_df[i,]
    cat(sprintf(fmt, r$threshold, r$outcome, r$n_treated,
                r$att, r$se, r$pvalue, stars(r$pvalue)))
  }
}


# ── Overlay event-study figures ───────────────────────────────────────────────
if (length(all_es) > 0) {
  es_all <- do.call(rbind, all_es)

  colors_map <- setNames(
    sapply(THRESHOLDS, function(x) x$color),
    sapply(THRESHOLDS, function(x) x$label)
  )

  for (yn in c("suicide", "overdose")) {
    sub <- es_all[es_all$outcome == yn, ]
    if (nrow(sub) == 0) next

    ylabel <- if (yn == "suicide") "Suicide (IHS per-100k)" else "Overdose (IHS per-100k)"
    title_main <- if (yn == "suicide") "Suicide" else "Overdose"

    p <- ggplot(sub, aes(x = l, y = estimate, color = threshold, fill = threshold)) +
      annotate("rect", xmin = -4.5, xmax = -0.5, ymin = -Inf, ymax = Inf,
               fill = "steelblue", alpha = 0.04) +
      annotate("rect", xmin = -0.5, xmax = 4.5, ymin = -Inf, ymax = Inf,
               fill = "orange", alpha = 0.04) +
      geom_hline(yintercept = 0, linetype = "dashed", linewidth = 0.5) +
      geom_vline(xintercept = -0.5, linetype = "dotted", color = "red", linewidth = 0.8) +
      geom_ribbon(aes(ymin = conf_low, ymax = conf_high), alpha = 0.15, color = NA) +
      geom_line(linewidth = 0.85) +
      geom_point(size = 2.5) +
      scale_color_manual(values = colors_map, name = "Treatment definition") +
      scale_fill_manual( values = colors_map, name = "Treatment definition") +
      scale_x_continuous(breaks = -4:4) +
      labs(
        title    = sprintf("Robustness — Fire Size Threshold: %s\nCallaway-Sant'Anna (2021), Never-Treated Controls", title_main),
        subtitle = "95% CI bands; reference period l = -1; cluster-robust SE by county",
        x        = "Event time (years relative to first qualifying wildfire)",
        y        = ylabel
      ) +
      theme_bw(base_size = 12) +
      theme(
        plot.title   = element_text(face = "bold"),
        legend.position = "bottom",
        legend.text  = element_text(size = 9)
      )

    out_fig <- file.path(FIGDIR, sprintf("robustness_firesize_%s.png", yn))
    ggsave(out_fig, p, width = 11, height = 5.5, dpi = 150)
    cat(sprintf("Saved: robustness_firesize_%s.png\n", yn))
  }

  # Also write full event-study table
  write_csv(es_all, file.path(OUTDIR, "robustness_firesize_eventstudy.csv"))
}

cat(sprintf("\nAll outputs saved to: %s\n", OUTDIR))
cat("Key files:\n")
cat("  robustness_firesize_att.csv          — overall ATT comparison table\n")
cat("  robustness_firesize_eventstudy.csv   — full event-study coefficients\n")
cat("  figures/robustness_firesize_suicide.png\n")
cat("  figures/robustness_firesize_overdose.png\n")
cat("\nDone.\n")
