"""
Generate mock industrial data for the Maintenance Wizard.

Produces an asset-tagged dataset for a heavy steel manufacturing plant:
  - asset_registry.csv      : the canonical asset list (the Semantic Layer spine)
  - aliases.json            : conversational jargon -> formal asset_id (fuzzy matching)
  - sensor_logs.csv         : time-series sensor readings per asset (ML input)
  - delay_logs.csv          : production delay events tied to assets
  - incident_records.csv    : historical breakdown / failure analysis records
  - spare_parts_inventory.csv: ERP stock + procurement lead times
  - manuals/                 : per-asset SOP/manual markdown (RAG corpus)

Every row is tagged with an `asset_id` so the whole system stays asset-centric.
Run:  python data/generate_mock_data.py
"""
from __future__ import annotations
import csv
import json
import os
import random
from datetime import datetime, timedelta

random.seed(42)

HERE = os.path.dirname(os.path.abspath(__file__))
MANUALS_DIR = os.path.join(HERE, "manuals")
os.makedirs(MANUALS_DIR, exist_ok=True)

# --------------------------------------------------------------------------
# 1. Asset registry  (the canonical spine of the Semantic Layer)
# --------------------------------------------------------------------------
# criticality: 1 (low) .. 5 (process-critical, stops the whole line)
ASSETS = [
    # asset_id,        name,                       type,         line,      criticality
    ("FURNACE-01",     "Electric Arc Furnace 1",   "furnace",    "Melt Shop",   5),
    ("LADLE-02",       "Ladle Refining Furnace 2", "furnace",    "Melt Shop",   5),
    ("CONV-BELT-03",   "Sinter Conveyor Belt 3",   "conveyor",   "Sinter",      4),
    ("CONV-BELT-08",   "Charge Conveyor Belt 8",   "conveyor",   "Melt Shop",   3),
    ("PUMP-12",        "Cooling Water Pump 12",     "pump",       "Utilities",   4),
    ("PUMP-19",        "Hydraulic Supply Pump 19",  "pump",       "Caster",      3),
    ("HYD-VALVE-07",   "Mold Hydraulic Valve 7",    "valve",      "Caster",      4),
    ("ROLL-MILL-04",   "Hot Strip Roll Mill 4",     "mill",       "Rolling",     5),
    ("ROLL-MILL-11",   "Cold Roll Stand 11",        "mill",       "Rolling",     4),
    ("GEARBOX-05",     "Mill Drive Gearbox 5",      "gearbox",    "Rolling",     4),
    ("COMPRESSOR-09",  "Plant Air Compressor 9",    "compressor", "Utilities",   3),
    ("CRANE-06",       "Charge Bay EOT Crane 6",    "crane",      "Melt Shop",   3),
]

ASSET_IDS = [a[0] for a in ASSETS]

with open(os.path.join(HERE, "asset_registry.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["asset_id", "name", "type", "line", "criticality", "install_date", "manufacturer"])
    mfrs = ["Siemens VAI", "Danieli", "SMS Group", "Primetals", "ABB", "Flowserve"]
    for aid, name, typ, line, crit in ASSETS:
        install = datetime(2015, 1, 1) + timedelta(days=random.randint(0, 2500))
        w.writerow([aid, name, typ, line, crit, install.strftime("%Y-%m-%d"),
                    random.choice(mfrs)])

# --------------------------------------------------------------------------
# 2. Alias dictionary  (fuzzy / jargon resolution -> formal asset_id)
# --------------------------------------------------------------------------
ALIASES = {
    "arc furnace": "FURNACE-01",
    "eaf": "FURNACE-01",
    "big furnace": "FURNACE-01",
    "melt furnace": "FURNACE-01",
    "ladle furnace": "LADLE-02",
    "lrf": "LADLE-02",
    "sinter belt": "CONV-BELT-03",
    "sinter conveyor": "CONV-BELT-03",
    "belt 3": "CONV-BELT-03",
    "charge belt": "CONV-BELT-08",
    "belt 8": "CONV-BELT-08",
    "cooling pump": "PUMP-12",
    "water pump": "PUMP-12",
    "big pump": "PUMP-12",
    "hydraulic pump": "PUMP-19",
    "caster pump": "PUMP-19",
    "mold valve": "HYD-VALVE-07",
    "that valve that keeps leaking": "HYD-VALVE-07",
    "leaky valve": "HYD-VALVE-07",
    "hot mill": "ROLL-MILL-04",
    "strip mill": "ROLL-MILL-04",
    "roll mill": "ROLL-MILL-04",
    "cold mill": "ROLL-MILL-11",
    "roll stand": "ROLL-MILL-11",
    "gearbox": "GEARBOX-05",
    "mill gearbox": "GEARBOX-05",
    "air compressor": "COMPRESSOR-09",
    "compressor": "COMPRESSOR-09",
    "crane": "CRANE-06",
    "eot crane": "CRANE-06",
    "charge crane": "CRANE-06",
}
with open(os.path.join(HERE, "aliases.json"), "w") as f:
    json.dump(ALIASES, f, indent=2)

# --------------------------------------------------------------------------
# 3. Sensor logs (the ML input). Each asset has a "health" trajectory.
# --------------------------------------------------------------------------
# We give each asset a hidden degradation state so the ML model has signal.
# Features: temperature(C), vibration(mm/s), pressure(bar), humidity(%), power(kW)
# Label (computed later in train_model): remaining useful life (days).

# Per-type nominal operating points (mean, std) for healthy operation.
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

# Hidden health 0..1 (1 = perfect). Degraded assets drift sensors upward.
HEALTH = {
    "FURNACE-01": 0.85, "LADLE-02": 0.92, "CONV-BELT-03": 0.18, "CONV-BELT-08": 0.74,
    "PUMP-12": 0.38, "PUMP-19": 0.66, "HYD-VALVE-07": 0.30, "ROLL-MILL-04": 0.42,
    "ROLL-MILL-11": 0.80, "GEARBOX-05": 0.28, "COMPRESSOR-09": 0.71, "CRANE-06": 0.88,
}
TYPE_OF = {a[0]: a[2] for a in ASSETS}

def degraded(value_mean, value_std, health, factor):
    """Lower health -> higher mean + higher variance (more erratic)."""
    drift = (1 - health) * factor
    noise = random.gauss(0, value_std * (1 + (1 - health)))
    return round(value_mean * (1 + drift) + noise, 2)

rows = []
now = datetime(2026, 6, 6, 6, 0, 0)
for aid in ASSET_IDS:
    typ = TYPE_OF[aid]
    nom = NOMINAL[typ]
    h = HEALTH[aid]
    # 120 hourly readings per asset (most recent last)
    N = 120
    for i in range(N):
        ts = now - timedelta(hours=(N - i))
        # health slowly decays across the window for unhealthy assets
        h_t = max(0.05, h - (N - i) * 0.0020 * (1 - h))
        rows.append([
            ts.strftime("%Y-%m-%d %H:%M"), aid,
            degraded(*nom["temperature"], h_t, 0.45),
            degraded(*nom["vibration"], h_t, 1.20),
            degraded(*nom["pressure"], h_t, 0.15),
            round(random.gauss(nom["humidity"][0], nom["humidity"][1]), 1),
            degraded(*nom["power"], h_t, 0.25),
            round(h_t, 3),
        ])

with open(os.path.join(HERE, "sensor_logs.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["timestamp", "asset_id", "temperature", "vibration",
                "pressure", "humidity", "power", "health_index"])
    w.writerows(rows)

# --------------------------------------------------------------------------
# 4. Delay logs (production impact tied to assets)
# --------------------------------------------------------------------------
DELAY_CODES = {
    "MECH": "Mechanical failure",
    "HYDR": "Hydraulic fault",
    "ELEC": "Electrical fault",
    "LUBE": "Lubrication issue",
    "WEAR": "Component wear",
    "PROC": "Process upset",
}
with open(os.path.join(HERE, "delay_logs.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["delay_id", "asset_id", "date", "delay_code", "delay_desc",
                "downtime_min", "tonnage_lost"])
    did = 1000
    for aid in ASSET_IDS:
        # unhealthy assets generate more delays
        n = int(round((1 - HEALTH[aid]) * 8)) + random.randint(0, 2)
        for _ in range(n):
            d = now - timedelta(days=random.randint(1, 120))
            code = random.choice(list(DELAY_CODES))
            dt = random.randint(15, 320)
            w.writerow([f"DLY-{did}", aid, d.strftime("%Y-%m-%d"), code,
                        DELAY_CODES[code], dt, round(dt * random.uniform(0.4, 1.8), 1)])
            did += 1

# --------------------------------------------------------------------------
# 5. Incident / failure-analysis records (historical root causes)
# --------------------------------------------------------------------------
INCIDENTS = [
    ("CONV-BELT-03", "Drive bearing seizure", "Bearing ran dry due to blocked grease line; vibration climbed for 6 days before seizure.", "Replaced bearing, cleared grease line, added vibration alarm at 6.0 mm/s."),
    ("CONV-BELT-03", "Belt mistracking", "Idler misalignment caused edge wear and repeated trips.", "Re-aligned idlers, replaced 12m belt section."),
    ("PUMP-12", "Mechanical seal failure", "Seal face wear allowed coolant leak; temperature rose 18%.", "Replaced cartridge seal, flushed cooling jacket."),
    ("PUMP-12", "Impeller cavitation", "Suction strainer fouling dropped inlet pressure, cavitation pitted impeller.", "Cleaned strainer, balanced and refit impeller."),
    ("HYD-VALVE-07", "Spool sticking", "Contaminated oil caused mold valve spool to stick, casting defects appeared.", "Replaced spool, fitted 10-micron filter, drained reservoir."),
    ("HYD-VALVE-07", "Internal leakage", "Worn seals caused pressure droop and slow mold oscillation.", "Reseal kit fitted, verified oscillation profile."),
    ("GEARBOX-05", "Tooth pitting", "Oil analysis showed iron particles; pinion pitting from overload.", "Replaced pinion, switched to ISO VG320 oil, set load trip."),
    ("ROLL-MILL-04", "Work roll thermal crack", "Cooling spray header partially blocked, roll surface cracked.", "Reground roll, cleared spray header nozzles."),
    ("FURNACE-01", "Electrode arm overheating", "Clamp contact resistance rose, arm temperature elevated.", "Cleaned clamp contacts, retorqued to spec."),
    ("PUMP-19", "Coupling wear", "Elastomeric coupling degraded, vibration rose on caster supply.", "Replaced coupling element, re-aligned to 0.05mm."),
]
with open(os.path.join(HERE, "incident_records.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["incident_id", "asset_id", "title", "root_cause", "resolution", "date"])
    for i, (aid, title, rc, res) in enumerate(INCIDENTS, start=1):
        d = now - timedelta(days=random.randint(40, 700))
        w.writerow([f"INC-{200 + i}", aid, title, rc, res, d.strftime("%Y-%m-%d")])

# --------------------------------------------------------------------------
# 6. Spare parts inventory (ERP: stock + procurement lead times)
# --------------------------------------------------------------------------
PARTS = [
    # part_no, asset_id, description, qty_on_hand, reorder_pt, lead_time_days, unit_cost
    ("BRG-6314",   "CONV-BELT-03", "Drive-end roller bearing 6314",    0, 2, 21, 480),
    ("BELT-SNT-3", "CONV-BELT-03", "Sinter belt section 12m",          1, 1, 35, 5200),
    ("SEAL-CART-12","PUMP-12",     "Cartridge mechanical seal 65mm",   3, 2, 7,  920),
    ("IMP-12",     "PUMP-12",      "Closed impeller 65mm",             1, 1, 28, 2400),
    ("SPOOL-HV7",  "HYD-VALVE-07", "Proportional valve spool kit",     0, 1, 18, 1650),
    ("RESEAL-HV7", "HYD-VALVE-07", "Valve reseal kit",                 4, 2, 5,  210),
    ("PINION-G5",  "GEARBOX-05",   "Drive pinion 22T",                 0, 1, 45, 7800),
    ("OIL-VG320",  "GEARBOX-05",   "ISO VG320 gear oil 200L",          2, 2, 4,  640),
    ("ROLL-WR4",   "ROLL-MILL-04", "Work roll forged",                 1, 1, 60, 22000),
    ("CPLG-19",    "PUMP-19",      "Elastomeric coupling element",     5, 2, 6,  180),
    ("ELEC-CLMP1", "FURNACE-01",   "Electrode clamp contact pad",      6, 3, 14, 540),
    ("FILT-10MIC", "HYD-VALVE-07", "10-micron hydraulic filter",       8, 4, 3,  85),
]
with open(os.path.join(HERE, "spare_parts_inventory.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["part_no", "asset_id", "description", "qty_on_hand",
                "reorder_point", "lead_time_days", "unit_cost_usd"])
    for p in PARTS:
        w.writerow(list(p))

# --------------------------------------------------------------------------
# 7. Per-asset manuals / SOPs (the RAG corpus, asset-tagged markdown)
# --------------------------------------------------------------------------
MANUALS = {
    "CONV-BELT-03": ("Sinter Conveyor Belt 3 - Maintenance Manual", """
## SOP-CONV-03: Drive Bearing Inspection & Replacement

### Safety Isolation (mandatory before any work)
1. Stop the belt at the local HMI and select LOCAL/OFF.
2. Apply Lock-Out/Tag-Out (LOTO) on the drive motor isolator MCC-S3-07.
3. Verify zero energy: confirm motor cannot start and gravity take-up is chocked.
4. Confirm with the shift supervisor before removing any guard.

### Condition limits
- Vibration alarm: 6.0 mm/s RMS at drive-end bearing. Trip: 8.0 mm/s.
- Bearing temperature warning: 75 C. Trip: 90 C.
- Grease line pressure must be > 1.0 bar during auto-lube cycle.

### Bearing replacement procedure
1. Remove drive guard (after LOTO verified).
2. Slacken belt via take-up, mark roller position.
3. Withdraw bearing 6314 (part BRG-6314) using bearing puller.
4. Inspect shaft seat for fretting; clean grease line and verify flow.
5. Fit new bearing, hand-pack with lithium-complex EP2 grease.
6. Re-tension belt to 1.2 kN, re-align idlers within 0.5 mm.
7. Reinstate guard, remove LOTO, run at 25% for 10 min and recheck vibration.

### Known failure modes
- Dry-running bearing seizure from blocked grease line (see INC-201).
- Belt mistracking from idler misalignment causing edge wear.
"""),
    "PUMP-12": ("Cooling Water Pump 12 - Maintenance Manual", """
## SOP-PUMP-12: Mechanical Seal & Impeller Service

### Safety Isolation
1. Close suction and discharge valves; tag closed.
2. LOTO motor isolator MCC-U-12; verify zero energy.
3. Drain pump casing to the utilities sump; confirm zero pressure on gauge.

### Condition limits
- Bearing/casing temperature warning: 72 C. Trip: 85 C.
- Vibration warning: 4.5 mm/s. Trip: 6.5 mm/s.
- Discharge pressure must stay within 6.0-7.0 bar.

### Mechanical seal replacement
1. After isolation and drain, remove coupling guard and back pull-out assembly.
2. Extract cartridge seal SEAL-CART-12; inspect seal faces for wear/heat checking.
3. Flush cooling jacket; verify no scaling.
4. Fit new cartridge seal to torque spec; do not pre-compress by hand.
5. Re-align coupling to 0.05 mm; reinstate guard.
6. Open valves, vent air, remove LOTO, run and confirm pressure 6.0-7.0 bar.

### Known failure modes
- Seal face wear -> coolant leak -> temperature rise (see INC-203).
- Suction strainer fouling -> cavitation -> impeller pitting (see INC-204).
"""),
    "HYD-VALVE-07": ("Mold Hydraulic Valve 7 - Maintenance Manual", """
## SOP-HYD-07: Proportional Valve Service (Mold Oscillation)

### Safety Isolation
1. Place caster in MAINT mode; stop mold oscillation.
2. Bleed hydraulic accumulator to 0 bar; verify on local gauge.
3. LOTO hydraulic power unit HPU-CAST-2.
4. Catch-tray under valve; oil is hot - allow to cool below 40 C.

### Condition limits
- System pressure band: 170-190 bar. Droop below 165 bar indicates internal leak.
- Oil cleanliness: ISO 4406 18/16/13 or better. Replace 10-micron filter (FILT-10MIC) on alarm.

### Spool replacement
1. After isolation/bleed, disconnect electrical connector and mark ports.
2. Remove proportional valve; fit spool kit SPOOL-HV7 in clean conditions.
3. Replace reseal kit RESEAL-HV7; never reuse seals.
4. Drain and refill reservoir if contamination found; fit new 10-micron filter.
5. Reinstate, restore pressure, verify mold oscillation profile against setpoint.

### Known failure modes
- Contaminated oil -> spool sticking -> casting surface defects (see INC-205).
- Worn seals -> internal leakage -> pressure droop -> slow oscillation (see INC-206).
"""),
    "GEARBOX-05": ("Mill Drive Gearbox 5 - Maintenance Manual", """
## SOP-GBX-05: Gearbox Condition & Pinion Service

### Safety Isolation
1. Stop the mill drive; LOTO main drive isolator and auxiliary lube pump.
2. Verify zero energy and that the drive train cannot rotate.

### Condition limits
- Oil temperature warning: 80 C. Trip: 95 C.
- Vibration warning: 4.0 mm/s. Trip: 5.5 mm/s.
- Oil analysis iron content > 150 ppm indicates tooth wear - investigate.

### Pinion inspection / replacement
1. Drain oil; take sample for analysis before draining if possible.
2. Open inspection cover; check teeth for pitting/spalling.
3. If pitting > 10% of contact face, replace pinion PINION-G5.
4. Refill with ISO VG320 oil (OIL-VG320); set overload trip.

### Known failure modes
- Overload tooth pitting; iron particles in oil (see INC-207).
"""),
    "ROLL-MILL-04": ("Hot Strip Roll Mill 4 - Maintenance Manual", """
## SOP-MILL-04: Work Roll & Cooling System

### Safety Isolation
1. Stop mill, LOTO main and screw-down drives.
2. Isolate cooling water header; relieve pressure.

### Condition limits
- Roll surface temperature warning: 85 C. Cooling spray flow must be > 90% nominal.
- Vibration warning at backup bearing: 5.0 mm/s.

### Work roll change
1. After isolation, retract screw-down; use roll-change carriage.
2. Inspect roll for thermal cracks; if cracked, send roll ROLL-WR4 for regrind.
3. Clear cooling spray header nozzles; verify uniform spray pattern.
4. Fit reground/new roll, set roll gap, verify cooling flow before restart.

### Known failure modes
- Blocked spray header -> thermal cracking of roll surface (see INC-208).
"""),
    "FURNACE-01": ("Electric Arc Furnace 1 - Maintenance Manual", """
## SOP-EAF-01: Electrode Arm & Clamp Maintenance

### Safety Isolation
1. Power off transformer; LOTO HV isolator (HV permit required).
2. Verify de-energized with HV tester; earth the electrodes.

### Condition limits
- Electrode arm temperature warning: 70 C above ambient at clamp.
- Clamp contact resistance must be within spec; high resistance causes heating.

### Clamp service
1. After HV isolation/earthing, inspect clamp contact pads (ELEC-CLMP1).
2. Clean oxidation, replace pads if pitted, retorque to spec.
3. Verify cooling water flow to arm; check for leaks.

### Known failure modes
- Clamp contact resistance rise -> arm overheating (see INC-209).
"""),
    "PUMP-19": ("Hydraulic Supply Pump 19 - Maintenance Manual", """
## SOP-PUMP-19: Coupling & Alignment

### Safety Isolation
1. Stop pump, LOTO motor isolator; verify zero energy.
2. Relieve hydraulic pressure to 0 bar.

### Condition limits
- Vibration warning: 4.0 mm/s (coupling wear shows as 1x/2x rpm peaks).
- Discharge pressure band per caster spec.

### Coupling replacement
1. Remove coupling guard; inspect elastomeric element (CPLG-19) for cracks.
2. Replace element; re-align shafts to 0.05 mm TIR.
3. Reinstate guard; run and confirm vibration < 3.0 mm/s.

### Known failure modes
- Elastomeric coupling degradation -> rising vibration (see INC-210).
"""),
}

# generic stub manual for assets without a detailed one
GENERIC = """
## SOP-GENERIC: Standard Maintenance Procedure

### Safety Isolation
1. Stop the asset at the local control; apply LOTO on the supply isolator.
2. Verify zero energy before removing any guard.

### Condition limits
- Follow OEM vibration and temperature alarm setpoints.
- Record all readings in the digital logbook.

### Procedure
1. Inspect for abnormal noise, heat, leakage or vibration.
2. Compare readings against nominal operating band.
3. Escalate to specialist if outside limits; do not run to failure.
"""

for aid in ASSET_IDS:
    if aid in MANUALS:
        title, body = MANUALS[aid]
    else:
        name = next(a[1] for a in ASSETS if a[0] == aid)
        title, body = f"{name} - Maintenance Manual", GENERIC
    with open(os.path.join(MANUALS_DIR, f"{aid}.md"), "w") as f:
        f.write(f"# {title}\n\n*Asset ID: {aid}*\n{body}")

print("Mock data generated:")
for fn in ["asset_registry.csv", "aliases.json", "sensor_logs.csv", "delay_logs.csv",
           "incident_records.csv", "spare_parts_inventory.csv"]:
    p = os.path.join(HERE, fn)
    print(f"  {fn:28s} {os.path.getsize(p):>7} bytes")
print(f"  manuals/                     {len(os.listdir(MANUALS_DIR))} files")
