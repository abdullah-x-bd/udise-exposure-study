suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
})

# Final state-clustered RD estimates from FINAL_TIMING_AND_INCENTIVES_FINDINGS.md
# Outcome: jump in P(reported CSG receipt >= Rs 75,000) at the 250.5 pupil cutoff.
d <- tibble::tribble(
  ~cohort,   ~stage,          ~estimate, ~label,
  "2019–20", "GRANT YEAR\n+2",   0.00,     "≈0",
  "2019–20", "UDISE RECORD\n+3", 24.70,     "+24.7",
  "2020–21", "GRANT YEAR\n+2",   5.65,     "+5.7",
  "2020–21", "UDISE RECORD\n+3", 31.81,     "+31.8",
  "2021–22", "GRANT YEAR\n+2",   6.35,     "+6.4",
  "2021–22", "UDISE RECORD\n+3", 33.21,     "+33.2",
  "2022–23", "GRANT YEAR\n+2",   9.12,     "+9.1",
  "2022–23", "UDISE RECORD\n+3", 32.52,     "+32.5"
) %>%
  mutate(
    cohort = factor(cohort, levels = rev(c("2019–20", "2020–21", "2021–22", "2022–23"))),
    stage = factor(stage, levels = c("GRANT YEAR\n+2", "UDISE RECORD\n+3")),
    text_colour = if_else(estimate >= 18, "white", "#111111")
  )

ink <- "#111111"
muted <- "#687078"
light <- "#F3F4F5"
accent <- "#C75B00"

p <- ggplot(d, aes(stage, cohort, fill = estimate)) +
  geom_tile(width = 0.76, height = 0.72, colour = "white", linewidth = 4.5) +
  geom_text(aes(label = label, colour = text_colour),
            size = 9.7, fontface = "bold", show.legend = FALSE) +
  scale_colour_identity() +
  scale_fill_gradient(low = light, high = accent, limits = c(0, 35), guide = "none") +
  scale_x_discrete(position = "top", expand = expansion(add = c(0.50, 0.50))) +
  scale_y_discrete(expand = expansion(add = c(0.42, 0.42))) +
  coord_cartesian(clip = "off") +
  labs(
    title = "THE GRANT SIGNAL APPEARS AT +3",
    subtitle = "250 → 251 pupils moves the statutory CSG band ₹50,000 → ₹75,000\nJump in the chance UDISE records receipt ≥ ₹75,000, percentage points",
    x = NULL,
    y = NULL
  ) +
  theme_void(base_family = "sans") +
  theme(
    plot.title = element_text(size = 27, face = "bold", colour = ink,
                              hjust = 0, margin = margin(b = 9)),
    plot.subtitle = element_text(size = 12.5, colour = ink,
                                 hjust = 0, lineheight = 1.25, margin = margin(b = 24)),
    axis.text.x = element_text(size = 15.5, face = "bold", colour = ink,
                               lineheight = 1.0, margin = margin(b = 14)),
    axis.text.y = element_text(size = 15.5, face = "bold", colour = ink,
                               margin = margin(r = 22)),
    plot.margin = margin(36, 42, 34, 42)
  )

# One sentence that explains the extra reporting round.
p <- p +
  annotate("segment", x = 1.18, xend = 1.82, y = 4.72, yend = 4.72,
           linewidth = 0.85, colour = muted,
           arrow = arrow(length = unit(0.14, "inches"), type = "closed")) +
  annotate("text", x = 1.50, y = 4.93,
           label = "UDISE reports the previous financial year",
           size = 4.1, colour = muted, fontface = "bold")

out_dir <- "studies/composite_school_grant/figures/rendered"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

ggsave(file.path(out_dir, "csg_policy_prism_R.png"), p,
       width = 10.6, height = 7.8, units = "in", dpi = 320, bg = "white")
ggsave(file.path(out_dir, "csg_policy_prism_R.svg"), p,
       width = 10.6, height = 7.8, units = "in", bg = "white")
ggsave(file.path(out_dir, "csg_policy_prism_R.pdf"), p,
       width = 10.6, height = 7.8, units = "in", bg = "white")
