#!/usr/bin/env python3
"""Extract training curves from log files."""
import re, json
from pathlib import Path

epoch_pat = re.compile(r"Epoch\s+(\d+)/\d+\s+train=([\d.]+)\s+test=([\d.]+)\s+best=([\d.]+)")

logs = {
    2: "retrain_s2_l40s", 3: "v3_p2", 4: "v3_p3", 5: "v3_p4",
    6: "v3b_s6", 7: "v3_p6", 8: "v3_p7", 9: "v3_p8",
    10: "v3b_s10", 11: "v3_p10", 12: "v3_p11",
    13: "v3b_s13", 14: "v3b_s14", 15: "v3b_s15",
    16: "v3c_s16", 17: "v3b_s17", 18: "v3c_s18", 19: "v3c_s19",
    20: "v3e_s20",
}

# Find seed 1
for f in Path("logs").glob("*.err"):
    content = f.read_text(errors="ignore")
    if "Seed 1 done" in content:
        print("Found seed 1 in %s" % f.name)
        logs[1] = f.stem
        break

result = {}
for seed in sorted(logs.keys()):
    logname = logs[seed]
    logpath = Path("logs/%s.err" % logname)
    if not logpath.exists():
        print("Seed %d: %s missing" % (seed, logpath))
        continue
    text = logpath.read_text(errors="ignore")
    epochs, train, test, best = [], [], [], []
    for m in epoch_pat.finditer(text):
        epochs.append(int(m.group(1)))
        train.append(float(m.group(2)))
        test.append(float(m.group(3)))
        best.append(float(m.group(4)))
    result[str(seed)] = {"epoch": epochs, "train": train, "test": test, "best": best}
    print("Seed %d: %d epochs from %s" % (seed, len(epochs), logname))

with open("results/training_curves_20seeds.json", "w") as f:
    json.dump(result, f, indent=2)
print("Saved to results/training_curves_20seeds.json")
