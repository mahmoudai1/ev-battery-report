import json
from statistics import median

def dod(start_soc, end_soc):
    s = min(max(start_soc, 0.0), 1.0)
    e = min(max(end_soc, 0.0), 1.0)
    return max(0.0, s - e)

def deep_capacity_estimates(discharge_events):
    caps = []
    for ev in discharge_events:
        s = ev.get("start_soc")
        e = ev.get("end_soc")
        en = ev.get("energy_kwh")
        if s is None or e is None or en is None:
            continue
        d = dod(s, e)
        if d >= 0.60 and d > 0:
            cap = en / d
            if 5.0 <= cap <= 200.0:
                caps.append(cap)
    # use top 3 deepest if there are many
    return caps[:3] if len(caps) <= 3 else sorted(caps, reverse=True)[:3]

def soh_percent(log):
    nom = log.get("nominal_capacity_kwh")
    if not nom or nom <= 0:
        return None
    caps = deep_capacity_estimates(log.get("discharge_events", []))
    if not caps:
        return None
    return round(100.0 * median(caps) / nom, 2)

def equivalent_full_cycles(log):
    total = 0.0
    for ev in log.get("discharge_events", []):
        s = ev.get("start_soc")
        e = ev.get("end_soc")
        if s is None or e is None:
            continue
        total += dod(s, e)
    return round(total, 2)

def anomalies(log):
    # Simple checks over time series rows
    out = {
        "voltage_imbalance": [],
        "overheating": [],
        "thermal_gradient": []
    }
    for row in log.get("time_series", []):
        ts = row.get("timestamp")
        cv = row.get("cell_voltages_v", [])
        ct = row.get("cell_temps_c", [])

        if not ts or not cv or not ct:
            continue

        dv = max(cv) - min(cv)
        if dv > 0.10:
            out["voltage_imbalance"].append(
                {"timestamp": ts, "severity": "critical",
                 "delta_v": round(dv, 4)}
            )
        elif dv > 0.05:
            out["voltage_imbalance"].append(
                {"timestamp": ts, "severity": "warning",
                 "delta_v": round(dv, 4)}
            )

        tmax = max(ct)
        tmin = min(ct)

        if tmax > 60.0:
            out["overheating"].append(
                {"timestamp": ts, "severity": "critical",
                 "max_c": round(tmax, 2)}
            )
        elif tmax > 55.0:
            out["overheating"].append(
                {"timestamp": ts, "severity": "warning",
                 "max_c": round(tmax, 2)}
            )

        if (tmax - tmin) > 15.0:
            out["thermal_gradient"].append(
                {"timestamp": ts, "severity": "warning",
                 "delta_c": round(tmax - tmin, 2)}
            )

    return out

def build_report(log):
    return {
        "vehicle_id": log.get("vehicle_id", "unknown"),
        "soh_percent": soh_percent(log),
        "equivalent_full_cycles": equivalent_full_cycles(log),
        "event_counts": {
            "discharge": len(log.get("discharge_events", [])),
            "charge": len(log.get("charge_events", [])),
        },
        "anomalies": anomalies(log),
    }

def main():
    import argparse, sys
    p = argparse.ArgumentParser()
    p.add_argument("input_json")
    args = p.parse_args()

    with open(args.input_json, "r") as f:
        log = json.load(f)

    rep = build_report(log)
    json.dump(rep, sys.stdout, indent=2)
    print()

if __name__ == "__main__":
    main()
