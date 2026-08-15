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
    label = sprintf("%.1f", observed)
  )

ink <- "#111111"
muted <- "#B6BBC0"
soft <- "#F2F3F4"
accent <- "#C75B00"
accent_soft <- "#F1D6C3"

p <- ggplot(d, aes(y = cohort)) +
  # The repeated ~30 pp observed region
  annotate("rect", xmin = 24, xmax = 34, ymin = 0.5, ymax = 4.5,
           fill = accent_soft, alpha = 0.45) +

  # Gap from what is observed to the mechanical-record benchmark
  geom_segment(aes(x = observed, xend = benchmark, yend = cohort),
               linewidth = 3.0, colour = soft, lineend = "round") +

  # Observed discontinuities
  geom_point(aes(x = observed), size = 9.5, colour = accent) +
  geom_text(aes(x = observed, label = label),
            colour = "white", fontface = "bold", size = 5.3) +

  # Mechanical-record benchmark
  geom_point(aes(x = benchmark), shape = 21, size = 9.5,
             stroke = 1.5, fill = "white", colour = ink) +
  geom_vline(xintercept = 100, linewidth = 0.8, linetype = "dashed", colour = muted) +

  # Direct labels, no legend required
  annotate("text", x = 29, y = 4.52,
           label = "WHAT UDISE SHOWS",
           hjust = 0.5, vjust = -0.2, size = 5.1, fontface = "bold", colour = accent) +
  annotate("text", x = 100, y = 4.52,
           label = "MECHANICAL-RECORD\nBENCHMARK",
           hjust = 0.5, vjust = -0.2, size = 4.7, fontface = "bold", colour = ink, lineheight = 0.95) +

  # The gap itself is the result
  annotate("text", x = 66, y = 2.5,
           label = "≈70 pp not reflected\nin this UDISE indicator",
           size = 6.0, fontface = "bold", colour = muted, lineheight = 0.95) +

  scale_x_continuous(
    limits = c(0, 106),
    breaks = c(0, 25, 50, 75, 100),
    labels = function(x) paste0(x, " pp"),
    expand = c(0, 0)
  ) +
  scale_y_discrete(expand = expansion(add = c(0.45, 0.65))) +
  labs(
    title = "THE RULE IS SHARP. THE RECORD IS NOT.",
    subtitle = "250 → 251 pupils moves the statutory CSG band ₹50,000 → ₹75,000.\nAfter the correct +3 reporting alignment, the recorded jump is still only about 25–33 percentage points.",
    x = NULL,
    y = NULL,
    caption = "Benchmark = a binary UDISE receipt indicator that mechanically mirrors the statutory band transition. It is not a grant-delivery compliance rate."
  ) +
  theme_minimal(base_family = "sans") +
  theme(
    panel.grid.major.y = element_blank(),
    panel.grid.minor = element_blank(),
    panel.grid.major.x = element_line(colour = "#ECEEEF", linewidth = 0.55),
    axis.text.x = element_text(size = 11.5, colour = "#666666", margin = margin(t = 10)),
    axis.text.y = element_text(size = 15, face = "bold", colour = ink, margin = margin(r = 18)),
    plot.title = element_text(size = 27, face = "bold", colour = ink, hjust = 0, margin = margin(b = 8)),
    plot.subtitle = element_text(size = 13, colour = ink, hjust = 0, lineheight = 1.22, margin = margin(b = 28)),
    plot.caption = element_text(size = 9.7, colour = "#686868", hjust = 0, margin = margin(t = 24)),
    plot.margin = margin(36, 46, 30, 42)
  )

out_dir <- "studies/composite_school_grant/figures/rendered"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

ggsave(file.path(out_dir, "csg_policy_prism_R.png"), p,
       width = 12.2, height = 7.7, units = "in", dpi = 320, bg = "white")
ggsave(file.path(out_dir, "csg_policy_prism_R.svg"), p,
       width = 12.2, height = 7.7, units = "in", bg = "white")
ggsave(file.path(out_dir, "csg_policy_prism_R.pdf"), p,
       width = 12.2, height = 7.7, units = "in", bg = "white")
