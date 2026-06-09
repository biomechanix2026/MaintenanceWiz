// Maintenance Wizard — pitch deck generator (pptxgenjs)
// Neutral-technical palette. Run: NODE_PATH=$(npm root -g) node build_deck.js
const pptxgen = require("pptxgenjs");

const C = {
  INK: "16202E", NAVY: "1B2A3A", BLUE: "2B6CB0", BLUELT: "EAF2FB",
  STEEL: "5B7085", MUTE: "7A8AA0", LIGHT: "EEF2F6", BORDER: "CBD5E1",
  WHITE: "FFFFFF", TEAL: "0E9488", TEALLT: "E1F3F1",
  RED: "C0392B", ORANGE: "E67E22", AMBER: "F1C40F", GREEN: "27AE60",
  PANEL: "F6F8FB",
};
const F = { H: "Georgia", B: "Calibri", M: "Consolas" };
const shadow = () => ({ type: "outer", color: "1B2A3A", blur: 7, offset: 2, angle: 135, opacity: 0.13 });

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625
pres.author = "Maintenance Wizard";
pres.title = "Agentic Predictive Maintenance Wizard";

// ---- helpers ----
function kicker(s, t, color = C.BLUE) {
  s.addText(t.toUpperCase(), { x: 0.5, y: 0.34, w: 9, h: 0.25, fontFace: F.B, fontSize: 11, bold: true, color, charSpacing: 2, margin: 0 });
}
function title(s, t, color = C.INK) {
  s.addText(t, { x: 0.5, y: 0.56, w: 9, h: 0.6, fontFace: F.H, fontSize: 28, bold: true, color, margin: 0 });
}
function card(s, x, y, w, h, fill = C.WHITE, line = C.BORDER) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.06, fill: { color: fill }, line: { color: line, width: 1 }, shadow: shadow() });
}
function numCircle(s, x, y, n, d = 0.42, fill = C.BLUE) {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill } });
  s.addText(String(n), { x, y, w: d, h: d, align: "center", valign: "middle", fontFace: F.H, fontSize: 16, bold: true, color: C.WHITE, margin: 0 });
}

// ============================================================ 1. TITLE
(() => {
  const s = pres.addSlide();
  s.background = { color: C.NAVY };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.16, h: 5.625, fill: { color: C.BLUE } });
  s.addText("AGENTIC AI CHALLENGE · ROUND 2", { x: 0.7, y: 0.7, w: 8, h: 0.3, fontFace: F.B, fontSize: 12, bold: true, color: "8FB4DC", charSpacing: 2, margin: 0 });
  s.addText("Maintenance Wizard", { x: 0.66, y: 1.5, w: 9, h: 0.95, fontFace: F.H, fontSize: 52, bold: true, color: C.WHITE, margin: 0 });
  s.addText("Agentic predictive-maintenance decision support for heavy steel plants", { x: 0.7, y: 2.55, w: 8.6, h: 0.45, fontFace: F.B, fontSize: 18, color: "CFE0F2", margin: 0 });
  s.addText([
    { text: "A System of Action", options: { bold: true, color: C.WHITE } },
    { text: "  —  it predicts what will break, prepares the fix, and refuses to close a job until every compliance step is logged.", options: { color: "AEC2D6" } },
  ], { x: 0.7, y: 3.25, w: 8.7, h: 0.6, fontFace: F.B, fontSize: 14, margin: 0 });
  // risk-band dot motif
  const bands = [C.RED, C.ORANGE, C.AMBER, C.GREEN];
  bands.forEach((c, i) => s.addShape(pres.shapes.OVAL, { x: 0.72 + i * 0.32, y: 4.35, w: 0.2, h: 0.2, fill: { color: c } }));
  s.addText("CRITICAL · HIGH · MEDIUM · LOW   priority-banded triage", { x: 2.1, y: 4.32, w: 7, h: 0.3, fontFace: F.M, fontSize: 11, color: "8FB4DC", valign: "middle", margin: 0 });
  s.addText("Consolidated-Brain agent  ·  runs on numpy + pandas + Streamlit alone", { x: 0.7, y: 5.0, w: 9, h: 0.3, fontFace: F.B, fontSize: 11.5, italic: true, color: "7E97B0", margin: 0 });
})();

// ============================================================ 2. PROBLEM
(() => {
  const s = pres.addSlide(); s.background = { color: C.WHITE };
  kicker(s, "The problem");
  title(s, "Fragmented data, manual diagnosis, costly downtime");
  s.addText("In a steel plant, an engineer diagnosing a fault juggles five disconnected systems — by hand, under time pressure, dependent on expert judgement. The result is slow, inconsistent decisions and avoidable unplanned downtime.", { x: 0.5, y: 1.35, w: 4.3, h: 1.6, fontFace: F.B, fontSize: 14.5, color: C.INK, lineSpacingMultiple: 1.12, margin: 0 });
  // big stat
  card(s, 0.5, 3.15, 4.3, 1.9, C.NAVY, C.NAVY);
  s.addText("5 → 1", { x: 0.5, y: 3.35, w: 4.3, h: 0.85, align: "center", fontFace: F.H, fontSize: 46, bold: true, color: C.WHITE, margin: 0 });
  s.addText("five fragmented sources collapsed into one traceable decision", { x: 0.7, y: 4.25, w: 3.9, h: 0.7, align: "center", fontFace: F.B, fontSize: 13, color: "CFE0F2", margin: 0 });
  // right: the five sources
  const items = [
    ["Equipment manuals & SOPs", "torque specs, isolation steps"],
    ["Sensor / condition data", "temperature, vibration, pressure…"],
    ["Historical delay logs", "downtime, tonnage lost"],
    ["Failure / incident records", "root cause, resolution"],
    ["ERP spares inventory", "stock levels & procurement lead time"],
  ];
  let y = 1.35;
  items.forEach((it, i) => {
    card(s, 5.05, y, 4.45, 0.68, C.PANEL);
    numCircle(s, 5.18, y + 0.13, i + 1, 0.42, C.BLUE);
    s.addText([
      { text: it[0] + "\n", options: { bold: true, fontSize: 13.5, color: C.INK, breakLine: true } },
      { text: it[1], options: { fontSize: 11, color: C.STEEL } },
    ], { x: 5.74, y: y + 0.04, w: 3.7, h: 0.6, fontFace: F.B, valign: "middle", margin: 0 });
    y += 0.745;
  });
})();

// ============================================================ 3. SYSTEM OF ACTION
(() => {
  const s = pres.addSlide(); s.background = { color: C.WHITE };
  kicker(s, "The idea");
  title(s, "Not a System of Record — a System of Action");
  // left card
  card(s, 0.5, 1.45, 4.4, 3.4, C.PANEL);
  s.addText("SYSTEM OF RECORD", { x: 0.7, y: 1.65, w: 4, h: 0.3, fontFace: F.B, fontSize: 12, bold: true, color: C.STEEL, charSpacing: 1, margin: 0 });
  s.addText("Passive databases", { x: 0.7, y: 1.95, w: 4, h: 0.4, fontFace: F.H, fontSize: 18, bold: true, color: C.INK, margin: 0 });
  s.addText([
    { text: "Tells you what broke and when", options: { bullet: true, breakLine: true } },
    { text: "Waits for a human to ask", options: { bullet: true, breakLine: true } },
    { text: "Knowledge scattered across silos", options: { bullet: true, breakLine: true } },
    { text: "Reactive troubleshooting", options: { bullet: true } },
  ], { x: 0.75, y: 2.5, w: 4, h: 2.2, fontFace: F.B, fontSize: 13.5, color: C.INK, paraSpaceAfter: 8, margin: 0 });
  // arrow
  s.addShape(pres.shapes.RIGHT_ARROW, { x: 4.62, y: 2.9, w: 0.78, h: 0.55, fill: { color: C.BLUE } });
  // right card
  card(s, 5.1, 1.45, 4.4, 3.4, C.NAVY, C.NAVY);
  s.addText("SYSTEM OF ACTION", { x: 5.3, y: 1.65, w: 4, h: 0.3, fontFace: F.B, fontSize: 12, bold: true, color: "8FB4DC", charSpacing: 1, margin: 0 });
  s.addText("An autonomous agent", { x: 5.3, y: 1.95, w: 4, h: 0.4, fontFace: F.H, fontSize: 18, bold: true, color: C.WHITE, margin: 0 });
  s.addText([
    { text: "Predicts what will break — and when", options: { bullet: true, breakLine: true } },
    { text: "Prepares the work order before login", options: { bullet: true, breakLine: true } },
    { text: "Fuses all five sources in one loop", options: { bullet: true, breakLine: true } },
    { text: "Closes the loop: blocks non-compliant jobs", options: { bullet: true } },
  ], { x: 5.35, y: 2.5, w: 4, h: 2.2, fontFace: F.B, fontSize: 13.5, color: "E4ECF5", paraSpaceAfter: 8, margin: 0 });
})();

// ============================================================ 4. FIVE-STAGE CAPABILITY
(() => {
  const s = pres.addSlide(); s.background = { color: C.WHITE };
  kicker(s, "What it delivers");
  title(s, "One decision, five answered questions");
  const stages = [
    ["Operational Risk", "How urgent is this?", "priority band + score, delay severity"],
    ["Root-Cause Diagnosis", "Why is it failing?", "probable fault + SHAP drivers"],
    ["Maintenance Blueprint", "How do I fix it?", "isolation steps + verified SOP tasks"],
    ["Supply-Chain Strategy", "Can I get the parts?", "stock, lead time, mitigations"],
    ["Traceability & Audit", "Can I trust it?", "cited manuals, incidents, the SQL run"],
  ];
  const w = 1.78, gap = 0.08; let x = 0.5;
  stages.forEach((st, i) => {
    card(s, x, 1.5, w, 3.2, C.PANEL);
    numCircle(s, x + w / 2 - 0.21, 1.66, i + 1, 0.42, C.BLUE);
    s.addText(st[0], { x: x + 0.08, y: 2.2, w: w - 0.16, h: 0.7, align: "center", fontFace: F.H, fontSize: 14, bold: true, color: C.INK, margin: 0 });
    s.addText(st[1], { x: x + 0.08, y: 2.95, w: w - 0.16, h: 0.6, align: "center", fontFace: F.B, fontSize: 12, italic: true, color: C.BLUE, margin: 0 });
    s.addText(st[2], { x: x + 0.1, y: 3.65, w: w - 0.2, h: 0.95, align: "center", fontFace: F.B, fontSize: 11, color: C.STEEL, margin: 0 });
    if (i < 4) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + w + gap / 2 - 0.07, y: 2.95, w: 0.16, h: 0.22, fill: { color: C.BORDER } });
    x += w + gap;
  });
  s.addText("Every diagnosis returns the same mandatory five-block output — scannable, structured, and fully cited.", { x: 0.5, y: 4.85, w: 9, h: 0.4, align: "center", fontFace: F.B, fontSize: 12.5, italic: true, color: C.STEEL, margin: 0 });
})();

// ============================================================ 5. ARCHITECTURE (diagram)
(() => {
  const s = pres.addSlide(); s.background = { color: C.WHITE };
  kicker(s, "Architecture");
  title(s, "The Consolidated Brain");
  s.addImage({ path: "architecture.png", x: 0.5, y: 1.32, w: 6.55, h: 3.68 }); // 960x540 ratio
  // right callouts
  const pts = [
    ["One loop", "A single think→act→observe agent holds the full context and the entire tool suite — no sub-agents."],
    ["Dual mode", "Identical tools run via Claude (LLM) or a deterministic Python pipeline — the reproducible offline baseline."],
    ["Smart tools", "Every tool returns a rich structured object: RUL+SHAP, cited SOPs, stock+lead time, the exact SQL it ran."],
  ];
  let y = 1.4;
  pts.forEach((p) => {
    card(s, 7.2, y, 2.3, 1.12, C.PANEL);
    s.addText(p[0], { x: 7.34, y: y + 0.08, w: 2.05, h: 0.3, fontFace: F.H, fontSize: 13.5, bold: true, color: C.BLUE, margin: 0 });
    s.addText(p[1], { x: 7.34, y: y + 0.38, w: 2.05, h: 0.7, fontFace: F.B, fontSize: 10, color: C.INK, margin: 0, lineSpacingMultiple: 1.02 });
    y += 1.22;
  });
})();

// ============================================================ 6. ONE BRAIN VS MANY
(() => {
  const s = pres.addSlide(); s.background = { color: C.WHITE };
  kicker(s, "Design choice");
  title(s, "One brain beats many agents");
  card(s, 0.5, 1.45, 4.4, 3.4, C.PANEL);
  s.addText("MULTI-AGENT (supervisor + sub-agents)", { x: 0.7, y: 1.62, w: 4.05, h: 0.3, fontFace: F.B, fontSize: 11.5, bold: true, color: C.STEEL, charSpacing: 0.5, margin: 0 });
  s.addText([
    { text: "Planning split across a supervisor and specialised agents", options: { bullet: true, breakLine: true } },
    { text: "\"Split-brain\": agents hold mismatched slices of context", options: { bullet: true, breakLine: true } },
    { text: "More moving parts, more orchestration overhead", options: { bullet: true, breakLine: true } },
    { text: "Harder to trace one coherent decision", options: { bullet: true } },
  ], { x: 0.75, y: 2.1, w: 4.05, h: 2.6, fontFace: F.B, fontSize: 13, color: C.INK, paraSpaceAfter: 9, margin: 0 });
  card(s, 5.1, 1.45, 4.4, 3.4, C.BLUELT, C.BLUE);
  s.addText("CONSOLIDATED BRAIN (this project)", { x: 5.3, y: 1.62, w: 4.05, h: 0.3, fontFace: F.B, fontSize: 11.5, bold: true, color: C.BLUE, charSpacing: 0.5, margin: 0 });
  s.addText([
    { text: "One loop holds the full context + the entire tool suite", options: { bullet: true, breakLine: true } },
    { text: "No knowledge mismatch — nothing to reconcile", options: { bullet: true, breakLine: true } },
    { text: "Simpler, cheaper, fully observable trace", options: { bullet: true, breakLine: true } },
    { text: "Same five-stage capability, one accountable answer", options: { bullet: true } },
  ], { x: 5.35, y: 2.1, w: 4.05, h: 2.6, fontFace: F.B, fontSize: 13, color: C.INK, paraSpaceAfter: 9, margin: 0 });
  s.addText("Following the Omni / Blobby lesson: consolidate planning, don't fragment it.", { x: 0.5, y: 4.95, w: 9, h: 0.35, align: "center", fontFace: F.B, fontSize: 12, italic: true, color: C.STEEL, margin: 0 });
})();

// ============================================================ 7. REASONING PIPELINE
(() => {
  const s = pres.addSlide(); s.background = { color: C.WHITE };
  kicker(s, "Reasoning pipeline");
  title(s, "Think → act → observe");
  const steps = [
    ["0", "Resolve", "map jargon → asset_id", "resolve_asset"],
    ["1", "Predict", "RUL, failure prob, SHAP", "prognostic_tool"],
    ["2", "Retrieve", "SOPs, incidents, SQL", "rag_tool · sql_query"],
    ["3", "Supply", "stock & lead times", "inventory_tool"],
    ["4", "Prioritise", "constraint-aware score", "risk_score_tool"],
    ["5", "Reconcile", "emit 5-block, alert", "alert_dispatch"],
  ];
  const w = 1.46, gap = 0.06; let x = 0.5;
  steps.forEach((st) => {
    card(s, x, 1.7, w, 2.4, C.PANEL);
    numCircle(s, x + 0.12, 1.84, st[0], 0.4, C.NAVY);
    s.addText(st[1], { x: x + 0.08, y: 2.36, w: w - 0.16, h: 0.35, align: "center", fontFace: F.H, fontSize: 14, bold: true, color: C.INK, margin: 0 });
    s.addText(st[2], { x: x + 0.08, y: 2.74, w: w - 0.16, h: 0.7, align: "center", fontFace: F.B, fontSize: 10.5, color: C.STEEL, margin: 0 });
    s.addText(st[3], { x: x + 0.06, y: 3.5, w: w - 0.12, h: 0.5, align: "center", fontFace: F.M, fontSize: 8.7, color: C.BLUE, margin: 0 });
    x += w + gap;
  });
  card(s, 0.5, 4.35, 9, 0.78, C.BLUELT, C.BLUE);
  s.addText([
    { text: "STEP 4.5 — Plant impact (designed): ", options: { bold: true, color: C.BLUE } },
    { text: "cascade_tool computes downstream blast radius so an asset's priority reflects what it idles, not just its own health.", options: { color: C.INK } },
  ], { x: 0.7, y: 4.46, w: 8.6, h: 0.55, fontFace: F.B, fontSize: 12, valign: "middle", margin: 0 });
})();

// ============================================================ 8. PROGNOSTICS + SHAP
(() => {
  const s = pres.addSlide(); s.background = { color: C.WHITE };
  kicker(s, "Model design & explainability");
  title(s, "Prognostics you can interrogate");
  s.addText([
    { text: "Remaining Useful Life", options: { bold: true, color: C.INK } },
    { text: " + 30-day failure probability, from a Random Forest trained on per-asset-type ", options: { color: C.INK } },
    { text: "deviations", options: { bold: true, italic: true, color: C.BLUE } },
    { text: " (z-scores vs a healthy baseline). One model serves furnaces, pumps, valves…", options: { color: C.INK } },
  ], { x: 0.5, y: 1.35, w: 4.35, h: 1.5, fontFace: F.B, fontSize: 14, lineSpacingMultiple: 1.12, margin: 0 });
  s.addText([
    { text: "SHAP attribution", options: { bold: true, color: C.INK } },
    { text: " explains every prediction — negative bars push RUL down (accelerate failure). Falls back to model-agnostic ablation when the SHAP library is absent.", options: { color: C.INK } },
  ], { x: 0.5, y: 2.95, w: 4.35, h: 1.5, fontFace: F.B, fontSize: 14, lineSpacingMultiple: 1.12, margin: 0 });
  // SHAP bar chart (example: gearbox)
  s.addText("SHAP drivers — Mill Drive Gearbox 5 (example)", { x: 5.05, y: 1.3, w: 4.45, h: 0.3, align: "center", fontFace: F.B, fontSize: 12, bold: true, color: C.STEEL, margin: 0 });
  s.addChart(pres.charts.BAR, [{
    name: "Contribution (days)",
    labels: ["vibration", "temperature", "pressure", "power", "humidity"],
    values: [-8.4, -3.6, -1.2, 0.9, 0.3],
  }], {
    x: 4.95, y: 1.6, w: 4.6, h: 3.5, barDir: "bar",
    chartColors: [C.BLUE], chartColorsOpacity: [95],
    chartArea: { fill: { color: C.PANEL } },
    catAxisLabelPos: "low", // keep category labels at the left edge, clear of diverging bars
    catAxisLabelColor: C.STEEL, catAxisLabelFontSize: 11, catAxisLabelFontFace: F.M,
    valAxisLabelColor: C.STEEL, valAxisLabelFontSize: 9,
    valGridLine: { color: C.BORDER, size: 0.5 }, catGridLine: { style: "none" },
    showValue: true, dataLabelColor: C.INK, dataLabelFontSize: 9.5, dataLabelPosition: "outEnd",
    showLegend: false, showTitle: false,
  });
})();

// ============================================================ 9. CONSTRAINT-AWARE
(() => {
  const s = pres.addSlide(); s.background = { color: C.WHITE };
  kicker(s, "Signature behaviour");
  title(s, "Constraint-aware prioritization");
  card(s, 0.5, 1.4, 9, 0.95, C.NAVY, C.NAVY);
  s.addText("Priority  =  100 × ( 0.40·RUL  +  0.30·criticality  +  0.15·delay-history  +  0.15·spares )", { x: 0.5, y: 1.55, w: 9, h: 0.4, align: "center", fontFace: F.M, fontSize: 15, bold: true, color: C.WHITE, margin: 0 });
  s.addText("deterministic, explainable, 0–100 → CRITICAL / HIGH / MEDIUM / LOW", { x: 0.5, y: 1.98, w: 9, h: 0.3, align: "center", fontFace: F.B, fontSize: 11.5, color: "AEC2D6", margin: 0 });
  // the flip
  card(s, 0.5, 2.65, 4.4, 2.45, C.PANEL);
  s.addText("The constraint flag", { x: 0.7, y: 2.8, w: 4, h: 0.35, fontFace: F.H, fontSize: 15, bold: true, color: C.INK, margin: 0 });
  s.addText("When an out-of-stock part's lead time exceeds the predicted RUL, the repair physically cannot finish before failure. The agent flips its own recommendation.", { x: 0.7, y: 3.2, w: 4.05, h: 1.8, fontFace: F.B, fontSize: 13, color: C.INK, lineSpacingMultiple: 1.12, margin: 0 });
  card(s, 5.1, 2.65, 4.4, 2.45, C.TEALLT, C.TEAL);
  s.addText("GEARBOX-05 — worked example", { x: 5.3, y: 2.8, w: 4, h: 0.35, fontFace: F.H, fontSize: 14, bold: true, color: "0B5E55", margin: 0 });
  s.addText([
    { text: "Predicted RUL:  ~38 days\n", options: { breakLine: true } },
    { text: "Pinion lead time:  45 days\n", options: { breakLine: true } },
    { text: "→ part arrives AFTER failure\n\n", options: { bold: true, color: C.RED, breakLine: true } },
    { text: "Recommendation flips:  ", options: { color: C.INK } },
    { text: "\"replace now\" → monitored-degradation plan + auto-alert", options: { bold: true, color: "0B5E55" } },
  ], { x: 5.3, y: 3.2, w: 4.05, h: 1.85, fontFace: F.B, fontSize: 12.5, color: C.INK, margin: 0 });
})();

// ============================================================ 10. FALLBACK LADDER
(() => {
  const s = pres.addSlide(); s.background = { color: C.WHITE };
  kicker(s, "Runs anywhere");
  title(s, "Production stack, zero-dependency fallback");
  const rows = [
    [{ text: "Layer", options: { bold: true, color: C.WHITE } }, { text: "Production path", options: { bold: true, color: C.WHITE } }, { text: "Zero-dep fallback", options: { bold: true, color: C.WHITE } }],
    ["Prognostics", "scikit-learn RandomForest", "NumpyForest (bagged CART, numpy)"],
    ["Explainability", "shap.TreeExplainer", "ablation attribution"],
    ["Retrieval", "ChromaDB vector store", "TF-IDF cosine index (numpy)"],
    ["Reasoning", "Claude tool-use loop", "deterministic Python pipeline"],
  ];
  s.addTable(rows, {
    x: 0.5, y: 1.5, w: 9, colW: [1.9, 3.55, 3.55],
    rowH: [0.5, 0.62, 0.62, 0.62, 0.62],
    fontFace: F.B, fontSize: 13, color: C.INK, valign: "middle",
    border: { type: "solid", pt: 1, color: C.BORDER },
    fill: { color: C.WHITE },
    align: "left",
  });
  // header + zebra via manual fills isn't trivial; recolor header row by overlay
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.5, w: 9, h: 0.5, fill: { color: C.NAVY } });
  s.addText([
    { text: "Layer", options: { bold: true } }, { text: "", options: { breakLine: false } },
  ], { x: 0.6, y: 1.5, w: 1.8, h: 0.5, fontFace: F.B, fontSize: 13, bold: true, color: C.WHITE, valign: "middle", margin: 0 });
  s.addText("Production path", { x: 2.5, y: 1.5, w: 3.4, h: 0.5, fontFace: F.B, fontSize: 13, bold: true, color: C.WHITE, valign: "middle", margin: 0 });
  s.addText("Zero-dependency fallback", { x: 6.05, y: 1.5, w: 3.4, h: 0.5, fontFace: F.B, fontSize: 13, bold: true, color: C.WHITE, valign: "middle", margin: 0 });
  card(s, 0.5, 4.55, 9, 0.62, C.BLUELT, C.BLUE);
  s.addText([
    { text: "The deterministic path is also the reproducible baseline the eval judges score against — ", options: { color: C.INK } },
    { text: "the same fixed inputs always land in the same risk band.", options: { bold: true, color: C.BLUE } },
  ], { x: 0.7, y: 4.66, w: 8.6, h: 0.4, fontFace: F.B, fontSize: 12.5, valign: "middle", margin: 0 });
})();

// ============================================================ 11. DIFFERENTIATORS
(() => {
  const s = pres.addSlide(); s.background = { color: C.WHITE };
  kicker(s, "Why it stands out");
  title(s, "Six things most submissions miss");
  const items = [
    ["Real prognostic ML", "RUL + failure prob + SHAP — not just LLM-over-docs"],
    ["Zero-hallucination", "tool outputs are the only source of truth; SQL shown"],
    ["Runs offline", "deterministic mode + numpy fallback ladder"],
    ["Multi-turn dialogue", "context-aware follow-ups keep the asset in focus"],
    ["Feedback loop", "engineer corrections re-index RAG + adjust priority"],
    ["Trace-based evals", "judges guard every change against regressions"],
  ];
  const w = 2.86, h = 1.5, gx = 0.21, gy = 0.22; let i = 0;
  for (let r = 0; r < 2; r++) for (let c = 0; c < 3; c++) {
    const x = 0.5 + c * (w + gx), y = 1.5 + r * (h + gy);
    card(s, x, y, w, h, C.PANEL);
    s.addShape(pres.shapes.OVAL, { x: x + 0.16, y: y + 0.18, w: 0.34, h: 0.34, fill: { color: C.BLUE } });
    s.addText("✓", { x: x + 0.16, y: y + 0.18, w: 0.34, h: 0.34, align: "center", valign: "middle", fontFace: F.B, fontSize: 15, bold: true, color: C.WHITE, margin: 0 });
    s.addText(items[i][0], { x: x + 0.6, y: y + 0.18, w: w - 0.75, h: 0.4, fontFace: F.H, fontSize: 14, bold: true, color: C.INK, margin: 0 });
    s.addText(items[i][1], { x: x + 0.18, y: y + 0.66, w: w - 0.36, h: 0.75, fontFace: F.B, fontSize: 11.5, color: C.STEEL, lineSpacingMultiple: 1.05, margin: 0 });
    i++;
  }
})();

// ============================================================ 12. DEMO SCENARIOS
(() => {
  const s = pres.addSlide(); s.background = { color: C.WHITE };
  kicker(s, "See it work");
  title(s, "Demo scenarios");
  const rows = [
    ["what's wrong with the mill gearbox?", "Constraint-aware triage", "RUL < lead time → flips to monitored degradation + auto-alert"],
    ["that valve that keeps leaking on the caster", "Fuzzy resolution", "plant jargon → HYD-VALVE-07 before any tool call"],
    ["check the EAF", "Abbreviation", "resolves to FURNACE-01"],
    ["Pre-Shift Report tab", "Proactive autonomy", "work orders drafted for every flagged asset before login"],
    ["Digital Logbook tab", "Loop closure", "job closure blocked until all five compliance items are green"],
  ];
  let y = 1.45;
  rows.forEach((r) => {
    card(s, 0.5, y, 9, 0.66, C.PANEL);
    s.addText("“" + r[0] + "”", { x: 0.66, y: y + 0.05, w: 3.5, h: 0.56, fontFace: F.M, fontSize: 11, color: C.BLUE, valign: "middle", margin: 0 });
    s.addText(r[1], { x: 4.25, y: y + 0.05, w: 1.95, h: 0.56, fontFace: F.B, fontSize: 12.5, bold: true, color: C.INK, valign: "middle", margin: 0 });
    s.addText(r[2], { x: 6.25, y: y + 0.05, w: 3.15, h: 0.56, fontFace: F.B, fontSize: 10.8, color: C.STEEL, valign: "middle", margin: 0 });
    y += 0.74;
  });
})();

// ============================================================ 13. ROADMAP
(() => {
  const s = pres.addSlide(); s.background = { color: C.WHITE };
  kicker(s, "Beyond the brief");
  title(s, "Roadmap — surpassing the requirements");
  const items = [
    ["Plant cascade graph", "Designed", "blast-radius / bottleneck propagation across the line", C.BLUE],
    ["Domain-specific SLM", "Planned", "distilled maintenance model as an offline reasoning rung", C.STEEL],
    ["Quantified outcomes", "Planned", "back-tested downtime-hours & cost avoided", C.STEEL],
    ["Optimized scheduling", "Planned", "place repairs in the RUL window vs production calendar", C.STEEL],
  ];
  const w = 4.4, h = 1.55, gx = 0.2, gy = 0.22; let i = 0;
  for (let r = 0; r < 2; r++) for (let c = 0; c < 2; c++) {
    const x = 0.5 + c * (w + gx), y = 1.5 + r * (h + gy);
    card(s, x, y, w, h, C.PANEL);
    s.addText(items[i][0], { x: x + 0.22, y: y + 0.2, w: 2.9, h: 0.4, fontFace: F.H, fontSize: 15, bold: true, color: C.INK, margin: 0 });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + w - 1.35, y: y + 0.22, w: 1.13, h: 0.34, rectRadius: 0.17, fill: { color: items[i][3] } });
    s.addText(items[i][1], { x: x + w - 1.35, y: y + 0.22, w: 1.13, h: 0.34, align: "center", valign: "middle", fontFace: F.B, fontSize: 10.5, bold: true, color: C.WHITE, margin: 0 });
    s.addText(items[i][2], { x: x + 0.22, y: y + 0.72, w: w - 0.44, h: 0.7, fontFace: F.B, fontSize: 12, color: C.STEEL, lineSpacingMultiple: 1.05, margin: 0 });
    i++;
  }
})();

// ============================================================ 14. CLOSING
(() => {
  const s = pres.addSlide(); s.background = { color: C.NAVY };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.16, h: 5.625, fill: { color: C.BLUE } });
  s.addText("FROM REACTIVE TO PROACTIVE", { x: 0.7, y: 0.9, w: 8, h: 0.3, fontFace: F.B, fontSize: 12, bold: true, color: "8FB4DC", charSpacing: 2, margin: 0 });
  s.addText("Predict. Prepare. Close the loop.", { x: 0.66, y: 1.5, w: 9, h: 0.9, fontFace: F.H, fontSize: 40, bold: true, color: C.WHITE, margin: 0 });
  const outs = [
    "Reduce unplanned downtime",
    "Faster, more consistent diagnosis",
    "Proactive, prioritized maintenance",
    "Audit-grade, traceable decisions",
  ];
  let y = 2.75;
  outs.forEach((o) => {
    s.addShape(pres.shapes.OVAL, { x: 0.72, y: y + 0.03, w: 0.18, h: 0.18, fill: { color: C.TEAL } });
    s.addText(o, { x: 1.05, y: y - 0.05, w: 8, h: 0.35, fontFace: F.B, fontSize: 16, color: "E4ECF5", margin: 0 });
    y += 0.5;
  });
  s.addText("Maintenance Wizard  ·  Consolidated-Brain agent for heavy steel plants", { x: 0.7, y: 5.05, w: 9, h: 0.3, fontFace: F.B, fontSize: 12, italic: true, color: "7E97B0", margin: 0 });
})();

pres.writeFile({ fileName: "MaintenanceWizard.pptx" }).then((f) => console.log("Deck written:", f));
