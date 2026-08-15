suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(scales)
})

# Final study values from FINAL_FULL_RESEARCH_PROGRAM_RESULTS.md
state <- tibble::tribble(
  ~state, ~first_stage,
  "Chhattisgarh", 67.1,
  "Uttar Pradesh", 66.7,
  "Delhi", 65.7,
  "Haryana", 55.3,
  "Gujarat", 46.0,
  "Jammu & Kashmir", 44.8,
  "Jharkhand", 33.8,
  "Rajasthan", 26.9,
  "Assam", 26.1,
  "Tamil Nadu", 25.7,
  "Tripura", 19.4,
  "Bihar", 18.9,
  "Madhya Pradesh", 17.0,
  "Andhra Pradesh", 14.8,
  "West Bengal", 13.5,
  "Kerala", 12.6,
  "Karnataka", 8.1,
  "Odisha", 7.9,
  "Punjab", 7.7,
  "Maharashtra", 7.6,
  "Uttarakhand", 6.1,
  "Telangana", 2.0,
  "Himachal Pradesh", -0.3
)

national <- tibble::tibble(
  cohort = c("2019–20", "2020–21", "2021–22", "2022–23"),
  estimate = c(24.70, 31.81, 33.21, 32.52)
)

# The visual uses a single grammar: one exact statutory rule enters the
# administrative system and fans into the state-level UDISE fingerprints.
# Left-side vertical position is schematic because rupees and percentage points
# are different units. The right-side scale is quantitative.

# deterministic offsets so close state estimates remain visible
state <- state %>%
  arrange(first_stage) %>%
  mutate(
    y = pmax(first_stage, 0),
    x_end = 8.45 + rep(c(-0.06, 0, 0.06), length.out = n()),
    label = if_else(state %in% c("Chhattisgarh", "Uttar Pradesh", "Delhi", "Himachal Pradesh", "Telangana"), state, NA_character_)
  )

# Core palette
ink <- "#111111"
muted <- "#A7B0B7"
rule_lo <- "#1F77B4"
rule_hi <- "#2CA02C"
accent <- "#D97706"
shadow <- "#DCE8F1"

p <- ggplot() +
  # --- Statutory rule, one-pupil cliff ---
  annotate("segment", x = 0.65, xend = 2.2, y = 18, yend = 18,
           linewidth = 2.0, colour = rule_lo, lineend = "round") +
  annotate("segment", x = 2.2, xend = 2.2, y = 18, yend = 48,
           linewidth = 2.0, colour = accent, lineend = "round") +
  annotate("segment", x = 2.2, xend = 3.6, y = 48, yend = 48,
           linewidth = 2.0, colour = rule_hi, lineend = "round") +

  annotate("text", x = 0.65, y = 23.5, label = "₹50,000",
           hjust = 0, size = 6.3, fontface = "bold", colour = ink) +
  annotate("text", x = 2.38, y = 53.0, label = "₹75,000",
           hjust = 0, size = 6.3, fontface = "bold", colour = ink) +
  annotate("text", x = 1.45, y = 11.5, label = "250 pupils",
           size = 4.3, fontface = "bold", colour = ink) +
  annotate("text", x = 2.95, y = 58.2, label = "251 pupils",
           size = 4.3, fontface = "bold", colour = ink) +
  annotate("text", x = 2.42, y = 33, label = "+₹25,000",
           hjust = 0, size = 5.2, fontface = "bold", colour = accent) +
  annotate("text", x = 0.65, y = 69, label = "THE RULE",
           hjust = 0, size = 4.2, fontface = "bold", colour = ink) +
  annotate("text", x = 0.65, y = 64.3, label = "one pupil changes the statutory band",
           hjust = 0, size = 3.9, colour = ink) +

  # --- Administrative delay ---
  annotate("segment", x = 3.9, xend = 5.25, y = 35, yend = 35,
           linewidth = 1.1, colour = muted,
           arrow = arrow(length = unit(0.17, "inches"), type = "closed")) +
  annotate("text", x = 4.58, y = 43.5, label = "+3 UDISE rounds",
           size = 5.5, fontface = "bold", colour = ink) +
  annotate("text", x = 4.58, y = 39.1, label = "allocation + reporting",
           size = 3.7, colour = ink) +

  # --- The fan: one rule becomes many recorded fingerprints ---
  geom_curve(
    data = state,
    aes(x = 5.4, y = 35, xend = x_end, yend = y),
    curvature = 0.14,
    linewidth = 0.42,
    colour = muted,
    alpha = 0.55
  ) +

  # National four-cohort envelope: 24.7 to 33.2 pp
  annotate("rect", xmin = 7.92, xmax = 8.98,
           ymin = min(national$estimate), ymax = max(national$estimate),
           fill = accent, alpha = 0.20, colour = NA) +
  geom_point(
    data = national,
    aes(x = 8.45, y = estimate),
    shape = 23, size = 4.0, fill = accent, colour = accent
  ) +

  # State fingerprints
  geom_point(
    data = state,
    aes(x = x_end, y = y),
    size = 2.0, colour = ink, alpha = 0.80
  ) +

  # Quantitative state range guide
  annotate("segment", x = 9.65, xend = 9.65, y = 0, yend = 67.1,
           linewidth = 0.55, colour = ink) +
  annotate("segment", x = 9.57, xend = 9.73, y = 67.1, yend = 67.1,
           linewidth = 0.55, colour = ink) +
  annotate("segment", x = 9.57, xend = 9.73, y = 0, yend = 0,
           linewidth = 0.55, colour = ink) +
  annotate("text", x = 9.82, y = 67.1, label = "≈67 pp",
           hjust = 0, size = 4.2, fontface = "bold") +
  annotate("text", x = 9.82, y = 0, label = "≈0 pp",
           hjust = 0, size = 4.2, fontface = "bold") +

  # Right-side explanation, tied directly to quantitative marks
  annotate("text", x = 7.45, y = 73.0, label = "WHAT UDISE RECORDS",
           hjust = 0, size = 4.2, fontface = "bold", colour = ink) +
  annotate("text", x = 8.45, y = 40.5, label = "+25 to +33 pp",
           size = 6.0, fontface = "bold", colour = accent) +
  annotate("text", x = 8.45, y = 36.0,
           label = "national jump in the chance\nUDISE records ≥ ₹75k",
           size = 3.7, colour = ink) +
  annotate("text", x = 9.83, y = 34,
           label = "state\nrange",
           hjust = 0, size = 3.5, colour = ink) +

  # Selected state labels only, to prove the fan is real data without clutter
  geom_text(
    data = state %>% filter(!is.na(label)),
    aes(x = x_end + 0.11, y = y, label = label),
    hjust = 0, size = 3.0, colour = ink, check_overlap = TRUE
  ) +

  # Conclusion
  annotate("text", x = 0.65, y = -13.0,
           label = "Exact in law.  Delayed, incomplete, and state-dependent in the record.",
           hjust = 0, size = 6.7, fontface = "bold", colour = ink) +
  annotate("text", x = 0.65, y = -20.0,
           label = "Final four-cohort UDISE analysis at the 250/251 pupil cutoff.",
           hjust = 0, size = 3.5, colour = ink) +

  coord_cartesian(xlim = c(0.4, 10.8), ylim = c(-22, 78), clip = "off") +
  labs(
    title = "A SHARP RULE BECOMES A FAN OF ADMINISTRATIVE OUTCOMES",
    subtitle = "India’s Composite School Grant is deterministic on paper. Its UDISE fingerprint is neither immediate nor uniform."
  ) +
  theme_void(base_family = "sans") +
  theme(
    plot.title = element_text(size = 24, face = "bold", colour = ink, hjust = 0, margin = margin(b = 6)),
    plot.subtitle = element_text(size = 11.5, colour = ink, hjust = 0, margin = margin(b = 20)),
    plot.margin = margin(24, 34, 24, 28)
  )

out_dir <- "studies/composite_school_grant/figures/rendered"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

ggsave(file.path(out_dir, "csg_policy_prism_R.png"), p,
       width = 15.5, height = 8.5, units = "in", dpi = 320, bg = "white")
ggsave(file.path(out_dir, "csg_policy_prism_R.svg"), p,
       width = 15.5, height = 8.5, units = "in", bg = "white")
ggsave(file.path(out_dir, "csg_policy_prism_R.pdf"), p,
       width = 15.5, height = 8.5, units = "in", bg = "white")
