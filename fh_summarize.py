#!/usr/bin/env python3
"""
fh_summarize.py — Forza Horizon 6 drag telemetry summariser for Ollama.

Reads a telemetry CSV, splits into individual drag runs, and outputs a
compact text summary you paste into Ollama with your tuning persona.

Usage:
    python3 fh_summarize.py fh6-session.csv
    python3 fh_summarize.py --show-columns fh6-session.csv   # inspect only

Requires: pandas (pip3 install pandas)
"""

import sys
import math

import pandas as pd

# ── Column map (tuned to your CSV schema) ───────────────────────────
# Your header row uses these exact names:
COL_NAMES = {
    "speed":    "Speed",
    "rpm":      "CurrentEngineRpm",
    "maxrpm":   "EngineMaxRpm",
    "throttle": "Accel",           # 0–1 accelerator input
    "brake":    "Brake",           # 0–1 brake input
    "accelz":   "AccelerationZ",   # longitudinal G (forward/back)
    "time":     "TimestampMS",
    "slip":     "TireSlipRatioRearLeft",    # rear slip = most useful for drag
    "gear":     "Gear",
    "dist":     "DistanceTraveled",         # odometer in metres
}

# Run-detection thresholds
SPEED_NEAR_ZERO = 1.0       # mph — below this = stopped
MIN_RUN_SAMPLES = 10        # ignore tiny snippets

# Drag distances (metres)
HALF_MILE_M = 804.672
QUARTER_MILE_M = 402.336

# ── Helpers ─────────────────────────────────────────────────────────

def mph_to_ms(mph):
    return mph * 0.44704

def ms_to_mph(ms):
    return ms * 2.23694

def detect_columns(df):
    """Map CSV columns to internal names.  Returns col_map dict."""
    col_map = {}
    header_set = {str(c).strip() for c in df.columns}
    for key, expected in COL_NAMES.items():
        if expected in header_set:
            col_map[key] = expected
        else:
            # Fuzzy fallback: case-insensitive match
            for col in header_set:
                if col.lower() == expected.lower():
                    col_map[key] = col
                    break
    return col_map

def assess_launch(run_df, col_map, speed_in_mph=False):
    """Return a short phrase describing launch quality."""
    slip_col = col_map.get("slip")
    accel_col = col_map.get("accelz")
    speed_col = col_map.get("speed")
    rpm_col = col_map.get("rpm")

    window = run_df.head(min(30, max(15, len(run_df) // 8)))

    # Wheelspin: only check when car is actually moving
    if slip_col and slip_col in window.columns and speed_col and speed_col in window.columns:
        moving = window[speed_col] > 1.0  # > 1 m/s = actually rolling
        if moving.any():
            max_slip = window.loc[moving, slip_col].abs().max()
            if max_slip > 0.18:
                return "possible wheelspin"
            if max_slip > 0.10:
                return "slight wheelspin"

    # Bog: acceleration stays low despite WOT
    if accel_col and accel_col in window.columns:
        peak_g = window[accel_col].max()
        if peak_g < 6.0:
            return "possible bog"

    # Speed pickup (convert to mph for threshold)
    if speed_col and speed_col in run_df.columns:
        first_third = run_df[speed_col].iloc[min(15, len(run_df) - 1)]
        first_third_mph = first_third if speed_in_mph else (first_third * 2.23694)
        if first_third_mph > 20:
            return "strong launch"
        if first_third_mph < 8:
            return "slow pickup"

    return "unclear from available fields"

def detect_limiter_hit(run_df, rpm_col, maxrpm_col=None):
    """True if RPM saturates near max for 5+ consecutive samples."""
    if rpm_col not in run_df.columns:
        return None
    rpm = run_df[rpm_col].values
    ceiling = (
        run_df[maxrpm_col].iloc[0]
        if (maxrpm_col and maxrpm_col in run_df.columns)
        else rpm.max()
    )
    near = rpm >= ceiling * 0.975
    cnt = 0
    for v in near:
        cnt = cnt + 1 if v else 0
        if cnt >= 5:
            return True
    return False

def estimate_et(run_df, speed_col, time_col, dist_col=None):
    """Estimate elapsed time and trap speed at 1/4 and 1/2 mile."""
    if dist_col and dist_col in run_df.columns:
        raw = run_df[dist_col].values
        if raw.max() > 1.0:
            dist = raw - raw[0]
        else:
            dist = None
    else:
        dist = None

    if dist is None:
        # Fall back: integrate speed over time (skip stationary parts)
        dt = run_df[time_col].diff().fillna(0) / 1000.0
        dist = (run_df[speed_col].clip(lower=0) * dt).cumsum().fillna(0).values

    speed = run_df[speed_col].values
    t = run_df[time_col].values / 1000.0

    def crossing(target_m):
        for i in range(1, len(dist)):
            if dist[i] >= target_m >= dist[i - 1]:
                frac = (target_m - dist[i - 1]) / (dist[i] - dist[i - 1])
                ct = t[i - 1] + frac * (t[i] - t[i - 1])
                cs = speed[i - 1] + frac * (speed[i] - speed[i - 1])
                return ct, cs
        return None, None

    start_t = t[0]
    results = {}
    for label, d in [("1/4 mile", QUARTER_MILE_M), ("1/2 mile", HALF_MILE_M)]:
        et, trap = crossing(d)
        if et is not None:
            results[label] = (round(et - start_t, 3), round(ms_to_mph(trap), 1))
    return results

def speed_col_in_mph(df, col):
    """Detect if a speed column is already in mph (vs m/s) by sampling."""
    if col not in df.columns:
        return False
    sample = df[col].dropna().head(50)
    if len(sample) == 0:
        return False
    mean_val = sample.mean()
    # Mph drag runs typically average ~80–160 mph
    # m/s would be ~35–70
    return 60 < mean_val < 200

# ── Main ────────────────────────────────────────────────────────────

def main():
    # Parse args
    show_only = False
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage:")
        print("  python3 fh_summarize.py fh6-session.csv")
        print("  python3 fh_summarize.py --show-columns fh6-session.csv")
        sys.exit(0)
    if sys.argv[1] == "--show-columns":
        show_only = True
        csv_path = sys.argv[2]
    else:
        csv_path = sys.argv[1]

    # ── Read CSV ────────────────────────────────────────────────────
    try:
        df = pd.read_csv(csv_path, sep=None, engine="python")
    except FileNotFoundError:
        print(f"File not found: {csv_path}")
        sys.exit(1)

    print(f"Columns detected ({len(df.columns)}):")
    for i, c in enumerate(df.columns):
        print(f"  {i:2d}: {c}")
    print()
    print(f"Rows: {len(df)}")
    print(f"First 3 rows (preview):")
    print(df.head(3).to_string())
    print()

    if show_only:
        return

    # ── Map columns ─────────────────────────────────────────────────
    col_map = detect_columns(df)

    missing = [k for k in ["speed", "rpm", "time"] if k not in col_map]
    if missing:
        print(f"Missing critical columns: {missing}")
        print("Cannot analyse — need at least Speed, CurrentEngineRpm, and TimestampMS.")
        sys.exit(1)

    speed_col = col_map["speed"]
    rpm_col = col_map["rpm"]
    time_col = col_map["time"]
    maxrpm_col = col_map.get("maxrpm")
    gear_col = col_map.get("gear")
    dist_col = col_map.get("dist")
    throttle_col = col_map.get("throttle")

    # Detect whether Speed is stored in mph or m/s
    speed_in_mph = speed_col_in_mph(df, speed_col)

    # ── Split into runs ─────────────────────────────────────────────
    # Heuristic: speed drops near zero marks run boundaries.
    # Also watch for the finish (braking at end of strip) via Accel dropping.
    threshold = 2.0 if speed_in_mph else mph_to_ms(SPEED_NEAR_ZERO)
    stopped = df[speed_col] < threshold

    runs = []
    in_run = False
    boundaries = []
    for i in range(len(df)):
        if not in_run and not stopped.iloc[i]:
            run_start = i
            in_run = True
        elif in_run and stopped.iloc[i]:
            in_run = False
            if i - run_start >= MIN_RUN_SAMPLES:
                boundaries.append((run_start, i))
    if in_run and len(df) - run_start >= MIN_RUN_SAMPLES:
        boundaries.append((run_start, len(df) - 1))

    for s, e in boundaries:
        runs.append(df.iloc[s:e + 1].copy().reset_index(drop=True))

    # Filter out non-drag runs (pit driving, repositioning)
    drag_runs = []
    for r in runs:
        max_spd = r[speed_col].max()
        max_spd_mph = max_spd if speed_in_mph else ms_to_mph(max_spd)
        if max_spd_mph > 50:
            drag_runs.append(r)
    runs = drag_runs

    if not runs:
        print("No runs detected (speed never crossed threshold).")
        print("Trying single-run fallback with entire file...")
        runs = [df]

    # ── Analyse each run ────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  {len(runs)} drag run(s) detected")
    print(f"{'=' * 60}\n")

    for idx, run_df in enumerate(runs):
        print(f"  ── Run {idx + 1} ──")

        # Find the launch point: Accel goes WOT from near-zero speed
        sv_arr = run_df[speed_col].values
        accel_col_local = col_map.get("throttle")
        launch_idx = 0
        if accel_col_local and accel_col_local in run_df.columns:
            acc_arr = run_df[accel_col_local].values
            for i in range(1, len(sv_arr)):
                if (acc_arr[i] > 200 and sv_arr[i] < mph_to_ms(15)):
                    launch_idx = max(0, i - 2)
                    break
        if launch_idx == 0:
            # Fallback: first time speed exceeds 5 mph
            launch_thresh = 5.0 if speed_in_mph else mph_to_ms(5.0)
            for i in range(1, len(sv_arr)):
                if sv_arr[i] >= launch_thresh and sv_arr[i - 1] < launch_thresh * 0.5:
                    launch_idx = i - 1
                    break

        # Use only the acceleration phase (launch to 30 rows after peak)
        phase = run_df.iloc[launch_idx:].copy().reset_index(drop=True)
        pv = phase[speed_col].values
        peak_idx = pv.argmax()
        trimmed = phase.iloc[:min(peak_idx + 30, len(phase))].copy()
        speed_vals = trimmed[speed_col].values
        if not speed_in_mph:
            speed_vals = ms_to_mph(speed_vals)
        max_spd = speed_vals.max()
        trap_zone = speed_vals[int(len(speed_vals) * 0.80):]
        trap_spd = trap_zone.max() if len(trap_zone) else max_spd
        print(f"    Max speed:  {max_spd:.1f} mph")
        print(f"    Trap speed: {trap_spd:.1f} mph")

        # RPM
        if rpm_col in run_df.columns:
            print(f"    Max RPM:    {run_df[rpm_col].max():.0f}")

        # Gear at max speed point (last 10% of trimmed run)
        if gear_col and gear_col in trimmed.columns:
            finish_gear = trimmed[gear_col].iloc[int(len(trimmed) * 0.9):].mode()
            finish_gear = int(finish_gear.iloc[0] if len(finish_gear) else trimmed[gear_col].iloc[-1])
            print(f"    Finish gear: {finish_gear}")

        # ET / trap at hard distances (use trimmed launch phase)
        if not speed_in_mph:
            for label, (et, trap) in estimate_et(trimmed, speed_col, time_col, dist_col).items():
                print(f"    {label}: ET {et:.1f}s @ {trap:.0f} mph")
        else:
            run_df_mps = trimmed.copy()
            run_df_mps[speed_col] = trimmed[speed_col] / 2.23694
            for label, (et, trap) in estimate_et(run_df_mps, speed_col, time_col, dist_col).items():
                print(f"    {label}: ET {et:.1f}s @ {trap:.0f} mph")

        # Limiter
        lim = detect_limiter_hit(trimmed, rpm_col, maxrpm_col)
        if lim:
            print(f"    ⚠  Hitting rev limiter before finish")
        elif lim is False:
            print(f"    ✓  Not hitting limiter")

        # Launch
        print(f"    Launch:     {assess_launch(trimmed, col_map, speed_in_mph)}")

        # Duration
        dur_s = (trimmed[time_col].iloc[-1] - trimmed[time_col].iloc[0]) / 1000.0
        print(f"    Duration:   {dur_s:.1f}s  ({len(trimmed)} samples)")

        print()

    # ── Compact Ollama block ────────────────────────────────────────
    print(f"{'=' * 60}")
    print("  OLLAMA PASTE SUMMARY")
    print(f"{'=' * 60}\n")

    for idx, run_df in enumerate(runs):
        # Find launch point (same as above)
        sv_arr = run_df[speed_col].values
        accel_col_local = col_map.get("throttle")
        launch_idx = 0
        if accel_col_local and accel_col_local in run_df.columns:
            acc_arr = run_df[accel_col_local].values
            for i in range(1, len(sv_arr)):
                if (acc_arr[i] > 200 and sv_arr[i] < mph_to_ms(15)):
                    launch_idx = max(0, i - 2)
                    break
        if launch_idx == 0:
            launch_thresh = 5.0 if speed_in_mph else mph_to_ms(5.0)
        for i in range(1, len(sv_arr)):
            if sv_arr[i] >= launch_thresh and sv_arr[i - 1] < launch_thresh * 0.5:
                launch_idx = i - 1
                break
        phase = run_df.iloc[launch_idx:].copy().reset_index(drop=True)
        pv = phase[speed_col].values
        peak_idx = pv.argmax()
        trimmed = phase.iloc[:min(peak_idx + 30, len(phase))].copy()
        speed_vals = trimmed[speed_col].values
        if not speed_in_mph:
            speed_vals = ms_to_mph(speed_vals)
        trap_zone = speed_vals[int(len(speed_vals) * 0.80):]
        trap = trap_zone.max() if len(trap_zone) else speed_vals.max()

        lines = [f"Run {idx + 1}: 2012 Nissan GT-R Black Edition FE (R35)"]
        lines.append(f"  Trap: {trap:.0f} mph  Max: {speed_vals.max():.0f} mph")

        if rpm_col in run_df.columns:
            lines.append(f"  Max RPM: {run_df[rpm_col].max():.0f}")
        if gear_col and gear_col in trimmed.columns:
            fg = trimmed[gear_col].iloc[int(len(trimmed) * 0.9):].mode()
            fg = int(fg.iloc[0] if len(fg) else trimmed[gear_col].iloc[-1])
            lines.append(f"  Finish gear: {fg}")

        if not speed_in_mph:
            for label, (et, trap) in estimate_et(trimmed, speed_col, time_col, dist_col).items():
                lines.append(f"  {label}: {et:.1f}s @ {trap:.0f} mph")
        else:
            run_df_mps = trimmed.copy()
            run_df_mps[speed_col] = trimmed[speed_col] / 2.23694
            for label, (et, trap) in estimate_et(run_df_mps, speed_col, time_col, dist_col).items():
                lines.append(f"  {label}: {et:.1f}s @ {trap:.0f} mph")

        if detect_limiter_hit(trimmed, rpm_col, maxrpm_col):
            lines.append("  ⚠  Hitting rev limiter before finish")

        lines.append(f"  Launch: {assess_launch(trimmed, col_map, speed_in_mph)}")

        dur = (trimmed[time_col].iloc[-1] - trimmed[time_col].iloc[0]) / 1000.0
        lines.append(f"  Full-run ET: ~{dur:.1f}s")

        print("\n".join(lines))
        print()

    # ── Schema feedback ─────────────────────────────────────────────
    found = [k for k, v in col_map.items() if v is not None]
    ideal = {"speed", "rpm", "time", "maxrpm", "gear", "slip", "accelz", "throttle", "dist"}
    missing = ideal - set(col_map.keys())
    if missing:
        print(f"  Fields found: {sorted(found)}")
        print(f"  Fields missing (partial analysis): {sorted(missing)}")
    else:
        print("  All expected fields present — full analysis.")


if __name__ == "__main__":
    main()
