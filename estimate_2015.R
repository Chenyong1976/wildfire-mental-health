# estimate_2015.R
# 2015-cohort wildfire study — Western US
#
# All treated counties share treatment year 2015 → standard TWFE is valid.
#
# Specifications:
#   1. TWFE event study  (primary): i(year, treated, ref=2014) | GEOID + year
#   2. Simple DiD        (summary): treated × post | GEOID + year
#   3. Dose-response     (intensity): i(year, log_pct_burned_2015, ref=2014)
#                                     among treated counties only
#   4. Depression 2019   (cross-section): OLS with pre-period controls
#
# Event window: l ∈ {−4,−3,−2,−1,0,+1,+2,+3,+4}  (ref = l = −1, year 2014)
# Pre-trend test: joint F-test on l = −4,−3,−2

suppressWarnings(suppressMessages({
  library(fixest)
  library(dplyr)
  library(tidyr)
  library(readr)
  library(ggplot2)
  library(purrr)
}))

setwd("C:/Users/chenyon/Research Paper 2026(1)")
dir.create("figures",  showWarnings=FALSE)
dir.create("results",  showWarnings=FALSE)

OUTCOMES   <- c("ihs_suicide_rate", "ihs_overdose_rate")
OUT_LABELS <- c("IHS Suicide Rate", "IHS Overdose Rate")
THRESHOLDS <- list(
  list(tag="T1_moderate_1k",   file="panel_2015_T1_moderate_1k.csv",
       label="T1 ≥1,000 ac",   color="#d73027"),
  list(tag="T2_large_5k",      file="panel_2015_T2_large_5k.csv",
       label="T2 ≥5,000 ac",   color="#4575b4"),
  list(tag="T3_verylarge_25k", file="panel_2015_T3_verylarge_25k.csv",
       label="T3 ≥25,000 ac",  color="#1a9850")
)

# ── Helper: run TWFE event study ───────────────────────────────────────────────
run_twfe <- function(df, outcome) {
  df <- df %>%
    mutate(
      year    = as.integer(year),
      treated = as.integer(treated)
    ) %>%
    filter(!is.na(unemployment_rate))

  form <- as.formula(paste0(
    outcome, " ~ i(year, treated, ref=2014) + unemployment_rate | GEOID + year"
  ))
  tryCatch(feols(form, data=df, vcov=~GEOID), error=function(e) {
    message("  TWFE error: ", conditionMessage(e)); NULL
  })
}

# ── Helper: extract event study coefficients ───────────────────────────────────
extract_es <- function(m, tag, outcome, label) {
  if (is.null(m)) return(NULL)
  cf  <- coef(m)
  se  <- se(m)
  pv  <- pvalue(m)
  nm  <- grep("^year::[0-9]+:treated$", names(cf), value=TRUE)
  if (length(nm) == 0) return(NULL)
  yr  <- as.integer(gsub("year::|:treated", "", nm))
  data.frame(
    event_time = yr - 2015,
    year       = yr,
    estimate   = as.numeric(cf[nm]),
    se         = as.numeric(se[nm]),
    pvalue     = as.numeric(pv[nm]),
    ci_lo      = as.numeric(cf[nm]) - 1.96 * as.numeric(se[nm]),
    ci_hi      = as.numeric(cf[nm]) + 1.96 * as.numeric(se[nm]),
    threshold  = tag,
    label      = label,
    outcome    = outcome,
    stringsAsFactors = FALSE
  )
}

# ── Helper: simple DiD ─────────────────────────────────────────────────────────
run_did <- function(df, outcome) {
  df <- df %>% filter(!is.na(unemployment_rate)) %>%
    mutate(post = as.integer(year >= 2015), treated = as.integer(treated))
  form <- as.formula(paste0(
    outcome, " ~ i(treated, post, ref=0) + unemployment_rate | GEOID + year"
  ))
  tryCatch(feols(form, data=df, vcov=~GEOID), error=function(e) NULL)
}

# ── Storage ────────────────────────────────────────────────────────────────────
all_es    <- list()
all_did   <- list()
all_dose  <- list()
all_pre   <- list()

# ═════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═════════════════════════════════════════════════════════════════════════════
for (thr in THRESHOLDS) {
  tag   <- thr$tag
  lab   <- thr$label
  fname <- thr$file
  cat("\n", strrep("=", 60), "\n")
  cat("THRESHOLD:", lab, "\n")
  cat(strrep("=", 60), "\n")

  df <- read_csv(fname, col_types=cols(GEOID=col_character()), show_col_types=FALSE) %>%
    mutate(across(c(ihs_suicide_rate, ihs_overdose_rate, unemployment_rate,
                    pct_burned_2015, log_pct_burned_2015, suicide_rate,
                    overdose_rate), as.numeric),
           year    = as.integer(year),
           treated = as.integer(treated),
           cohort_g = as.integer(cohort_g))

  n_tr <- n_distinct(df$GEOID[df$treated==1])
  n_ct <- n_distinct(df$GEOID[df$treated==0])
  cat("  Treated counties:", n_tr, " | Control counties:", n_ct, "\n")

  # ── 1. TWFE event study ─────────────────────────────────────────────────────
  cat("\n  1. TWFE EVENT STUDY\n")
  for (oc in OUTCOMES) {
    m <- run_twfe(df, oc)
    if (is.null(m)) next
    es <- extract_es(m, tag, oc, lab)
    if (!is.null(es)) {
      all_es[[length(all_es)+1]] <- es

      # Print event-time coefficients
      for (i in seq_len(nrow(es))) {
        r <- es[i,]
        stars <- ifelse(r$pvalue < .001, "***",
                 ifelse(r$pvalue < .01, "**",
                 ifelse(r$pvalue < .05, "*",
                 ifelse(r$pvalue < .1,  ".", ""))))
        cat(sprintf("  %s  l=%+3d: %+.4f (SE=%.4f, p=%.3f) %s\n",
                    oc, r$event_time, r$estimate, r$se, r$pvalue, stars))
      }

      # Pre-trend joint F-test (l = -4, -3, -2)
      pre_nm <- grep("year::(2011|2012|2013):treated", names(coef(m)), value=TRUE)
      if (length(pre_nm) >= 2) {
        ftest <- tryCatch(
          wald(m, pre_nm),
          error = function(e) NULL
        )
        if (!is.null(ftest)) {
          cat(sprintf("  %s  Pre-trend F = %.3f  p = %.4f\n",
                      oc, ftest$stat, ftest$p))
          all_pre[[length(all_pre)+1]] <- data.frame(
            threshold=tag, outcome=oc,
            F_stat=ftest$stat, p_pretrend=ftest$p
          )
        }
      }
    }
  }

  # ── 2. Simple DiD ──────────────────────────────────────────────────────────
  cat("\n  2. SIMPLE DiD\n")
  for (oc in OUTCOMES) {
    m <- run_did(df, oc)
    if (is.null(m)) next
    cf <- coef(m)
    se <- se(m)
    pv <- pvalue(m)
    nm <- grep("treated::1:post$|treated:post", names(cf), value=TRUE)
    if (length(nm) == 0) nm <- grep(":post", names(cf), value=TRUE)
    if (length(nm) > 0) {
      nm1 <- nm[1]
      cat(sprintf("  %s  ATT = %+.4f  SE = %.4f  p = %.4f\n",
                  oc, cf[nm1], se[nm1], pv[nm1]))
      all_did[[length(all_did)+1]] <- data.frame(
        threshold=tag, label=lab, outcome=oc,
        att=cf[nm1], se=se[nm1], pvalue=pv[nm1],
        ci_lo=cf[nm1] - 1.96*se[nm1],
        ci_hi=cf[nm1] + 1.96*se[nm1]
      )
    }
  }

  # ── 3. Dose-response: i(year, log_pct_burned_2015, ref=2014) ─────────────
  cat("\n  3. DOSE-RESPONSE (log_pct_burned_2015 × year)\n")
  df_tr <- df %>% filter(treated == 1, !is.na(log_pct_burned_2015),
                         !is.na(unemployment_rate))
  if (n_distinct(df_tr$GEOID) >= 5 &&
      sd(df_tr$log_pct_burned_2015, na.rm=TRUE) > 1e-6) {
    for (oc in OUTCOMES) {
      form_d <- as.formula(paste0(
        oc, " ~ i(year, log_pct_burned_2015, ref=2014) + unemployment_rate",
        " | GEOID + year"
      ))
      m_d <- tryCatch(feols(form_d, data=df_tr, vcov=~GEOID),
                      error=function(e) NULL)
      if (!is.null(m_d)) {
        cf <- coef(m_d); se <- se(m_d); pv <- pvalue(m_d)
        nm <- grep("log_pct_burned_2015", names(cf), value=TRUE)
        post_nm <- grep("::(2015|2016|2017|2018|2019):", nm, value=TRUE)
        if (length(post_nm) > 0) {
          avg_beta <- mean(cf[post_nm])
          cat(sprintf("  %s  mean post-β(dose) = %+.4f\n", oc, avg_beta))
          for (n1 in post_nm) {
            yr1 <- as.integer(gsub(".*::(\\d{4}):.*","\\1", n1))
            cat(sprintf("    l=%+3d: %+.4f (SE=%.4f, p=%.3f)\n",
                        yr1-2015, cf[n1], se[n1], pv[n1]))
          }
          all_dose[[length(all_dose)+1]] <- data.frame(
            threshold=tag, label=lab, outcome=oc,
            year=as.integer(gsub(".*::(\\d{4}):.*","\\1",post_nm)),
            beta_dose=as.numeric(cf[post_nm]),
            se_dose  =as.numeric(se[post_nm]),
            pvalue   =as.numeric(pv[post_nm])
          )
        }
      }
    }
  } else {
    cat("  Insufficient variation in log_pct_burned_2015 — skipping\n")
  }
}  # end threshold loop

# ═════════════════════════════════════════════════════════════════════════════
# DEPRESSION 2019 (cross-sectional)
# ═════════════════════════════════════════════════════════════════════════════
cat("\n", strrep("=", 60), "\n")
cat("DEPRESSION 2019 (cross-sectional regression)\n")
cat(strrep("=", 60), "\n")

all_dep <- list()

for (thr in THRESHOLDS) {
  tag   <- thr$tag
  lab   <- thr$label
  df    <- read_csv(thr$file,
                    col_types=cols(GEOID=col_character()),
                    show_col_types=FALSE) %>%
    mutate(across(c(pct_depression, ihs_suicide_rate, ihs_overdose_rate,
                    unemployment_rate, RUCC2013, log_pct_burned_2015), as.numeric),
           year=as.integer(year), treated=as.integer(treated))

  df_2019 <- df %>% filter(year == 2019, !is.na(pct_depression))
  df_pre  <- df %>% filter(year %in% 2011:2014) %>%
    group_by(GEOID) %>%
    summarise(pre_suicide  = mean(ihs_suicide_rate,  na.rm=TRUE),
              pre_overdose = mean(ihs_overdose_rate, na.rm=TRUE),
              pre_unemp    = mean(unemployment_rate, na.rm=TRUE),
              .groups="drop")

  df_dep <- df_2019 %>%
    left_join(df_pre, by="GEOID") %>%
    filter(!is.na(RUCC2013))

  cat(sprintf("\n  %s — N = %d counties with 2019 depression\n", lab, nrow(df_dep)))
  if (nrow(df_dep) < 10) { cat("  Too few — skipping\n"); next }

  cat(sprintf("  Depression 2019: treated = %.2f%%  control = %.2f%%\n",
              mean(df_dep$pct_depression[df_dep$treated==1], na.rm=TRUE),
              mean(df_dep$pct_depression[df_dep$treated==0], na.rm=TRUE)))

  m_dep <- lm(pct_depression ~ treated + pre_suicide + pre_overdose +
                pre_unemp + RUCC2013,
              data=df_dep)
  s <- summary(m_dep)
  cf <- coef(s)
  if ("treated" %in% rownames(cf)) {
    cat(sprintf("  β(treated) = %+.4f  SE = %.4f  p = %.4f\n",
                cf["treated","Estimate"],
                cf["treated","Std. Error"],
                cf["treated","Pr(>|t|)"]))
    all_dep[[length(all_dep)+1]] <- data.frame(
      threshold=tag, label=lab, n=nrow(df_dep),
      beta=cf["treated","Estimate"],
      se  =cf["treated","Std. Error"],
      pvalue=cf["treated","Pr(>|t|)"]
    )
  }
}

# ═════════════════════════════════════════════════════════════════════════════
# EXPORT RESULTS
# ═════════════════════════════════════════════════════════════════════════════
cat("\n", strrep("=", 60), "\n")
cat("RESULTS SUMMARY\n")
cat(strrep("=", 60), "\n")

add_stars <- function(df) {
  df %>% mutate(stars = case_when(
    pvalue < .001 ~ "***", pvalue < .01 ~ "**",
    pvalue < .05  ~ "*",   pvalue < .1  ~ ".",
    TRUE ~ ""))
}

if (length(all_did) > 0) {
  did_tbl <- bind_rows(all_did) %>% add_stars()
  write_csv(did_tbl, "results/did_2015_simple.csv")
  cat("\nSIMPLE DiD (ATT post-2015):\n")
  print(as.data.frame(did_tbl %>%
    select(threshold, outcome, att, se, pvalue, stars)))
}

if (length(all_pre) > 0) {
  pre_tbl <- bind_rows(all_pre)
  write_csv(pre_tbl, "results/did_2015_pretrend.csv")
  cat("\nPRE-TREND F-TESTS:\n")
  print(as.data.frame(pre_tbl))
}

if (length(all_es) > 0) {
  es_tbl <- bind_rows(all_es) %>% add_stars()
  write_csv(es_tbl, "results/did_2015_eventstudy.csv")
}

if (length(all_dose) > 0) {
  dose_tbl <- bind_rows(all_dose) %>% add_stars()
  write_csv(dose_tbl, "results/did_2015_doseresponse.csv")
  cat("\nDOSE-RESPONSE (post-period mean β per threshold):\n")
  summary_dose <- dose_tbl %>% filter(year >= 2015) %>%
    group_by(threshold, outcome) %>%
    summarise(mean_beta=round(mean(beta_dose),4), .groups="drop")
  print(as.data.frame(summary_dose))
}

if (length(all_dep) > 0) {
  dep_tbl <- bind_rows(all_dep) %>% add_stars()
  write_csv(dep_tbl, "results/did_2015_depression.csv")
  cat("\nDEPRESSION 2019:\n")
  print(as.data.frame(dep_tbl))
}

# ═════════════════════════════════════════════════════════════════════════════
# FIGURES
# ═════════════════════════════════════════════════════════════════════════════
if (length(all_es) > 0) {
  es_tbl  <- bind_rows(all_es)
  ref_rows <- es_tbl %>% distinct(threshold, outcome, label) %>%
    mutate(event_time=-1, year=2014, estimate=0, se=0,
           ci_lo=0, ci_hi=0, pvalue=1, stars="")
  es_plot  <- bind_rows(es_tbl, ref_rows) %>%
    arrange(threshold, outcome, event_time) %>%
    filter(event_time %in% -4:4)

  thr_colors <- c(
    T1_moderate_1k   = "#d73027",
    T2_large_5k      = "#4575b4",
    T3_verylarge_25k = "#1a9850"
  )
  thr_labels <- c(
    T1_moderate_1k   = "T1 ≥1,000 ac",
    T2_large_5k      = "T2 ≥5,000 ac",
    T3_verylarge_25k = "T3 ≥25,000 ac"
  )

  for (oc in OUTCOMES) {
    oc_lab <- OUT_LABELS[match(oc, OUTCOMES)]
    dat    <- es_plot %>% filter(outcome == oc)
    if (nrow(dat) == 0) next

    g <- ggplot(dat, aes(x=event_time, y=estimate,
                          color=threshold, fill=threshold)) +
      geom_hline(yintercept=0, linetype="dashed", color="gray50", linewidth=0.5) +
      geom_vline(xintercept=-0.5, linetype="dotted", color="gray60", linewidth=0.4) +
      annotate("rect", xmin=-0.5, xmax=4.5, ymin=-Inf, ymax=Inf,
               fill="lightyellow", alpha=0.25) +
      geom_ribbon(aes(ymin=ci_lo, ymax=ci_hi), alpha=0.15, color=NA) +
      geom_line(linewidth=0.9) +
      geom_point(size=2.5, shape=21, stroke=0.6) +
      scale_x_continuous(
        breaks = -4:4,
        labels = c("-4","-3","-2","-1","0","+1","+2","+3","+4")) +
      scale_color_manual(values=thr_colors, labels=thr_labels) +
      scale_fill_manual( values=thr_colors, labels=thr_labels) +
      labs(
        title    = paste("Event Study (2015 Wildfire Cohort):", oc_lab),
        subtitle = paste("TWFE with county + year FE, SEs clustered by county\n",
                         "Reference year: 2014 (l = −1); Western US, pop ≥ 10k"),
        x     = "Years relative to 2015 wildfire",
        y     = paste("Coefficient —", oc_lab),
        color = "Fire-size threshold",
        fill  = "Fire-size threshold"
      ) +
      theme_bw(base_size=12) +
      theme(legend.position="bottom",
            panel.grid.minor=element_blank(),
            plot.title=element_text(face="bold", size=13))

    fname_fig <- paste0("figures/2015_eventstudy_", oc, ".png")
    ggsave(fname_fig, g, width=10, height=6, dpi=180)
    cat("Saved:", fname_fig, "\n")
  }

  # Combined 2-panel figure (suicide + overdose side-by-side)
  dat_both <- es_plot %>%
    mutate(outcome_label = ifelse(outcome=="ihs_suicide_rate",
                                  "IHS Suicide Rate", "IHS Overdose Rate"))
  g2 <- ggplot(dat_both, aes(x=event_time, y=estimate,
                               color=threshold, fill=threshold)) +
    geom_hline(yintercept=0, linetype="dashed", color="gray50", linewidth=0.4) +
    geom_vline(xintercept=-0.5, linetype="dotted", color="gray60", linewidth=0.3) +
    annotate("rect", xmin=-0.5, xmax=4.5, ymin=-Inf, ymax=Inf,
             fill="lightyellow", alpha=0.20) +
    geom_ribbon(aes(ymin=ci_lo, ymax=ci_hi), alpha=0.12, color=NA) +
    geom_line(linewidth=0.85) +
    geom_point(size=2.2, shape=21, stroke=0.5) +
    facet_wrap(~outcome_label, scales="free_y") +
    scale_x_continuous(breaks=-4:4,
                       labels=c("-4","-3","-2","-1","0","+1","+2","+3","+4")) +
    scale_color_manual(values=thr_colors, labels=thr_labels) +
    scale_fill_manual( values=thr_colors, labels=thr_labels) +
    labs(
      title    = "2015 Wildfire Impacts on Mental Health Outcomes",
      subtitle = "TWFE event study | Western US counties | Reference: 2014",
      x     = "Years relative to 2015 wildfire",
      y     = "TWFE coefficient",
      color = "Fire-size threshold",
      fill  = "Fire-size threshold"
    ) +
    theme_bw(base_size=11) +
    theme(legend.position="bottom",
          panel.grid.minor=element_blank(),
          strip.text=element_text(face="bold"),
          plot.title=element_text(face="bold", size=13))

  ggsave("figures/2015_eventstudy_combined.png", g2,
         width=13, height=6, dpi=180)
  cat("Saved: figures/2015_eventstudy_combined.png\n")
}

cat("\nestimate_2015.R complete.\n")
