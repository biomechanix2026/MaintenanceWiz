# Maintenance Wizard — Architecture & Presentation

Deliverables explaining the **Agentic Predictive Maintenance Wizard** (Consolidated-Brain
decision-support agent for heavy steel plants).

## Files

| File | What it is |
|------|------------|
| `MaintenanceWizard.pptx` | 14-slide pitch deck (editable PowerPoint) |
| `MaintenanceWizard.pdf` | Same deck exported to PDF (for the submission ZIP) |
| `architecture.svg` | Standalone architecture diagram (vector, 960×540) |
| `architecture.png` | Rasterized architecture diagram (1920×1080) |
| `build_deck.js` | pptxgenjs source that generates the deck |
| `slides/` | Per-slide PNG renders (QA / preview) |

## Deck outline

1. Title
2. The Problem — fragmented data, manual diagnosis, costly downtime
3. The Idea — System of Record → System of Action
4. Five answered questions (the five-block output)
5. Architecture — The Consolidated Brain (embeds `architecture.png`)
6. One brain beats many agents (vs. multi-agent reference designs)
7. Reasoning pipeline — think → act → observe
8. Prognostics & explainability — RUL + SHAP
9. Constraint-aware prioritization (lead-time-vs-RUL flip)
10. Production stack + zero-dependency fallback ladder
11. Six differentiators
12. Demo scenarios
13. Roadmap — surpassing the requirements
14. Closing — predict, prepare, close the loop

## Regenerating

```bash
# Architecture PNG from the SVG (requires sharp)
NODE_PATH=$(npm root -g) node -e "require('sharp')('architecture.svg',{density:300}).resize(1920,1080).png().toFile('architecture.png')"

# The deck (requires pptxgenjs)
NODE_PATH=$(npm root -g) node build_deck.js
```

Export to PNG/PDF for review was done via PowerPoint COM automation (LibreOffice/poppler
were not available on this machine).

## Style

Neutral-technical: navy/blue/steel-grey palette, Georgia headers + Calibri body,
Consolas for tool/code names. Risk-band colors (red/orange/amber/green) used only where
priority semantics are shown.
