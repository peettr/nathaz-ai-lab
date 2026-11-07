"""由 per_field.json / pairwise.json / rmse_better_but_miss.json 程序化生成结果表（数字不手抄）。"""
import json, collections
import numpy as np
D = "/content/out"
rows = json.load(open(f"{D}/per_field.json"))
pw = json.load(open(f"{D}/pairwise.json"))
inst = json.load(open(f"{D}/rmse_better_but_miss.json"))
SHOW = ["RMSE", "PSNR", "PeakErr", "PeakShift", "Reg95_Hit", "Reg95_AreaRelErr", "Reg95_False",
        "Reg90_Hit", "Reg99_Hit", "PD_bottleneck", "PD_W2", "MTproxy_topkPersL2"]
LOWER = {"RMSE": 1, "PSNR": 0, "PeakErr": 1, "PeakShift": 1, "Reg95_Hit": 0, "Reg95_AreaRelErr": 1, "Reg95_False": 1,
         "Reg90_Hit": 0, "Reg99_Hit": 0, "PD_bottleneck": 1, "PD_W2": 1, "MTproxy_topkPersL2": 1}
out = ["# L26.2 结果表（程序生成，summarize_l262.py）", "",
       "参考场：CM1 D420 50 m 水平风速（27 帧，10 s 间隔）。指标定义见项目页。Hit=真值显著区（面积≥9 格）被候选覆盖≥50% 的比例。", ""]
for g in sorted({r["group"] for r in rows}):
    gr = [r for r in rows if r["group"] == g]
    cands = sorted({r["cand"] for r in gr})
    mean = {c: {m: float(np.nanmean([r[m] for r in gr if r["cand"] == c])) for m in SHOW} for c in cands}
    out += [f"## {g}：各候选 27 帧平均值（括号内为该指标下的名次，1=最好）", "",
            "| 候选 | " + " | ".join(SHOW) + " |", "|---" * (len(SHOW) + 1) + "|"]
    ranks = {}
    for m in SHOW:
        order = sorted(cands, key=lambda c: mean[c][m] if LOWER[m] else -mean[c][m])
        ranks[m] = {c: order.index(c) + 1 for c in cands}
    for c in cands:
        out.append(f"| {c} | " + " | ".join(f"{mean[c][m]:.3g} ({ranks[m][c]})" for m in SHOW) + " |")
    out.append("")
    # 判据：RMSE 或 PSNR 与其他指标在同一对候选上方向相反，且双方都有分辨力（逐帧胜场 ≥60%、p<0.05）
    out += [f"### {g}：与 RMSE 排序相反且两边都有分辨力的候选对（逐帧胜场 ≥60% 且符号检验 p<0.05）", "",
            "| A | B | RMSE 判（A 胜帧/总帧, p） | 相反指标 | 该指标判（B 胜帧/总帧, p） |", "|---|---|---|---|---|"]
    idx = {(x["A"], x["B"], x["metric"]): x for x in pw if x["group"] == g}
    n_disc = 0
    for (a, b, m), x in idx.items():
        if m != "RMSE" or not x["n"]:
            continue
        for o in SHOW[1:]:
            y = idx.get((a, b, o))
            if not y or not y["n"]:
                continue
            for (P, Q) in ((x, y),):
                aR = P["shareA"] >= 0.6 and P["p"] < 0.05
                bR = P["shareA"] <= 0.4 and P["p"] < 0.05
                aO = Q["shareA"] >= 0.6 and Q["p"] < 0.05
                bO = Q["shareA"] <= 0.4 and Q["p"] < 0.05
                if aR and bO:
                    out.append(f"| {a} | {b} | A {P['winA']}/{P['n']}, p={P['p']:.2g} | {o} | B {Q['winB']}/{Q['n']}, p={Q['p']:.2g} |"); n_disc += 1
                elif bR and aO:
                    out.append(f"| {b} | {a} | A {P['winB']}/{P['n']}, p={P['p']:.2g} | {o} | B {Q['winA']}/{Q['n']}, p={Q['p']:.2g} |"); n_disc += 1
    out += ["", f"相反对数：{n_disc}", ""]
cnt = collections.Counter((i["group"], i["pct"], i["A_rmse_better"], i["B"]) for i in inst)
out += ["## RMSE 更好（相对差≥2%）却漏掉真值显著区、而另一候选命中的实例", "",
        f"实例总数（帧×候选对×阈值，同一帧多区算 1 条）：{len(inst)}", "",
        "| 组 | 阈值 | RMSE 更好的 A | 命中的 B | 帧数 |", "|---|---|---|---|---|"]
for (g, p, a, b), n in sorted(cnt.items(), key=lambda kv: -kv[1]):
    out.append(f"| {g} | P{p} | {a} | {b} | {n} |")
open(f"{D}/results_table.md", "w").write("\n".join(out))
print("\n".join(out[:12]))
