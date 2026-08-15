suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
})

# Final state-clustered RD estimates from FINAL_TIMING_AND_INCENTIVES_FINDINGS.md
# Outcome: jump in P(reported CSG receipt >= Rs 75,000) at the 250.5 pupil cutoff.
# The 100 pp endpoint is a mechanical binary-record benchmark: if the UDISE
# receipt indicator perfectly mirrored the statutory band transition around
# 250/251, the indicator would switch completely at the cutoff.
d <- tibble::tribble(
  ~cohort,   ~observed,
  "2019–20", 24.70,
  "2020–21", 31.81,
  "2021–22", 33.21,
  "2022–23", 32.52
) %>%
  mutate(
    cohort = factor(cohort, levels = rev(c("2019–20", "2020–21", "2021–22", "2022–23"))),
    benchmark = 100,
    gap = benchmark - observed,
    label = sprintf("%.1f pp", observed)
  )

ink <- "#111111"
muted <- "#B6BBC0"
soft <- "#F2F3F4"
accent <- "#C75B00"
accent_soft <- "#F1D6C3"

p <- ggplot(d, aes(y = cohort)) +
  # The repeated observed region
  annotate("rect", xmin = 24, xmax = 34, ymin = 0.5, ymax = 4.5,
           fill = accent_soft, alpha = 0.45) +

  # Gap from observed discontinuity to a mechanically faithful binary record
  geom_segment(aes(x = observed, xend = benchmark, yend = cohort),
               linewidth = 3.0, colour = soft, lineend = "round") +

  # Observed discontinuities
  geom_point(aes(x = observed), size = 6.4, colour = accent) +
  geom_text(aes(x = observed, label = label),
            nudge_y = 0.18, colour = accent, fontface = "bold", size = 4.4) +

  # Mechanical-record benchmark
  geom_point(aes(x = benchmark), shape = 21, size = 7.6,
             stroke = 1.45, fill = "white", colour = ink) +
  geom_vline(xintercept = 100, linewidth = 0.8, linetype = "dashed", colour = muted) +

  # Direct labels, no legend
  annotate("text", x = 29, y = 4.35,
           label = "OBSERVED IN UDISE",
           hjust = 0.5, size = 4.7, fontface = "bold", colour = accent) +
  annotate("text", x = 100, y = 4.35,
           label = "100 pp\nMECHANICAL BENCHMARK",
           hjust = 0.5, size = 4.25, fontface = "bold", colour = ink, lineheight = 0.95) +

  # The gap itself is the finding
  annotate("text", x = 66, y = 2.5,
           label = "≈70 pp of the mechanical signal\nis not reflected in this indicator",
           size = 5.5, fontface = "bold", colour = muted, lineheight = 0.95) +

  scale_x_continuous(
    limits = c(0, 106),
    breaks = c(0, 25, 50, 75, 100),
    labels = function(x) paste0(x, " pp"),
    expand = c(0, 0)
  ) +
  scale_y_discrete(expand = expansion(add = c(0.45, 0.78))) +
  labs(
    title = "THE RULE IS SHARP. THE RECORD IS NOT.",
    subtitle = "250 → 251 pupils moves the statutory CSG band ₹50,000 → ₹75,000.\nAt the correctly aligned +3 record, the discontinuity is still only 24.7–33.2 percentage points.",
    x = NULL,
    y = NULL,
    caption = "100 pp is a mechanical-record benchmark, not a grant-delivery compliance rate."
  ) +
  theme_minimal(base_family = "sans") +
  theme(
    panel.grid.major.y = element_blank(),
    panel.grid.minor = element_blank(),
    panel.grid.major.x = element_line(colour = "#ECEEEF", linewidth = 0.55),
    axis.text.x = element_text(size = 11.5, colour = "#666666", margin = margin(t = 10)),
    axis.text.y = element_text(size = 15, face = "bold", colour = ink, margin = margin(r = 18)),
    plot.title = element_text(size = 27, face = "bold", colour = ink, hjust = 0, margin = margin(b = 8)),
    plot.subtitle = element_text(size = 13, colour = ink, hjust = 0, lineheight = 1.22, margin = margin(b = 24)),
    plot.caption = element_text(size = 9.8, colour = "#686868", hjust = 0, margin = margin(t = 24)),
    plot.margin = margin(34, 46, 30, 42)
  )

out_dir <- "studies/composite_school_grant/figures/rendered"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

ggsave(file.path(out_dir, "csg_policy_prism_R.png"), p,
       width = 12.2, height = 7.7, units = "in", dpi = 320, bg = "white")
ggsave(file.path(out_dir, "csg_policy_prism_R.svg"), p,
       width = 12.2, height = 7.7, units = "in", bg = "white")
ggsave(file.path(out_dir, "csg_policy_prism_R.pdf"), p,
       width = 12.2, height = 7.7, units = "in", bg = "white")
