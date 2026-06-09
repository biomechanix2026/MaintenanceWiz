import { useState } from "react";

const sections = [
  {
    id: "problem",
    label: "THE REAL PROBLEM",
    icon: "⚡",
    color: "#FF4B1F",
    accent: "#ff6b47",
    items: [
      {
        title: "Information Overload",
        body: "Engineers juggle SOPs, sensor alerts, spreadsheet logs, and tribal knowledge simultaneously — under pressure, at 3 AM, when a furnace is failing.",
        tag: "Root Cause"
      },
      {
        title: "Synthesis is the Bottleneck",
        body: "The problem isn't lack of data. It's collapsing fragmented sources into a single traceable decision in seconds.",
        tag: "Insight"
      },
      {
        title: "Trust Gap",
        body: "Engineers won't act on AI outputs they can't inspect. Explainability isn't a nice-to-have — it's the product.",
        tag: "Critical"
      }
    ]
  },
  {
    id: "arch",
    label: "ARCHITECTURE BETS",
    icon: "🏗️",
    color: "#0057FF",
    accent: "#3380ff",
    items: [
      {
        title: "✅ Consolidated Brain (Recommended)",
        body: "Single LLM orchestrator with rich tool calls. Full context in one loop. No inter-agent drift. Clean traceability for judging panel.",
        tag: "Best for Demo"
      },
      {
        title: "⚠️ Multi-Agent Planner",
        body: "Orchestrator dispatches to Diagnostic / ML / SOP specialists. Impressive diagram but agent-to-agent handoff failures are demo killers.",
        tag: "High Risk"
      },
      {
        title: "✅✅ Hybrid — Smart Tools",
        body: "One brain, but each 'tool' is a rich mini-pipeline. RAG returns structured knowledge objects. ML returns RUL + SHAP breakdown. Best of both worlds.",
        tag: "Sweet Spot"
      }
    ]
  },
  {
    id: "tools",
    label: "TOOL DESIGN",
    icon: "🔧",
    color: "#00A878",
    accent: "#00cc94",
    items: [
      {
        title: "rag_knowledge_tool(asset_id, query)",
        body: "Returns: matched SOP sections, failure analysis excerpts, confidence score — all tagged to exact asset. Not just text blobs.",
        tag: "RAG"
      },
      {
        title: "prognostic_ml_tool(asset_id, sensors)",
        body: "Returns: failure_probability, rul_days, confidence interval, SHAP contributions per sensor parameter. The 'why' alongside the 'what'.",
        tag: "ML + SHAP"
      },
      {
        title: "erp_inventory_tool(part_number)",
        body: "Returns: stock qty, lead time, alternative parts, vendor — enables constraint-aware recommendations instead of impossible advice.",
        tag: "ERP"
      },
      {
        title: "delay_log_tool(asset_id, days)",
        body: "Returns: historical downtime events, delay codes, cost estimates, pattern detection (e.g. 'recurring Q1 spike').",
        tag: "History"
      }
    ]
  },
  {
    id: "scoring",
    label: "RISK SCORING LOGIC",
    icon: "📊",
    color: "#8B00FF",
    accent: "#a64dff",
    items: [
      {
        title: "Priority Score Formula",
        body: "SCORE = (Process Criticality × 0.35) + (Delay Severity × 0.25) + (RUL Urgency × 0.25) + (Parts Risk × 0.15)",
        tag: "Deterministic"
      },
      {
        title: "CRITICAL (>18): Act Now",
        body: "Immediate shutdown or isolation protocol. Alert shift supervisor. Generate emergency procurement request.",
        tag: "Band 4"
      },
      {
        title: "HIGH (12–18): 48hr Window",
        body: "Schedule within 48 hours. Raise procurement alert if parts unavailable. Increase sensor polling frequency.",
        tag: "Band 3"
      },
      {
        title: "Constraint Flip Logic",
        body: "If part lead time > RUL days → don't say 'replace immediately'. Instead generate a controlled degradation monitoring protocol.",
        tag: "🎯 Differentiator"
      }
    ]
  },
  {
    id: "differentiators",
    label: "WINNING DIFFERENTIATORS",
    icon: "🎯",
    color: "#FF006E",
    accent: "#ff4d95",
    items: [
      {
        title: "SHAP Waterfall Chart",
        body: "Not 'vibration is high' — a live bar chart showing exactly which sensor contributed how much to the failure prediction. Engineers trust what they can inspect.",
        tag: "Trust Builder"
      },
      {
        title: "One-Click Digital Logbook",
        body: "Every recommendation → pushed to log with engineer name, timestamp, AI confidence score, source citations. Traceability requirement solved elegantly.",
        tag: "Deliverable"
      },
      {
        title: "Plant-Level Bottleneck View",
        body: "Not just single asset — dashboard ranks ALL assets by Priority Score. Shift supervisor sees the whole picture at a glance.",
        tag: "Scale Story"
      },
      {
        title: "Feedback Loop UX",
        body: "After resolution: 'How did it go?' modal captures outcome. Feeds back into scoring calibration. Shows the system learns.",
        tag: "Bonus Points"
      },
      {
        title: "Constraint-Aware Plans",
        body: "RUL 12 days + 21-day lead time = system proactively offers degradation monitoring protocol. Operationally realistic advice.",
        tag: "Key Insight"
      }
    ]
  },
  {
    id: "ui",
    label: "UI PANELS",
    icon: "🖥️",
    color: "#FF8C00",
    accent: "#ffa640",
    items: [
      {
        title: "Panel 1: Plant Overview",
        body: "Asset health grid (color-coded by risk). Active alerts with Priority Scores. Plant-level bottleneck heatmap. RUL timeline for top 5 at-risk assets.",
        tag: "Dashboard"
      },
      {
        title: "Panel 2: Asset Deep-Dive",
        body: "Sensor trend charts (30-day). SHAP waterfall chart for current anomaly. Historical failure timeline. Linked SOP documents.",
        tag: "Analysis"
      },
      {
        title: "Panel 3: Wizard Chat",
        body: "Natural language interface with 5-block structured output rendered inline. Source citations. Expandable document preview. 'Log this action' button.",
        tag: "Core UX"
      },
      {
        title: "Panel 4: Digital Logbook",
        body: "Timestamped decisions with AI confidence scores. Filterable by asset/date/engineer/outcome. Export to PDF/CSV.",
        tag: "Audit Trail"
      }
    ]
  },
  {
    id: "techstack",
    label: "TECH STACK",
    icon: "⚙️",
    color: "#2D6A4F",
    accent: "#40916c",
    items: [
      { title: "Orchestration: LangGraph", body: "Stateful multi-turn, tool calling, and full execution trace for traceability.", tag: "Core" },
      { title: "LLM: Claude 3.5 Sonnet", body: "Strong reasoning + structured JSON output. Handles complex multi-constraint problems well.", tag: "Brain" },
      { title: "Vector Store: ChromaDB", body: "Zero-infra, fast for demo scale. No external service dependency.", tag: "RAG" },
      { title: "ML: sklearn + SHAP", body: "Random Forest for RUL. Direct SHAP integration. Trainable on mock data in minutes.", tag: "Predict" },
      { title: "UI: Streamlit", body: "Hackathon speed. Python-native. 4 panels in ~500 lines.", tag: "Frontend" },
      { title: "Storage: SQLite", body: "Mock ERP + delay log. Zero setup. Ships in a ZIP.", tag: "Data" }
    ]
  },
  {
    id: "sprint",
    label: "3-DAY SPRINT",
    icon: "🚀",
    color: "#C77DFF",
    accent: "#d499ff",
    items: [
      {
        title: "Day 1 — Data + Brain",
        body: "Generate mock data (CSV + Markdown SOPs). Train sklearn RUL model with SHAP. Set up ChromaDB, embed all documents. Write and test all 4 core tools.",
        tag: "Foundation"
      },
      {
        title: "Day 2 — Orchestration",
        body: "Build LangGraph loop. Wire system prompt. Implement 5-block structured output. Test multi-turn conversations for 3 core scenarios.",
        tag: "Logic"
      },
      {
        title: "Day 3 — UI + Polish",
        body: "Build Streamlit dashboard (4 panels). Integrate SHAP visualization. Build digital logbook + feedback modal. Record demo, write architecture doc, package ZIP.",
        tag: "Delivery"
      }
    ]
  },
  {
    id: "wildcards",
    label: "WILD CARDS",
    icon: "🃏",
    color: "#E63946",
    accent: "#f26370",
    items: [
      { title: "Voice Input (Whisper)", body: "Hands-free maintenance queries. Engineers wearing gloves in the field can't type.", tag: "Wow Factor" },
      { title: "Image Input (Vision)", body: "Upload photo of damaged component → Claude describes the fault. Real-world applicability.", tag: "Multimodal" },
      { title: "Failure Simulation", body: "'What if temperature rises 20% over 6 hours?' → stress-test predictions. Great for demo theater.", tag: "Demo" },
      { title: "Shift Handover Report", body: "Auto-generate end-of-shift summary of all AI interactions. Instant adoption story.", tag: "Practical" }
    ]
  }
];

const riskItems = [
  { risk: "LLM API rate limit during live demo", fix: "Pre-cache 3–5 'golden path' responses as static fixtures" },
  { risk: "ML model cold start lag", fix: "Pre-load model and warm up on app startup" },
  { risk: "RAG retrieval miss on demo asset", fix: "Hard-code fallback response for demo assets" },
  { risk: "UI crash mid-presentation", fix: "Record screen demo backup video first, always" },
  { risk: "No sensor data scenario", fix: "System gracefully falls back to pure RAG + manual heuristics" }
];

export default function BrainstormBoard() {
  const [active, setActive] = useState("problem");
  const [expandedRisk, setExpandedRisk] = useState(null);

  const current = sections.find(s => s.id === active);

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0a0a0f",
      color: "#e8e8e8",
      fontFamily: "'Courier New', 'Lucida Console', monospace",
      padding: "0",
      overflow: "hidden"
    }}>
      {/* Header */}
      <div style={{
        borderBottom: "1px solid #1e1e2e",
        padding: "20px 32px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        background: "#080810"
      }}>
        <div>
          <div style={{ fontSize: 11, letterSpacing: 6, color: "#555", textTransform: "uppercase", marginBottom: 4 }}>
            AGENTIC AI CHALLENGE — ROUND 2
          </div>
          <div style={{ fontSize: 22, fontWeight: "bold", color: "#fff", letterSpacing: 1 }}>
            MAINTENANCE WIZARD
            <span style={{ color: "#FF4B1F", marginLeft: 10 }}>BRAINSTORM</span>
          </div>
        </div>
        <div style={{
          fontSize: 11, color: "#444", letterSpacing: 3,
          border: "1px solid #1e1e2e", padding: "6px 14px",
          background: "#0d0d1a"
        }}>
          STEEL PLANT // INDUSTRIAL AI // HACKATHON
        </div>
      </div>

      <div style={{ display: "flex", height: "calc(100vh - 70px)" }}>
        {/* Sidebar Nav */}
        <div style={{
          width: 200,
          borderRight: "1px solid #1e1e2e",
          padding: "16px 0",
          background: "#080810",
          overflowY: "auto",
          flexShrink: 0
        }}>
          {sections.map(s => (
            <button
              key={s.id}
              onClick={() => setActive(s.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                width: "100%",
                padding: "10px 16px",
                background: active === s.id ? "#0d0d1a" : "transparent",
                border: "none",
                borderLeft: active === s.id ? `3px solid ${s.color}` : "3px solid transparent",
                color: active === s.id ? "#fff" : "#555",
                fontSize: 10,
                letterSpacing: 2,
                textAlign: "left",
                cursor: "pointer",
                textTransform: "uppercase",
                transition: "all 0.15s ease"
              }}
            >
              <span style={{ fontSize: 14 }}>{s.icon}</span>
              <span>{s.label.split(" ").slice(0, 2).join(" ")}</span>
            </button>
          ))}
          <div style={{
            margin: "16px 0 8px",
            borderTop: "1px solid #1e1e2e",
            paddingTop: 16
          }}>
            <button
              onClick={() => setActive("risks")}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                width: "100%",
                padding: "10px 16px",
                background: active === "risks" ? "#0d0d1a" : "transparent",
                border: "none",
                borderLeft: active === "risks" ? "3px solid #FFD60A" : "3px solid transparent",
                color: active === "risks" ? "#fff" : "#555",
                fontSize: 10,
                letterSpacing: 2,
                cursor: "pointer",
                textTransform: "uppercase"
              }}
            >
              <span style={{ fontSize: 14 }}>🛡️</span>
              <span>RISK REGISTER</span>
            </button>
          </div>
        </div>

        {/* Main Content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "28px 32px" }}>
          {active === "risks" ? (
            <div>
              <div style={{ marginBottom: 24 }}>
                <div style={{ fontSize: 10, letterSpacing: 4, color: "#FFD60A", marginBottom: 8 }}>🛡️ RISK REGISTER</div>
                <div style={{ fontSize: 20, color: "#fff", fontWeight: "bold" }}>Demo Day Risk Mitigation</div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {riskItems.map((r, i) => (
                  <div
                    key={i}
                    onClick={() => setExpandedRisk(expandedRisk === i ? null : i)}
                    style={{
                      background: "#0d0d1a",
                      border: "1px solid",
                      borderColor: expandedRisk === i ? "#FFD60A" : "#1e1e2e",
                      padding: "16px 20px",
                      cursor: "pointer",
                      transition: "border-color 0.15s"
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <div style={{ fontSize: 12, color: "#e8e8e8", letterSpacing: 1 }}>{r.risk}</div>
                      <div style={{
                        fontSize: 9, color: "#FFD60A", letterSpacing: 2,
                        border: "1px solid #FFD60A22", padding: "2px 8px",
                        marginLeft: 12, flexShrink: 0
                      }}>RISK {i + 1}</div>
                    </div>
                    {expandedRisk === i && (
                      <div style={{
                        marginTop: 12, paddingTop: 12,
                        borderTop: "1px solid #1e1e2e",
                        fontSize: 11, color: "#00cc94", lineHeight: 1.7
                      }}>
                        → MITIGATION: {r.fix}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : current ? (
            <div>
              {/* Section header */}
              <div style={{ marginBottom: 28 }}>
                <div style={{
                  fontSize: 10, letterSpacing: 4,
                  color: current.color, marginBottom: 8
                }}>
                  {current.icon} {current.label}
                </div>
                <div style={{ width: 40, height: 2, background: current.color }} />
              </div>

              {/* Cards grid */}
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
                gap: 16
              }}>
                {current.items.map((item, i) => (
                  <div
                    key={i}
                    style={{
                      background: "#0d0d1a",
                      border: `1px solid ${current.color}22`,
                      padding: "20px",
                      position: "relative",
                      transition: "border-color 0.2s",
                    }}
                    onMouseEnter={e => e.currentTarget.style.borderColor = current.color + "88"}
                    onMouseLeave={e => e.currentTarget.style.borderColor = current.color + "22"}
                  >
                    <div style={{
                      position: "absolute", top: 12, right: 12,
                      fontSize: 9, color: current.accent,
                      border: `1px solid ${current.color}44`,
                      padding: "2px 7px", letterSpacing: 2,
                      background: current.color + "11"
                    }}>
                      {item.tag}
                    </div>
                    <div style={{
                      fontSize: 12, fontWeight: "bold",
                      color: "#fff", marginBottom: 10,
                      lineHeight: 1.4, paddingRight: 60,
                      letterSpacing: 0.5
                    }}>
                      {item.title}
                    </div>
                    <div style={{
                      fontSize: 11, color: "#888",
                      lineHeight: 1.75, letterSpacing: 0.3
                    }}>
                      {item.body}
                    </div>
                  </div>
                ))}
              </div>

              {/* Additional section-specific content */}
              {active === "scoring" && (
                <div style={{
                  marginTop: 24, background: "#0d0d1a",
                  border: "1px solid #8B00FF44", padding: 20
                }}>
                  <div style={{ fontSize: 10, letterSpacing: 3, color: "#8B00FF", marginBottom: 12 }}>
                    PRIORITY BANDS
                  </div>
                  {[
                    { band: "CRITICAL", range: "> 18", color: "#FF4B1F", action: "Immediate shutdown/isolation" },
                    { band: "HIGH", range: "12–18", color: "#FF8C00", action: "Schedule within 48hrs, raise procurement alert" },
                    { band: "MEDIUM", range: "7–12", color: "#FFD60A", action: "Monitor closely, plan within 2 weeks" },
                    { band: "LOW", range: "< 7", color: "#00cc94", action: "Flag for next scheduled maintenance window" }
                  ].map((b, i) => (
                    <div key={i} style={{
                      display: "flex", alignItems: "center", gap: 16,
                      padding: "8px 0",
                      borderBottom: i < 3 ? "1px solid #1e1e2e" : "none"
                    }}>
                      <div style={{
                        width: 80, flexShrink: 0,
                        fontSize: 10, fontWeight: "bold",
                        color: b.color, letterSpacing: 2
                      }}>{b.band}</div>
                      <div style={{
                        width: 50, flexShrink: 0,
                        fontSize: 11, color: "#555"
                      }}>{b.range}</div>
                      <div style={{ fontSize: 11, color: "#777" }}>{b.action}</div>
                    </div>
                  ))}
                </div>
              )}

              {active === "techstack" && (
                <div style={{
                  marginTop: 24, background: "#0d0d1a",
                  border: "1px solid #2D6A4F44", padding: 20
                }}>
                  <div style={{ fontSize: 10, letterSpacing: 3, color: "#40916c", marginBottom: 12 }}>
                    DEMO ASSETS TO SIMULATE
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
                    {[
                      { id: "HYD-VALVE-07", desc: "Recurring seal failures", risk: "HIGH" },
                      { id: "CONV-BELT-03", desc: "Bearing degradation in progress", risk: "CRITICAL" },
                      { id: "FURNACE-01", desc: "Hot strip mill, process-critical", risk: "MEDIUM" },
                      { id: "PUMP-12", desc: "Cooling water pump, healthy", risk: "LOW" },
                      { id: "CRANE-09", desc: "Intermittent electrical fault", risk: "HIGH" }
                    ].map((a, i) => (
                      <div key={i} style={{
                        background: "#080810",
                        border: "1px solid #1e1e2e",
                        padding: "10px 14px",
                        minWidth: 160
                      }}>
                        <div style={{ fontSize: 11, color: "#40916c", fontWeight: "bold", letterSpacing: 1 }}>{a.id}</div>
                        <div style={{ fontSize: 10, color: "#555", marginTop: 4 }}>{a.desc}</div>
                        <div style={{
                          marginTop: 6, fontSize: 9, letterSpacing: 2,
                          color: a.risk === "CRITICAL" ? "#FF4B1F" :
                            a.risk === "HIGH" ? "#FF8C00" :
                              a.risk === "MEDIUM" ? "#FFD60A" : "#00cc94"
                        }}>{a.risk}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
