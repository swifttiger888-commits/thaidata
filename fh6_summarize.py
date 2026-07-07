#!/usr/bin/env python3
"""
fh6_summarize.py - Forza Horizon 6 drag telemetry summariser for Ollama.

Takes a telemetry CSV, splits into individual drag runs, and outputs a
compact text summary you can paste directly into Ollama with your tuning
persona.

Usage:
    python3 fh6_summarize.py fh6-session.csv
    python3 fh6_summarize.py --show-columns fh6-session.csv   # inspect only

Assumptions (from the Forza Motorsport UDP telemetry packet spec):
    If the CSV has NO header row, ~45 columns are assumed in the order
    defined in HEADER_NAMES below.

    If your logger uses different columns, pass a CSV with a proper
    header row — the script will auto-detect.  Or edit HEADER_NAMES.

Features:
    - Detects whether the CSV has headers or not
    - Prints column names + preview for verification
    - Splits runs using speed-drop and time-gap heuristics
    - Estimates ET/trap at 1/4 and 1/2 mile via speed integration
    - Detects rev limiter hits, launch quality, gear usage
    - Formats output as a compact block ready to paste into Ollama
"""

import sys
import math

import pandas as pd

# ── Config — column names (headerless CSV fallback) ────────────────

HEADER_NAMES = [
    "IsRaceOn", "TimestampMs", "EngineMaxRpm", "EngineIdleRpm",
    "CurrentEngineRpm", "AccelX", "AccelY", "AccelZ",
    "VelX", "VelY", "VelZ",
    "AngVelX", "AngVelY", "AngVelZ",
    "Yaw", "Pitch", "Roll",
    "SuspTravelFL", "SuspTravelFR", "SuspTravelRL", "SuspTravelRR",
    "SlipRatioFL", "SlipRatioFR", "SlipRatioRL", "SlipRatioRR",
    "WheelRpmFL", "WheelRpmFR", "WheelRpmRL", "WheelRpmRR",
    "HandBrake", "IsStable", "Clutch", "SteerInput", "Steer",
    "Throttle", "Brake",
    "ContactFL", "ContactFR", "ContactRL", "ContactRR",
    "TirePresFL", "TirePresFR", "TirePresRL", "TirePresRR",
    "Speed",
]

# Field aliases recognised during auto-detect
ALIASES = {
    "speed": {"Speed", "speed", "ground_speed", "vehiclespeed",
              "car_speed", "Speed (mph)", "Speed (km/h)"},
    "rpm":   {"CurrentEngineRpm", "current_engine_rpm", "engine_rpm",
              "rpm", "EngineRPM", "EngineRpm"},
    "maxrpm": {"EngineMaxRpm", "engine_max_rpm", "max_rpm"},
    "throttle": {"Throttle", "throttle", "gas", "accelerator", "Accelerator"},
    "brake": {"Brake", "brake"},
    "accelz": {"AccelZ", "accel_z", "acceleration_z", "AccelerationZ"},
    "time":  {"TimestampMs", "timestamp_ms", "time", "Time",
              "timestamp", "Timestamp"},
    "slip":  {"SlipRatioFL", "slip_ratio_fl", "tire_slip_ratio_fl",
              "SlipRatioFrontLeft", "TireSlipRatioFrontLeft"},
    "gear":  {"Gear", "gear", "CurrentGear", "current_gear"},
}

# Run-detection heuristics
SPEED_NEAR_ZERO = 0.5        # m/s
MIN_RUN_DURATION_MS = 2000

# Drag distances
HALF_MILE_M = 804.672
QUARTER_MILE_M = 402.336


# ── Helpers ─────────────────────────────────────────────────────────

def speed_to_mph(v):
    """Convert m/s to mph."""
    return v * 2.23694


def find_col(col_map, key):
    return col_map.get(key)


def auto_detect_columns(df):
    """Map common field names to our internal keys."""
    col_map = {}
    for col in df.columns:
        cs = str(col).strip()
        for key, names in ALIASES.items():
            if cs in names:
                col_map[key] = col
                break
    # Guess speed from max-RPM col if all else fails
    if "speed" not in col_map:
        # Maybe Speed is stored as a column name in an unexpected case
        for col in df.columns:
            if "speed" in str(col).lower():
                col_map["speed"] = col
                break
    return col_map


def compute_distance(run_df, speed_col, time_col):
    """Integrate speed over time to estimate cumulative distance (m)."""
    dt = run_df[time_col].diff().fillna(0) / 1000.0
    return (run_df[speed_col] * dt).cumsum().fillna(0)


def estimate_et_and_trap(run_df, speed_col, time_col):
    """Estimate elapsed time and trap speed at 1/4 and 1/2 mile."""
    dist = compute_distance(run_df, speed_col, time_col).values
    speed = run_df[speed_col].values
    t = run_df[time_col].values / 1000.0

    def crossing(dist_arr, target_m):
        for i in range(1, len(dist_arr)):
            if dist_arr[i] >= target_m >= dist_arr[i - 1]:
                frac = (target_m - dist_arr[i - 1]) / (dist_arr[i] - dist_arr[i - 1])
                return t[i - 1] + frac * (t[i] - t[i - 1]), speed[i - 1] + frac * (speed[i] - speed[i - 1])
        return None, None

    start_t = t[0]
    results = {}
    for label, dist_m in [("1/4 mile", QUARTER_MILE_M), ("1/2 mile", HALF_MILE_M)]:
        et, trap_ms = crossing(dist - dist[0], dist_m)
        if et is not None:
            results[label] = {"ET_s": round(et - start_t, 3), "Trap_mph": round(speed_to_mph(trap_ms), 1)}
    return results


def detect_limiter_hit(run_df, rpm_col, maxrpm_col=None):
    r"""True if RPM saturates near max for 3+ consecutive samples."""
    if rpm_col not in run_df.columns:
        return None
    rpms = run_df[rpm_col].values
    ceiling = run_df[maxrpm_col].iloc[0] if (maxrpm_col and maxrpm_col in run_df.columns) else rpms.max()
    near = rpms >= ceiling * 0.97
    cnt = 0
    for v in near:
        cnt = cnt + 1 if v else 0
        if cnt >= 3:
            return True
    return False


def assess_launch(run_df, col_map):
    r"""Return a short phrase describing launch quality."""
    speed_col = find_col(col_map, "speed")
    accel_col = find_col(col_map, "accelz")
    slip_col = find_col(col_map, "slip")
    if len(run_df) < 3:
        return "too short"
    window = run_df.head(min(20, max(10, len(run_df) // 10)))

    spun = False
    if slip_col and slip_col in window.columns:
        if window[slip_col].abs().max() > 0.15:
            spun = True
    peak = None
    if accel_col and accel_col in window.columns:
        peak = window[accel_col].max()

    if spun:
        return "possible wheelspin"
    if peak is not None and peak < 7.0:
        return "possible bog"
    if speed_col and speed_col in run_df.columns:
        s10 = run_df[speed_col].iloc[min(15, len(run_df) - 1)]
        if s10 > 15:
            return "strong launch"
        if s10 < 8:
            return "slow pickup"
    return "neutral"


# ── Main ────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage:")
        print("  python3 fh6_summarize.py fh6-session.csv")
        print("  python3 fh6_summarize.py --show-columns fh6-session.csv")
        sys.exit(0)

    csv_path = sys.argv[1]
    show_only_columns = len(sys.argv) > 1 and sys.argv[1] == "--show-columns"
    if show_only_columns:
        csv_path = sys.argv[2]

    # ── Step 1: Read CSV ────────────────────────────────────────────
    try:
        df_preview = pd.read_csv(csv_path, nrows=0)
    except FileNotFoundError:
        print(f"❌  File not found: {csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌  Error reading CSV: {e}")
        sys.exit(1)

    has_headers = not all(
        c.startswith("Unnamed") for c in df_preview.columns
    ) and any(
        str(c).strip() in {"Speed", "speed", "CurrentEngineRpm", "rpm", "Gear",
                           "IsRaceOn", "TimestampMs", "AccelX", "Time", "time"}
        for c in df_preview.columns
    )

    if has_headers:
        df = pd.read_csv(csv_path)
        print(f"✔  CSV has headers: {list(df.columns)}")
    else:
        df = pd.read_csv(csv_path, header=None, names=HEADER_NAMES)
        print("‼  No header detected — using default column names:")
        for i, name in enumerate(HEADER_NAMES):
            print(f"   {i:2d}: {name}")

    print(f"\nRows: {len(df)}")
    print(f"\nFirst 3 rows (raw):")
    print(df.head(3).to_string())
    print()

    if show_only_columns:
        return

    # ── Step 2: Identify key columns ────────────────────────────────
    col_map = auto_detect_columns(df)

    missing_k = [k for k in ["speed", "rpm", "throttle", "time"] if k not in col_map]
    if missing_k:
        print(f"⚠  Missing key columns: {missing_k}")
        print("   Run detection will be limited.")
        if "speed" not in col_map and "rpm" not in col_map:
            print("\n❌  Need at least Speed or RPM. Showing raw data preview.")
            print(df.head(10).to_string())
            sys.exit(1)

    time_col = find_col(col_map, "time") or "TimestampMs"
    speed_col = find_col(col_map, "speed")
    rpm_col = find_col(col_map, "rpm")
    maxrpm_col = find_col(col_map, "maxrpm")
    gear_col = find_col(col_map, "gear")

    # ── Step 3: Split into runs ─────────────────────────────────────
    runs = []
    if speed_col and speed_col in df.columns:
        stopped = df[speed_col] < SPEED_NEAR_ZERO
        in_run = False
        boundaries = []
        for i in range(len(df)):
            if not in_run and not stopped.iloc[i]:
                run_start = i
                in_run = True
            elif in_run and stopped.iloc[i]:
                in_run = False
                if i - run_start > 5:
                    boundaries.append((run_start, i))
        if in_run and len(df) - run_start > 5:
            boundaries.append((run_start, len(df) - 1))

        for s, e in boundaries:
            snippet = df.iloc[s:e + 1].copy()
            if time_col in snippet.columns:
                dur = snippet[time_col].iloc[-1] - snippet[time_col].iloc[0]
                if dur < MIN_RUN_DURATION_MS:
                    continue
            runs.append(snippet)
    else:
        runs = [df]

    # ── Step 4: Analyse & print each run ────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"Detected {len(runs)} run(s)")
    print(f"{'=' * 60}\n")

    for idx, run_df in enumerate(runs):
        run_df = run_df.reset_index(drop=True)
        print(f"── Run {idx + 1} ──")

        if speed_col and speed_col in run_df.columns:
            max_spd = run_df[speed_col].max()
            trap = run_df[speed_col].iloc[-5:].max()
            print(f"  Max speed:  {speed_to_mph(max_spd):.1f} mph")
            print(f"  Trap speed: {speed_to_mph(trap):.1f} mph")

        if rpm_col and rpm_col in run_df.columns:
            print(f"  Max RPM:    {run_df[rpm_col].max():.0f}")
            if maxrpm_col and maxrpm_col in run_df.columns:
                print(f"  Engine max: {run_df[maxrpm_col].iloc[0]:.0f}")

        if gear_col and gear_col in run_df.columns:
            finish_gear = run_df[gear_col].iloc[-1]
            print(f"  Finish gear: {int(finish_gear)}")

        # ET / trap at measured distances
        if speed_col and time_col in run_df.columns:
            for dist_label, vals in estimate_et_and_trap(run_df, speed_col, time_col).items():
                print(f"  {dist_label}: ET {vals['ET_s']:.1f}s @ {vals['Trap_mph']:.0f} mph")

        # Limiter
        if rpm_col:
            hl = detect_limiter_hit(run_df, rpm_col, maxrpm_col)
            if hl:
                print(f"  ⚠  Hitting rev limiter before finish")
            elif hl is False:
                print(f"  ✓  Not hitting limiter")

        # Launch
        print(f"  Launch:     {assess_launch(run_df, col_map)}")

        # Duration
        if time_col in run_df.columns:
            dur_s = (run_df[time_col].iloc[-1] - run_df[time_col].iloc[0]) / 1000.0
            print(f"  Duration:   {dur_s:.1f}s  ({len(run_df)} samples)")
        print()

    # ── Step 5: Compact Ollama block ────────────────────────────────
    print(f"{'=' * 60}")
    print("OLLAMA PASTE SUMMARY")
    print(f"{'=' * 60}\n")

    for idx, run_df in enumerate(runs):
        run_df = run_df.reset_index(drop=True)
        lines = [f"Run {idx + 1}: Car = 2012 Nissan GT-R Black Edition FE (R35)"]

        if speed_col and speed_col in run_df.columns:
            trap = speed_to_mph(run_df[speed_col].iloc[-5:].max())
            mx = speed_to_mph(run_df[speed_col].max())
            lines.append(f"  Trap: {trap:.0f} mph  Max: {mx:.0f} mph")
        if rpm_col and rpm_col in run_df.columns:
            lines.append(f"  Max RPM: {run_df[rpm_col].max():.0f}")
        if gear_col and gear_col in run_df.columns:
            lines.append(f"  Finish gear: {int(run_df[gear_col].iloc[-1])}")
        if speed_col and time_col in run_df.columns:
            for dlab, vals in estimate_et_and_trap(run_df, speed_col, time_col).items():
                lines.append(f"  {dlab}: {vals['ET_s']:.1f}s @ {vals['Trap_mph']:.0f} mph")
        if rpm_col:
            if detect_limiter_hit(run_df, rpm_col, maxrpm_col):
                lines.append("  ⚠  Hitting rev limiter before finish")
        lines.append(f"  Launch: {assess_launch(run_df, col_map)}")
        # Duration as simple ET proxy
        if time_col in run_df.columns:
            dur = (run_df[time_col].iloc[-1] - run_df[time_col].iloc[0]) / 1000.0
            lines.append(f"  Full-run ET: ~{dur:.1f}s")

        print("\n".join(lines))
        print()

    # ── Step 6: Schema feedback ─────────────────────────────────────
    found = [k for k, v in col_map.items() if v is not None]
    for_fulls = {"speed", "rpm", "throttle", "time", "accelz", "slip", "gear"}
    missing = for_fulls - set(col_map.keys())
    if missing:
        print("── Schema notes ──")
        print(f"  Found: {sorted(found)}")
        print(f"  Best also: speed, rpm, throttle, time, accelZ, slip, gear")
        print(f"  Missing: {sorted(missing)}")
    else:
        print("── Schema OK — all expected fields present.")


if __name__ == "__main__":
    main()
