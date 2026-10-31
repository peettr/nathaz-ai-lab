"""L26.9 揭盲统计：覆盖率、Δ、配对 bootstrap、κ。
输入: units.jsonl {paper, unit_id, major}；judgments.jsonl {unit_id, covered_by:[item ids], partial_by:[...]}（裁决后）；
      blind_key.json；runs 每组份数。用法: python3 -I stats.py units judgments key out.md"""
import sys, json, random, statistics
def load(p): return [json.loads(l) for l in open(p) if l.strip()]
def kappa(a, b):
    n = len(a); labs = set(a) | set(b)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labs)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")
def main(up, jp, kp, outp):
    units = load(up); judg = {j["unit_id"]: j for j in load(jp)}; key = json.load(open(kp))
    runs = {}
    for v in key.values(): runs.setdefault(v["arm"], set()).add(v["run"])
    def cov(u, arm, run, partial=False):
        ids = judg[u["unit_id"]]["covered_by"] + (judg[u["unit_id"]].get("partial_by", []) if partial else [])
        return any(key[i]["arm"] == arm and key[i]["run"] == run for i in ids)
    def unit_rate(u, arm, partial=False):
        rs = sorted(runs[arm]); return sum(cov(u, arm, r, partial) for r in rs) / len(rs)
    lines = ["| 读法 | A 覆盖率 | B 覆盖率 | Δ (pp) | bootstrap 95% |", "|---|---|---|---|---|"]
    for name, part in (("主读法（只计完全覆盖）", False), ("另一读法（含部分覆盖）", True)):
        a = [unit_rate(u, "A", part) for u in units]; b = [unit_rate(u, "B", part) for u in units]
        d = [y - x for x, y in zip(a, b)]; rng = random.Random(2000); bs = []
        for _ in range(2000):
            s = [d[rng.randrange(len(d))] for _ in d]; bs.append(sum(s) / len(s))
        bs.sort()
        lines.append(f"| {name} | {100*statistics.mean(a):.1f}% | {100*statistics.mean(b):.1f}% | {100*statistics.mean(d):+.1f} | [{100*bs[49]:+.1f}, {100*bs[1949]:+.1f}] |")
    lines.append(f"\n真实意见单元 n = {len(units)}；每组份数 A={len(runs.get('A',[]))}, B={len(runs.get('B',[]))}")
    open(outp, "w").write("\n".join(lines) + "\n"); print("\n".join(lines))
if __name__ == "__main__": main(*sys.argv[1:5])
