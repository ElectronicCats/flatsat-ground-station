#!/usr/bin/env python3
"""HW-05: Simple Power Analysis (SPA) — extract secrets from power traces.

Processes power consumption traces captured from the FlatSat during
cryptographic operations. The AES-128-ECB encryption in the firmware
leaks key information through power consumption variations.

Works with CSV exports from oscilloscopes or Chipwhisperer.

Participants capture power traces while triggering CRYPTO_ORACLE commands,
then use this tool to correlate power patterns with key byte hypotheses.
"""

import csv
import sys


def load_trace(filepath: str) -> tuple[list[float], list[float]]:
    """Load a power trace from CSV.

    Supports formats:
    - Two columns: time, voltage
    - Single column: voltage (assumes uniform sampling)
    - Chipwhisperer format: numpy .npy files
    """
    if filepath.endswith(".npy"):
        try:
            import numpy as np

            data = np.load(filepath)
            if data.ndim == 1:
                return list(range(len(data))), data.tolist()
            return data[:, 0].tolist(), data[:, 1].tolist()
        except ImportError:
            print("[!] numpy required for .npy files: pip install numpy")
            sys.exit(1)

    times = []
    voltages = []

    with open(filepath) as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header

        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            try:
                if len(row) >= 2:
                    times.append(float(row[0]))
                    voltages.append(float(row[1]))
                else:
                    times.append(len(voltages))
                    voltages.append(float(row[0]))
            except ValueError:
                continue

    return times, voltages


def find_peaks(voltages: list[float], threshold: float | None = None) -> list[int]:
    """Find indices of significant peaks in the power trace."""
    if threshold is None:
        avg = sum(voltages) / len(voltages)
        std = (sum((v - avg) ** 2 for v in voltages) / len(voltages)) ** 0.5
        threshold = avg + 2 * std

    peaks = []
    for i in range(1, len(voltages) - 1):
        if voltages[i] > threshold and voltages[i] > voltages[i - 1] and voltages[i] > voltages[i + 1]:
            peaks.append(i)
    return peaks


def analyze_timing(traces: list[str]):
    """Analyze multiple power traces to find timing differences.

    Timing side-channel: AES operations that process different key bytes
    may take different amounts of time, visible as trace length variations.
    """
    print(f"[*] Analyzing timing across {len(traces)} traces...")
    print()

    results = []
    for filepath in traces:
        times, voltages = load_trace(filepath)
        peaks = find_peaks(voltages)
        duration = times[-1] - times[0] if times else 0
        peak_count = len(peaks)
        avg_power = sum(voltages) / len(voltages) if voltages else 0
        max_power = max(voltages) if voltages else 0

        results.append(
            {
                "file": filepath,
                "samples": len(voltages),
                "duration": duration,
                "peaks": peak_count,
                "avg_power": avg_power,
                "max_power": max_power,
            }
        )

        print(f"  {filepath}:")
        print(f"    Samples: {len(voltages)}, Duration: {duration:.6f}s")
        print(f"    Peaks: {peak_count}, Avg: {avg_power:.4f}, Max: {max_power:.4f}")

    # Look for timing variations
    if len(results) >= 2:
        durations = [r["duration"] for r in results]
        avg_dur = sum(durations) / len(durations)
        variance = sum((d - avg_dur) ** 2 for d in durations) / len(durations)
        print("\n[*] Timing analysis:")
        print(f"    Mean duration: {avg_dur:.6f}s")
        print(f"    Variance: {variance:.10f}")
        if variance > 1e-8:
            print("    [+] Timing variation detected — possible side-channel leak")
            # Sort by duration
            sorted_results = sorted(results, key=lambda r: r["duration"])
            print(f"    Shortest: {sorted_results[0]['file']} ({sorted_results[0]['duration']:.6f}s)")
            print(f"    Longest:  {sorted_results[-1]['file']} ({sorted_results[-1]['duration']:.6f}s)")
        else:
            print("    [-] No significant timing variation")


def correlation_attack(traces_dir: str, known_plaintexts: str | None = None):
    """Differential Power Analysis (DPA) attack — correlate power traces
    with key byte hypotheses using the Hamming weight model.

    This is a simplified demonstration. A real DPA attack needs:
    1. Many traces (100+) with known plaintexts
    2. Precise alignment of traces
    3. Statistical correlation across all key byte hypotheses
    """
    import glob
    import os

    trace_files = sorted(glob.glob(os.path.join(traces_dir, "*.csv")))
    if not trace_files:
        trace_files = sorted(glob.glob(os.path.join(traces_dir, "*.npy")))

    if not trace_files:
        print(f"[!] No trace files found in {traces_dir}")
        return

    print(f"[*] DPA attack with {len(trace_files)} traces from {traces_dir}")

    # Load all traces
    all_traces = []
    for tf in trace_files:
        _, voltages = load_trace(tf)
        all_traces.append(voltages)

    if not all_traces:
        return

    # Ensure all traces are same length (truncate to shortest)
    min_len = min(len(t) for t in all_traces)
    all_traces = [t[:min_len] for t in all_traces]

    print(f"[*] {len(all_traces)} traces, {min_len} samples each")

    # Compute difference of means (simplest DPA)
    avg = [sum(t[i] for t in all_traces) / len(all_traces) for i in range(min_len)]

    # Split traces into two groups by median power at first peak
    peaks = find_peaks(avg)
    if peaks:
        split_point = peaks[0]
        group_high = [t for t in all_traces if t[split_point] > avg[split_point]]
        group_low = [t for t in all_traces if t[split_point] <= avg[split_point]]

        if group_high and group_low:
            avg_high = [sum(t[i] for t in group_high) / len(group_high) for i in range(min_len)]
            avg_low = [sum(t[i] for t in group_low) / len(group_low) for i in range(min_len)]
            diff = [avg_high[i] - avg_low[i] for i in range(min_len)]

            max_diff_idx = max(range(min_len), key=lambda i: abs(diff[i]))
            print(f"\n[*] Max differential at sample {max_diff_idx}: {diff[max_diff_idx]:.6f}")
            print(f"    Group high: {len(group_high)} traces")
            print(f"    Group low: {len(group_low)} traces")

            if abs(diff[max_diff_idx]) > 0.01:
                print("    [+] Significant power differential — key bit leak likely")
            else:
                print("    [-] Weak differential — need more traces or better alignment")
    else:
        print("[!] No peaks found in average trace — check capture quality")


def visualize(filepath: str):
    """Print an ASCII visualization of a power trace."""
    times, voltages = load_trace(filepath)

    if not voltages:
        print("[!] No data in trace")
        return

    # Downsample to terminal width
    width = 80
    height = 20
    chunk = max(1, len(voltages) // width)

    downsampled = []
    for i in range(0, len(voltages), chunk):
        chunk_vals = voltages[i : i + chunk]
        downsampled.append(sum(chunk_vals) / len(chunk_vals))

    v_min = min(downsampled)
    v_max = max(downsampled)
    v_range = v_max - v_min or 1

    print(f"[*] Trace: {filepath}")
    print(f"[*] Samples: {len(voltages)}, Range: {v_min:.4f} - {v_max:.4f}")
    print()

    # Draw
    for row in range(height - 1, -1, -1):
        threshold = v_min + (row / (height - 1)) * v_range
        line = ""
        for v in downsampled[:width]:
            if v >= threshold:
                line += "#"
            else:
                line += " "
        label = f"{threshold:.3f}" if row % 5 == 0 else "     "
        print(f"{label:>8} |{line}|")

    print(f"{'':>8} +{'-' * width}+")
    peaks = find_peaks(voltages)
    print(f"[*] Detected {len(peaks)} peaks")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  power_analysis.py view <trace.csv>           ASCII visualization")
        print("  power_analysis.py timing <trace1> <trace2>.. Compare timing across traces")
        print("  power_analysis.py dpa <traces_dir/>          Differential power analysis")
        print()
        print("Analyze power traces from oscilloscope/Chipwhisperer captures.")
        print("Supports CSV (time,voltage) and numpy .npy formats.")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "view":
        visualize(sys.argv[2])
    elif cmd == "timing":
        analyze_timing(sys.argv[2:])
    elif cmd == "dpa":
        correlation_attack(sys.argv[2])
