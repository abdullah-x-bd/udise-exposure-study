suppressPackageStartupMessages({
  library(ggplot2)
  library(dplyr)
  library(scales)
})

# Final state-clustered RD estimates from FINAL_TIMING_AND_INCENTIVES_FINDINGS.md
# Outcome: P(reported CSG receipt >= Rs 75,000) at the 250.5 pupil cutoff.
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
light <- "#F2F4F6"
accent <- "#C65D00"

p <- ggplot(d, aes(stage, cohort, fill = estimate)) +
  geom_tile(width = 0.72, height = 0.72, colour = "white", linewidth = 5) +
  geom_text(aes(label = label, colour = text_colour),
            size = 11.5, fontface = "bold", show.legend = FALSE) +
  scale_colour_identity() +
  scale_fill_gradient(
    low = light,
    high = accent,
    limits = c(0, 35),
    guide = "none"
  ) +
  scale_x_discrete(position = "top") +
  coord_fixed(ratio = 0.78, clip = "off") +
  labs(
    title = "THE ₹25,000 FUNDING CLIFF SHOWS UP ONE UDISE ROUND LATER",
    subtitle = "250 → 251 pupils raises the statutory CSG band from ₹50,000 → ₹75,000.\nEach tile is the jump in the chance that UDISE records receipt of at least ₹75,000.",
    x = NULL,
    y = "ENROLMENT VINTAGE"
  ) +
  theme_void(base_family = "sans") +
  theme(
    plot.title = element_text(size = 25, face = "bold", colour = ink,
                              hjust = 0, margin = margin(b = 10)),
    plot.subtitle = element_text(size = 12.2, colour = ink,
                                 hjust = 0, lineheight = 1.25, margin = margin(b = 26)),
    axis.text.x = element_text(size = 15, face = "bold", colour = ink,
                               lineheight = 1.05, margin = margin(b = 14)),
    axis.text.y = element_text(size = 15, face = "bold", colour = ink,
                               margin = margin(r = 18)),
    axis.title.y = element_text(size = 10.5, face = "bold", colour = "#5F6368",
                                angle = 90, margin = margin(r = 18)),
    plot.margin = margin(34, 55, 34, 45)
  )

# One direct explanatory annotation, not a legend.
p <- p +
  annotate("segment", x = 1.10, xend = 1.90, y = 4.73, yend = 4.73,
           linewidth = 0.9, colour = "#7A838A",
           arrow = arrow(length = unit(0.16, "inches"), type = "closed")) +
  annotate("text", x = 1.50, y = 4.93,
           label = "UDISE reports the previous financial year",
           size = 4.0, colour = "#5F6368", fontface = "bold")

out_dir <- "studies/composite_school_grant/figures/rendered"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

ggsave(file.path(out_dir, "csg_policy_prism_R.png"), p,
       width = 11.5, height = 8.2, units = "in", dpi = 320, bg = "white")
ggsave(file.path(out_dir, "csg_policy_prism_R.svg"), p,
       width = 11.5, height = 8.2, units = "in", bg = "white")
ggsave(file.path(out_dir, "csg_policy_prism_R.pdf"), p,
       width = 11.5, height = 8.2, units = "in", bg = "white")
