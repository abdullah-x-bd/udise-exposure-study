suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(tibble)
})

# Final correctly aligned multi-threshold CSG fingerprint from
# FINAL_FULL_RESEARCH_PROGRAM_RESULTS.md
# Each value is the discontinuity in P(UDISE reported receipt >= statutory target)
# at the relevant enrolment threshold, in percentage points.

d <- tribble(
  ~threshold, ~target, ~cohort,   ~jump,
  "30 → 31",   "₹25k",  "2019–20", 24.58,
  "30 → 31",   "₹25k",  "2020–21", 27.22,
  "30 → 31",   "₹25k",  "2021–22", 30.52,
  "30 → 31",   "₹25k",  "2022–23", 30.03,
  "100 → 101", "₹50k",  "2019–20", 34.27,
  "100 → 101", "₹50k",  "2020–21", 39.46,
  "100 → 101", "₹50k",  "2021–22", 40.51,
  "100 → 101", "₹50k",  "2022–23", 39.99,
  "250 → 251", "₹75k",  "2019–20", 25.21,
  "250 → 251", "₹75k",  "2020–21", 32.88,
  "250 → 251", "₹75k",  "2021–22", 33.46,
  "250 → 251", "₹75k",  "2022–23", 33.24,
  "1000 → 1001", "₹100k", "2019–20", 15.07,
  "1000 → 1001", "₹100k", "2020–21", 11.36,
  "1000 → 1001", "₹100k", "2021–22", 19.44,
  "1000 → 1001", "₹100k", "2022–23", 15.02
) %>%
  mutate(
    threshold_label = paste0(threshold, " pupils\nnew band: ", target),
    threshold_label = factor(
      threshold_label,
      levels = rev(c(
        "30 → 31 pupils\nnew band: ₹25k",
        "100 → 101 pupils\nnew band: ₹50k",
        "250 → 251 pupils\nnew band: ₹75k",
        "1000 → 1001 pupils\nnew band: ₹100k"
      ))
    ),
    cohort = factor(cohort, levels = c("2019–20", "2020–21", "2021–22", "2022–23")),
    label = sprintf("+%.1f", jump)
  )

# One visual grammar: the formula fingerprint itself.
# Darker circles = stronger formula transmission into the UDISE record.

p <- ggplot(d, aes(x = cohort, y = threshold_label)) +
  geom_tile(width = 0.93, height = 0.78, fill = "#F4F4F2", colour = "white", linewidth = 3) +
  geom_point(aes(size = jump, fill = jump), shape = 21, colour = "#202020", stroke = 0.7) +
  geom_text(aes(label = label), colour = "white", fontface = "bold", size = 5.4) +
  scale_size_continuous(range = c(13, 23), limits = c(10, 42), guide = "none") +
  scale_fill_gradient(low = "#8AA6B4", high = "#0F3B4C", limits = c(10, 42), guide = "none") +
  labs(
    title = "THE FORMULA LEAVES A REPEATED FISCAL FINGERPRINT",
    subtitle = "Cross four different statutory enrolment thresholds and UDISE repeatedly moves toward the new grant band.\nEach circle is the jump in the chance that the correctly aligned UDISE record reaches the statutory target.",
    x = "Assignment-enrolment cohort",
    y = NULL,
    caption = "Percentage-point discontinuities at the correctly reconstructed +3 reporting alignment. 250/251 remains the primary design; the other thresholds are formula-fingerprint tests."
  ) +
  theme_minimal(base_family = "sans", base_size = 13) +
  theme(
    panel.grid = element_blank(),
    axis.text.x = element_text(size = 13.5, face = "bold", colour = "#222222", margin = margin(t = 10)),
    axis.text.y = element_text(size = 13.5, face = "bold", colour = "#222222", lineheight = 1.05, margin = margin(r = 14)),
    axis.title.x = element_text(size = 11.5, colour = "#555555", margin = margin(t = 18)),
    plot.title = element_text(size = 25, face = "bold", colour = "#111111", margin = margin(b = 10)),
    plot.subtitle = element_text(size = 13.2, colour = "#222222", lineheight = 1.2, margin = margin(b = 22)),
    plot.caption = element_text(size = 9.8, colour = "#666666", hjust = 0, margin = margin(t = 18)),
    plot.margin = margin(32, 34, 28, 36)
  ) +
  coord_cartesian(clip = "off")

out_dir <- "studies/composite_school_grant/figures/rendered"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

ggsave(file.path(out_dir, "csg_formula_fingerprint_R.png"), p,
       width = 12.2, height = 7.8, units = "in", dpi = 320, bg = "white")
ggsave(file.path(out_dir, "csg_formula_fingerprint_R.svg"), p,
       width = 12.2, height = 7.8, units = "in", bg = "white")
