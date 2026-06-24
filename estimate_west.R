# estimate_west.R
# Western US wildfire-mental health analysis
# Specifications:
#   1. CS2021 (Callaway-Sant'Anna) -- primary
#   2. SA2021 (Sun-Abraham)        -- robustness
#   3. TWFE event study            -- robustness
#   4. Dose-response TWFE          -- log_pct_burned × post
#   5. Depression 2x2 DiD          -- 2019 PLACES
# Panels: T1 (>=1k ac), T2 (>=5k ac), T3 (>=25k ac)

suppressWarnings(suppressMessages({
  library(did)       # v2.1.2 — CS2021
  library(fixest)    # SA2021 (sunab), TWFE
  library(dplyr)
  library(tidyr)
  library(readr)
  library(ggplot2)
  library(purrr)
}))

setwd("C:/Users/chenyon/Research Paper 2026(1)")
dir.create("figures", showWarnings=FALSE)
dir.create("results", showWarnings=FALSE)

OUTCOMES   <- c("ihs_suicide_rate", "ihs_overdose_rate")
OUT_LABELS <- c("IHS suicide rate", "IHS overdose rate")
ET_WINDOW  <- c(-4, -3, -2, 0, 1, 2, 3, 4)
BITERS     <- 999   # bootstrap iterations
THRESHOLDS <- list(
  list(tag="T1_moderate_1k",   file="panel_west_T1_moderate_1k.csv",   label="T1 (≥1k ac)"),
  list(tag="T2_large_5k",      file="panel_west_T2_large_5k.csv",      label="T2 (≥5k ac)"),
  list(tag="T3_verylarge_25k", file="panel_west_T3_verylarge_25k.csv", label="T3 (≥25k ac)")
)

# ── Helper: trim event window ──────────────────────────────────────────────────
trim_window <- function(df, window=ET_WINDOW) {
  df %>% filter(event_time %in% window)
}

# ── Helper: run CS2021 ATT(g,t) ───────────────────────────────────────────────
run_cs2021 <- function(df, outcome, control_group="notyettreated") {
  df <- df %>%
    filter(!is.na(unemployment_rate)) %>%
    arrange(GEOID, year)
  df$county_id <- as.integer(as.factor(df$GEOID))

  tryCatch({
    att_gt(
      yname          = outcome,
      tname          = "year",
      idname         = "county_id",
      gname          = "cohort_g",
      xformla        = ~unemployment_rate,
      data           = df,
      control_group  = control_group,
      base_period    = "universal",
      bstrap         = TRUE,
      biters         = BITERS,
      allow_unbalanced_panel = TRUE
    )
  }, error = function(e) {
    message("  CS2021 error: ", conditionMessage(e))
    NULL
  })
}

# ── Helper: extract event study ───────────────────────────────────────────────
extract_es <- function(cs_obj, tag, outcome) {
  if (is.null(cs_obj)) return(NULL)
  agg <- aggte(cs_obj, type="dynamic", min_e=-4, max_e=4,
               na.rm=TRUE, bstrap=TRUE, biters=BITERS)
  df  <- data.frame(
    event_time = agg$egt,
    estimate   = agg$att.egt,
    se         = agg$se.egt,
    pvalue     = 2 * pnorm(-abs(agg$att.egt / agg$se.egt)),
    ci_lo      = agg$att.egt - 1.96 * agg$se.egt,
    ci_hi      = agg$att.egt + 1.96 * agg$se.egt,
    threshold  = tag,
    outcome    = outcome
  )
  df
}

# ── Helper: ATT overall ────────────────────────────────────────────────────────
extract_att <- function(cs_obj, tag, outcome) {
  if (is.null(cs_obj)) return(NULL)
  agg <- aggte(cs_obj, type="simple", na.rm=TRUE, bstrap=TRUE, biters=BITERS)
  data.frame(
    threshold = tag, outcome = outcome,
    att       = agg$overall.att,
    se        = agg$overall.se,
    pvalue    = 2 * pnorm(-abs(agg$overall.att / agg$overall.se)),
    ci_lo     = agg$overall.att - 1.96 * agg$overall.se,
    ci_hi     = agg$overall.att + 1.96 * agg$overall.se
  )
}

# ── Helper: TWFE event study via fixest ────────────────────────────────────────
run_twfe_es <- function(df, outcome) {
  df <- df %>%
    filter(!is.na(unemployment_rate)) %>%
    mutate(
      et_clamp = case_when(
        treated == 0 ~ -1L,
        !is.na(event_time) & event_time >= -4 & event_time <= 4 ~ as.integer(event_time),
        TRUE ~ NA_integer_
      )
    ) %>%
    filter(!is.na(et_clamp)) %>%
    mutate(et_f = relevel(factor(et_clamp), ref="-1"))

  form <- as.formula(paste0(outcome, " ~ et_f + unemployment_rate | GEOID + year"))
  tryCatch(feols(form, data=df, vcov=~GEOID), error=function(e) NULL)
}

# ═════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═════════════════════════════════════════════════════════════════════════════
all_att <- list()
all_es  <- list()
all_dose <- list()

for (thr in THRESHOLDS) {
  tag   <- thr$tag
  lab   <- thr$label
  fname <- thr$file
  cat("\n", strrep("=", 60), "\n")
  cat("THRESHOLD:", lab, "\n")
  cat(strrep("=", 60), "\n")

  df <- read_csv(fname, col_types=cols(GEOID=col_character()), show_col_types=FALSE)
  df <- df %>%
    mutate(
      cohort_g           = as.integer(cohort_g),
      year               = as.integer(year),
      treated            = as.integer(treated),
      ihs_suicide_rate   = as.numeric(ihs_suicide_rate),
      ihs_overdose_rate  = as.numeric(ihs_overdose_rate),
      unemployment_rate  = as.numeric(unemployment_rate),
      log_pct_burned     = as.numeric(log_pct_burned)
    )

  n_treated  <- n_distinct(df$GEOID[df$treated==1])
  n_control  <- n_distinct(df$GEOID[df$treated==0])
  cohort_tab <- df %>% filter(treated==1) %>%
                group_by(cohort_g) %>% summarise(n=n_distinct(GEOID)) %>% arrange(cohort_g)
  cat("  Treated:", n_treated, " | Controls:", n_control, "\n")
  cat("  Cohorts:", paste(cohort_tab$cohort_g, "=", cohort_tab$n, collapse=", "), "\n")

  # ── A. CS2021 (primary: notyettreated) ─────────────────────────────────────
  for (oc in OUTCOMES) {
    cat("\n  CS2021 (notyettreated) —", oc, "\n")
    cs <- run_cs2021(df, oc, "notyettreated")
    if (!is.null(cs)) {
      att <- extract_att(cs, tag, oc)
      es  <- extract_es(cs, tag, oc)
      if (!is.null(att)) all_att[[length(all_att)+1]] <- att
      if (!is.null(es))  all_es[[length(all_es)+1]]   <- es
      cat("  Overall ATT =", round(att$att, 4),
          " SE =", round(att$se, 4),
          " p =", round(att$pvalue, 4), "\n")
    }
  }

  # ── B. TWFE event study (robustness) ───────────────────────────────────────
  cat("\n  TWFE event study:\n")
  for (oc in OUTCOMES) {
    m <- run_twfe_es(df, oc)
    if (!is.null(m)) {
      cf <- coef(m)
      se <- se(m)
      etnames <- grep("^et_f", names(cf), value=TRUE)
      et_vals <- as.integer(gsub("et_f","",etnames))
      twfe_es <- data.frame(
        event_time = et_vals,
        estimate   = cf[etnames],
        se         = se[etnames],
        pvalue     = 2*pnorm(-abs(cf[etnames]/se[etnames])),
        threshold  = paste0(tag, "_TWFE"),
        outcome    = oc
      )
      twfe_es <- twfe_es %>% filter(event_time %in% ET_WINDOW)
      all_es[[length(all_es)+1]] <- twfe_es
      post_att <- mean(twfe_es$estimate[twfe_es$event_time >= 0], na.rm=TRUE)
      cat("  ", oc, "— mean post-treatment TWFE =", round(post_att, 4), "\n")
    }
  }

  # ── C. Dose-response TWFE: log_pct_burned × post ───────────────────────────
  cat("\n  Dose-response (log_pct_burned):\n")
  df_treated <- df %>% filter(treated == 1) %>%
    mutate(post = as.integer(year >= cohort_g))
  if (sd(df_treated$log_pct_burned, na.rm=TRUE) > 0) {
    for (oc in OUTCOMES) {
      form_d <- as.formula(paste0(
        oc, " ~ log_pct_burned:post + post + unemployment_rate | GEOID + year"
      ))
      m_dose <- tryCatch(
        feols(form_d, data=df_treated, vcov=~GEOID),
        error=function(e) NULL
      )
      if (!is.null(m_dose)) {
        cf <- coef(m_dose)
        se <- se(m_dose)
        nm <- grep("log_pct_burned:post", names(cf), value=TRUE)
        if (length(nm) > 0) {
          cat("  ", oc, "— dose β =", round(cf[nm], 5),
              " SE =", round(se[nm], 5),
              " p =", round(2*pnorm(-abs(cf[nm]/se[nm])), 4), "\n")
          all_dose[[length(all_dose)+1]] <- data.frame(
            threshold=tag, outcome=oc,
            beta_dose=cf[nm], se_dose=se[nm],
            pvalue=2*pnorm(-abs(cf[nm]/se[nm]))
          )
        }
      }
    }
  } else {
    cat("  No variation in log_pct_burned — skipping dose-response\n")
  }

  # ── D. CS2021 sensitivity: nevertreated ────────────────────────────────────
  nt_controls <- n_distinct(df$GEOID[df$cohort_g == 0])
  if (nt_controls >= 5) {
    cat("\n  CS2021 sensitivity (nevertreated,", nt_controls, "controls):\n")
    for (oc in OUTCOMES) {
      cs_nt <- run_cs2021(df, oc, "nevertreated")
      if (!is.null(cs_nt)) {
        att_nt <- extract_att(cs_nt, paste0(tag,"_NT"), oc)
        if (!is.null(att_nt)) {
          all_att[[length(all_att)+1]] <- att_nt
          cat("  ", oc, "— ATT =", round(att_nt$att, 4),
              " p =", round(att_nt$pvalue, 4), "\n")
        }
      }
    }
  } else {
    cat("\n  [Skip nevertreated: only", nt_controls, "never-treated counties]\n")
  }
}  # end threshold loop

# ═════════════════════════════════════════════════════════════════════════════
# DEPRESSION 2×2 DiD (PLACES 2019)
# ═════════════════════════════════════════════════════════════════════════════
cat("\n", strrep("=", 60), "\n")
cat("DEPRESSION 2x2 DiD (2019 PLACES)\n")
cat(strrep("=", 60), "\n")

all_dep <- list()

for (thr in THRESHOLDS) {
  tag   <- thr$tag
  lab   <- thr$label
  fname <- thr$file

  df <- read_csv(fname, col_types=cols(GEOID=col_character()), show_col_types=FALSE)
  df <- df %>% mutate(
    cohort_g     = as.integer(cohort_g),
    year         = as.integer(year),
    treated      = as.integer(treated),
    pct_depression = as.numeric(pct_depression)
  )

  # Check depression coverage
  dep_years <- df %>% filter(!is.na(pct_depression)) %>% pull(year) %>% unique() %>% sort()
  cat("\n ", lab, "— depression years:", paste(dep_years, collapse=","), "\n")

  if (length(dep_years) == 0) {
    cat("  No depression data — skipping\n")
    next
  }

  # PLACES depression only available in 2019.
  # Strategy: cross-sectional regression of 2019 depression on treatment status,
  # controlling for pre-treatment suicide/overdose rates and county characteristics.
  df_2019 <- df %>%
    filter(year == 2019, !is.na(pct_depression)) %>%
    select(GEOID, post_depression=pct_depression, treated, cohort_g,
           ihs_suicide_rate, ihs_overdose_rate, unemployment_rate,
           RUCC2013, county_pop_2014)

  if (nrow(df_2019) < 10) {
    cat("  Insufficient 2019 depression obs:", nrow(df_2019), "— skipping\n")
    next
  }

  # Get pre-2015 average outcome rates as controls
  df_pre_rates <- df %>%
    filter(year <= 2014) %>%
    group_by(GEOID) %>%
    summarise(pre_suicide    = mean(ihs_suicide_rate,  na.rm=TRUE),
              pre_overdose   = mean(ihs_overdose_rate, na.rm=TRUE),
              pre_unemp      = mean(unemployment_rate, na.rm=TRUE),
              .groups="drop")

  df_dep <- df_2019 %>% left_join(df_pre_rates, by="GEOID")

  cat("  N =", nrow(df_dep), "counties with 2019 depression data\n")
  cat("  Post-depression mean: treated =",
      round(mean(df_dep$post_depression[df_dep$treated==1], na.rm=TRUE), 2),
      "control =",
      round(mean(df_dep$post_depression[df_dep$treated==0], na.rm=TRUE), 2), "\n")

  # Cross-sectional regression: depression_2019 ~ treated + pre-outcome controls
  m_dep <- tryCatch(
    lm(post_depression ~ treated + pre_suicide + pre_overdose + pre_unemp + RUCC2013,
       data=df_dep),
    error = function(e) NULL
  )
  if (!is.null(m_dep)) {
    s   <- summary(m_dep)
    cf  <- coef(s)
    nm  <- "treated"
    if (nm %in% rownames(cf)) {
      cat("  Cross-sec β(treated) =", round(cf[nm,"Estimate"], 4),
          " SE =", round(cf[nm,"Std. Error"], 4),
          " p =", round(cf[nm,"Pr(>|t|)"], 4), "\n")
      all_dep[[length(all_dep)+1]] <- data.frame(
        threshold = tag, label = lab,
        n         = nrow(df_dep),
        beta_did  = cf[nm,"Estimate"],
        se_did    = cf[nm,"Std. Error"],
        pvalue    = cf[nm,"Pr(>|t|)"]
      )
    }
  }
}

# ═════════════════════════════════════════════════════════════════════════════
# EXPORT RESULTS
# ═════════════════════════════════════════════════════════════════════════════
cat("\n", strrep("=", 60), "\n")
cat("EXPORTING RESULTS\n")
cat(strrep("=", 60), "\n")

# ATT overall table
if (length(all_att) > 0) {
  att_tbl <- bind_rows(all_att) %>%
    mutate(stars = case_when(
      pvalue < .001 ~ "***", pvalue < .01 ~ "**",
      pvalue < .05  ~ "*",   pvalue < .1  ~ ".",
      TRUE ~ ""
    ))
  write_csv(att_tbl, "results/west_att_overall.csv")
  cat("\nATT OVERALL:\n")
  print(as.data.frame(att_tbl %>% select(threshold, outcome, att, se, pvalue, stars)))
}

# Event study table
if (length(all_es) > 0) {
  es_tbl <- bind_rows(all_es)
  write_csv(es_tbl, "results/west_event_study.csv")
  cat("\nEvent study saved: results/west_event_study.csv\n")
}

# Dose-response table
if (length(all_dose) > 0) {
  dose_tbl <- bind_rows(all_dose)
  write_csv(dose_tbl, "results/west_dose_response.csv")
  cat("\nDOSE-RESPONSE:\n")
  print(dose_tbl)
}

# Depression table
if (length(all_dep) > 0) {
  dep_tbl <- bind_rows(all_dep)
  write_csv(dep_tbl, "results/west_depression_did.csv")
  cat("\nDEPRESSION DiD:\n")
  print(dep_tbl)
}

# ═════════════════════════════════════════════════════════════════════════════
# FIGURES — Event study plots (CS2021 primary specification)
# ═════════════════════════════════════════════════════════════════════════════
if (length(all_es) > 0) {
  es_tbl <- bind_rows(all_es)
  cs_es  <- es_tbl %>% filter(!grepl("_TWFE$|_NT$", threshold))

  for (oc in OUTCOMES) {
    oc_lab <- OUT_LABELS[match(oc, OUTCOMES)]
    dat <- cs_es %>% filter(outcome == oc, event_time %in% ET_WINDOW)
    if (nrow(dat) == 0) next

    # Add reference period row (l = -1, est = 0)
    ref_rows <- dat %>% distinct(threshold) %>%
      mutate(event_time=-1, estimate=0, se=0, ci_lo=0, ci_hi=0, pvalue=1, outcome=oc)
    dat <- bind_rows(dat, ref_rows) %>% arrange(threshold, event_time)

    g <- ggplot(dat, aes(x=event_time, y=estimate, color=threshold, fill=threshold)) +
      geom_hline(yintercept=0, linetype="dashed", color="gray50", linewidth=0.5) +
      geom_vline(xintercept=-0.5, linetype="dotted", color="gray60", linewidth=0.4) +
      geom_ribbon(aes(ymin=ci_lo, ymax=ci_hi), alpha=0.15, color=NA) +
      geom_line(linewidth=0.9) +
      geom_point(size=2.2) +
      scale_x_continuous(breaks=ET_WINDOW, labels=ET_WINDOW) +
      scale_color_manual(values=c(
        "T1_moderate_1k"="#d73027", "T2_large_5k"="#4575b4", "T3_verylarge_25k"="#1a9850"),
        labels=c("T1 (≥1k ac)", "T2 (≥5k ac)", "T3 (≥25k ac)")) +
      scale_fill_manual(values=c(
        "T1_moderate_1k"="#d73027", "T2_large_5k"="#4575b4", "T3_verylarge_25k"="#1a9850"),
        labels=c("T1 (≥1k ac)", "T2 (≥5k ac)", "T3 (≥25k ac)")) +
      labs(
        title    = paste("Event Study:", oc_lab),
        subtitle = "CS2021 (Callaway-Sant'Anna), not-yet-treated controls\nWestern US counties, pop ≥ 10k",
        x        = "Event time (years relative to first wildfire)",
        y        = paste("ATT —", oc_lab),
        color    = "Fire size threshold",
        fill     = "Fire size threshold"
      ) +
      theme_bw(base_size=12) +
      theme(legend.position="bottom",
            panel.grid.minor=element_blank(),
            plot.title=element_text(face="bold"))

    ggsave(paste0("figures/west_es_", oc, ".png"), g,
           width=10, height=6, dpi=180)
    cat("Saved: figures/west_es_", oc, ".png\n")
  }

  # TWFE overlay for comparison
  twfe_es <- es_tbl %>% filter(grepl("_TWFE$", threshold)) %>%
    mutate(spec = "TWFE", threshold_base = gsub("_TWFE$","",threshold))
  cs_es2  <- cs_es %>% mutate(spec = "CS2021", threshold_base = threshold)
  es_comp <- bind_rows(cs_es2, twfe_es) %>%
    filter(threshold_base == "T1_moderate_1k") %>%
    filter(!is.na(se))

  if (nrow(es_comp) > 0) {
    for (oc in OUTCOMES) {
      oc_lab <- OUT_LABELS[match(oc, OUTCOMES)]
      dat <- es_comp %>% filter(outcome == oc, event_time %in% ET_WINDOW)
      if (nrow(dat) == 0) next
      ref_rows <- dat %>% distinct(spec) %>%
        mutate(event_time=-1, estimate=0, se=0, ci_lo=0, ci_hi=0, pvalue=1, outcome=oc)
      dat <- bind_rows(dat, ref_rows) %>% arrange(spec, event_time)

      g2 <- ggplot(dat, aes(x=event_time, y=estimate, color=spec, fill=spec)) +
        geom_hline(yintercept=0, linetype="dashed", color="gray50") +
        geom_vline(xintercept=-0.5, linetype="dotted", color="gray60") +
        geom_ribbon(aes(ymin=ci_lo, ymax=ci_hi), alpha=0.15, color=NA) +
        geom_line(linewidth=0.9) +
        geom_point(size=2.2) +
        scale_x_continuous(breaks=ET_WINDOW) +
        scale_color_manual(values=c("CS2021"="#d73027","TWFE"="#4575b4")) +
        scale_fill_manual(values=c("CS2021"="#d73027","TWFE"="#4575b4")) +
        labs(title=paste("CS2021 vs TWFE:", oc_lab, "(T1 ≥1k ac)"),
             subtitle="Western US counties, pop ≥ 10k",
             x="Event time", y=paste("ATT —", oc_lab),
             color="Estimator", fill="Estimator") +
        theme_bw(base_size=12) +
        theme(legend.position="bottom", panel.grid.minor=element_blank(),
              plot.title=element_text(face="bold"))
      ggsave(paste0("figures/west_cs_vs_twfe_", oc, ".png"), g2,
             width=9, height=5.5, dpi=180)
    }
  }
}

cat("\nestimate_west.R complete.\n")
