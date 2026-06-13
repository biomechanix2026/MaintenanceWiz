"""
Central configuration for the Maintenance Wizard.

This is the single source of truth for paths, healthy operating baselines
(the numeric backbone of the Semantic Layer), alarm thresholds and the
deterministic risk-scoring weights. Both the data generator and the ML /
agent layers import from here so definitions never drift.
"""
import os

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
MANUALS_DIR = os.path.join(DATA_DIR, "manuals")
ML_ARTIFACTS_DIR = os.path.join(ROOT, "ml", "artifacts")
VECTORSTORE_DIR = os.path.join(ROOT, "knowledge", "store")

ASSET_REGISTRY_CSV = os.path.join(DATA_DIR, "asset_registry.csv")
ALIASES_JSON = os.path.join(DATA_DIR, "aliases.json")
SENSOR_LOGS_CSV = os.path.join(DATA_DIR, "sensor_logs.csv")
DELAY_LOGS_CSV = os.path.join(DATA_DIR, "delay_logs.csv")
INCIDENTS_CSV = os.path.join(DATA_DIR, "incident_records.csv")
PARTS_CSV = os.path.join(DATA_DIR, "spare_parts_inventory.csv")
LOGBOOK_CSV = os.path.join(DATA_DIR, "digital_logbook.csv")
FEEDBACK_CSV = os.path.join(DATA_DIR, "feedback.csv")

# --------------------------------------------------------------------------
# Feature set used by the prognostic model (order matters - it is the
# contract between training and inference).
# --------------------------------------------------------------------------
SENSOR_FEATURES = ["temperature", "vibration", "pressure", "humidity", "power"]

# Healthy operating baselines per asset type: (mean, std).
# The model is trained on per-type *deviations* so a single model works
# across furnaces, pumps, valves etc. and SHAP stays interpretable.
NOMINAL = {
    "furnace":    {"temperature": (640, 25), "vibration": (2.0, 0.4), "pressure": (3.0, 0.3), "humidity": (28, 4), "power": (820, 40)},
    "conveyor":   {"temperature": (55, 6),   "vibration": (3.5, 0.6), "pressure": (1.2, 0.2), "humidity": (45, 6), "power": (110, 12)},
    "pump":       {"temperature": (62, 7),   "vibration": (2.8, 0.5), "pressure": (6.5, 0.5), "humidity": (40, 5), "power": (160, 15)},
    "valve":      {"temperature": (58, 6),   "vibration": (1.8, 0.3), "pressure": (180, 12), "humidity": (35, 5), "power": (12, 2)},
    "mill":       {"temperature": (78, 8),   "vibration": (4.2, 0.8), "pressure": (210, 15), "humidity": (38, 5), "power": (1450, 70)},
    "gearbox":    {"temperature": (70, 7),   "vibration": (3.0, 0.6), "pressure": (4.0, 0.4), "humidity": (33, 4), "power": (480, 30)},
    "compressor": {"temperature": (66, 6),   "vibration": (2.6, 0.5), "pressure": (9.0, 0.6), "humidity": (42, 5), "power": (240, 20)},
    "crane":      {"temperature": (48, 5),   "vibration": (2.2, 0.5), "pressure": (2.5, 0.3), "humidity": (44, 6), "power": (95, 10)},
}

# Max modelled useful life in days (RUL = health_index * this).
MAX_RUL_DAYS = 120

# --------------------------------------------------------------------------
# Deterministic risk scoring (Step 4 of the execution pipeline)
# Priority Score = weighted blend, 0..100. Higher = more urgent.
# --------------------------------------------------------------------------
RISK_WEIGHTS = {
    "rul": 0.40,           # how soon failure is expected
    "criticality": 0.30,   # process impact if it fails
    "delay_history": 0.15, # how much downtime it has already caused
    "spares": 0.15,        # whether we can actually fix it in time
}

# Priority band thresholds on the 0..100 score.
PRIORITY_BANDS = [
    (80, "CRITICAL"),
    (60, "HIGH"),
    (40, "MEDIUM"),
    (0,  "LOW"),
]

# Auto-alert fires at/above this score.
ALERT_THRESHOLD = 80

# Role-based alert routing (OE-06). When an alert has no explicit recipient,
# it is routed to a role by severity: critical -> shift supervisor, high ->
# reliability engineering, otherwise the maintenance team.
ALERT_ROLES = {
    "maintenance": "maintenance-team@plant.local",
    "reliability": "reliability-engineering@plant.local",
    "supervisor":  "shift-supervisor@plant.local",
}

# --------------------------------------------------------------------------
# Independent abnormality detection
# --------------------------------------------------------------------------
# These thresholds are applied to current sensor deviations vs NOMINAL, separate
# from the RUL regressor. This closes the dynamic abnormality / early-warning
# objective without changing the deterministic priority score contract.
ANOMALY_WARNING_Z = 2.0
ANOMALY_CRITICAL_Z = 3.5
ANOMALY_TREND_Z = 0.75

# --------------------------------------------------------------------------
# Feedback loop policy
# --------------------------------------------------------------------------
# Engineer feedback ALWAYS re-indexes into the RAG corpus (advisory context).
# Whether it may also nudge the deterministic priority_score is opt-in and OFF
# by default, so the headline score stays grounded purely in the stated
# prioritisation basis (RUL, criticality, delay history, spares/lead time) and
# remains reproducible for the eval baseline. Enable with MW_APPLY_FEEDBACK_BIAS=1.
APPLY_FEEDBACK_BIAS = os.environ.get("MW_APPLY_FEEDBACK_BIAS", "0") == "1"

# --------------------------------------------------------------------------
# Plant topology (cascade / bottleneck graph)
# --------------------------------------------------------------------------
# Hybrid spec (see docs/superpowers/specs/2026-06-08-plant-cascade-graph-design.md):
# intra-line serial chains + consecutive-line bridges are DERIVED from the two
# structures below; cross-line utility dependencies are AUTHORED explicitly.
# Assets in the registry but absent here are isolated nodes (blast radius 0).
LINE_FLOW = ["Sinter", "Melt Shop", "Caster", "Rolling"]   # material backbone, ordered
LINE_ASSET_ORDER = {            # serial process order within each line
    "Sinter":    ["CONV-BELT-03"],
    "Melt Shop": ["CONV-BELT-08", "FURNACE-01", "LADLE-02"],
    "Caster":    ["PUMP-19", "HYD-VALVE-07"],
    "Rolling":   ["ROLL-MILL-04", "ROLL-MILL-11"],
}
UTILITY_EDGES = {               # explicit cross-line fan-out
    "PUMP-12":       ["FURNACE-01", "HYD-VALVE-07"],   # cooling water
    "COMPRESSOR-09": ["HYD-VALVE-07", "ROLL-MILL-04"], # plant air
    "GEARBOX-05":    ["ROLL-MILL-04"],                 # mechanical drive
    "CRANE-06":      ["FURNACE-01"],                   # charge handling
}
CASCADE_DECAY = 0.6    # per-hop attenuation of downstream weight
CASCADE_GAIN = 3.0     # blast-radius units -> system_priority points

# --------------------------------------------------------------------------
# Next-shift planner (crew-hour + spares constrained allocation)
# --------------------------------------------------------------------------
CREW_ROSTER_CSV = os.path.join(DATA_DIR, "crew_roster.csv")
JOB_TEMPLATES_CSV = os.path.join(DATA_DIR, "job_templates.csv")

# Mock CMMS: draft work orders are written here (opt-in artifact, like alerts/
# pre-shift reports). Drafts only - never an autonomous closure.
WORK_ORDERS_DIR = os.path.join(ROOT, "reports", "work_orders")
