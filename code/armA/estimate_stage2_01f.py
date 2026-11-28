"""Bounded stage-2 A10 wall-time gate using qualified stage-1 HOT timings.
Reads stage-1 outputs on CRC or on the local small-result evidence copy; never runs GPU.
The estimate treats each objective/window independently and includes compilation,
I/O, segmented-gradient and scheduling reserve explicitly instead of hiding them.
"""
import argparse
import json
import pathlib


def load_hot(folder, dtype, objective):
    path = folder / f"hot_{dtype}_{objective}.jsonl"
    data = [json.loads(line) for line in path.read_text().splitlines() if line.startswith("{")]
    keyed = {str(row["checkpoint"]).lower(): row for row in data if row.get("stage") == "hot_pilot"}
    if not keyed:
        raise ValueError(f"hot pilot absent: {path}")
    return keyed


def load_window(folder, dtype, key):
    path = folder / f"windows_{dtype}.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.startswith("{")]
    matching = [row["T"] for row in rows if row.get("metric") == key]
    if len(matching) != 1 or matching[0] is None:
        raise ValueError(f"qualified window missing: {path} {key}")
    return int(matching[0])


def estimate(folder, stage1_seconds, cap_hours=10, margin=1.2):
    total = 0.0
    components = []
    for objective, key in (("mean", "max_mean_se"), ("var", "max_sigma_relative_se")):
        t32 = load_window(folder, "float32", key)
        t64 = load_window(folder, "float64", key)
        if t32 != t64:
            # Conservative: compare both precisions on the longer qualified window.
            t = max(t32, t64)
        else:
            t = t32
        f32 = load_hot(folder, "float32", objective)
        f64 = load_hot(folder, "float64", objective)
        # Pick checkpoint variant with smallest observed hot gradient wall-time;
        # actual memory pass still must be checked separately before proceeding.
        g32 = min(float(row["gradient_s"]) for row in f32.values())
        g64 = min(float(row["gradient_s"]) for row in f64.values())
        forward = max(float(row["forward_s_per_step"]) for row in f64.values())
        for divisor in (1, 2, 4, 8):
            steps = max(1, t // divisor)
            factor = steps / t
            # 5 points, two AD precisions; per point FP64 FD has 18 components,
            # two perturbation sizes and both signs = 72 forward evaluations.
            seconds = 5 * (factor * (g32 + g64) + 72 * steps * forward)
            components.append({"objective": objective, "divisor": divisor,
                               "steps": steps, "fwd_evaluations": 360,
                               "ad_evaluations": 10, "seconds": seconds})
            total += seconds
    # I/O, compile, restarts, segmented-gradient and postprocessing reserve.
    projected = stage1_seconds + margin * total
    return {"stage1_seconds": stage1_seconds, "stage2_raw_seconds": total,
            "stage2_with_margin_seconds": margin * total,
            "total_a10_hours": projected / 3600,
            "cap_hours": cap_hours, "within_cap": projected <= cap_hours * 3600,
            "components": components,
            "qualification_note": "Conditional estimate only; requires qualified windows, hot JAX device-memory pass, and remaining allocation. Segment-gradient overhead is not independently measured."}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("folder", type=pathlib.Path)
    p.add_argument("--stage1-seconds", type=float, required=True)
    a = p.parse_args()
    print(json.dumps(estimate(a.folder, a.stage1_seconds), indent=2))
