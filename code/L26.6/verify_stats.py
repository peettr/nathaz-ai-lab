"""两线核对的无异议率（判据 2），由逐条判定表计算。"""
R165 = {  # 主读法异议 / 严读法异议（存疑中提出改轴也算）
 "obj_main": ["C06","C09","C12","C33","C35","C36","X02"],
 "obj_strict_extra": ["C01","C14","C22","C29"],  # C17、C40、C44 存疑未提改轴
 "n": 49}
T28 = {"obj_main": [], "obj_strict_extra": ["F02","F06","F09"], "n": 12}
T27 = {"obj_main": ["A05"], "obj_strict_extra": ["A01","A03"], "n": 7}
rows = []
for name, d in [("R16.5（cfd-claude #d5de0a02）", R165), ("T28（fluent-claude #7511f066）", T28)]:
    m = d["n"] - len(d["obj_main"]); s = m - len(d["obj_strict_extra"])
    rows.append((name, d["n"], m, s))
tn = sum(r[1] for r in rows); tm = sum(r[2] for r in rows); ts = sum(r[3] for r in rows)
out = ["# L26.6 两线核对统计（判据 2：无异议率 ≥80%）\n",
"主读法＝开工前写定的定义：只有改任一轴分类或否认事实才算异议，“属实（存疑…）”算无异议。",
"严读法＝10-19 收齐回复后补充的另一种读法（事后补定）：存疑里明确提出另一轴取值的也算异议。\n",
"| 线 | 送核条数 | 主读法无异议 | 主读法比率 | 严读法无异议 | 严读法比率 |","|---|---|---|---|---|---|"]
for n, k, m, s in rows: out.append(f"| {n} | {k} | {m} | {m/k:.1%} | {s} | {s/k:.1%} |")
out.append(f"| **两线合计** | {tn} | {tm} | **{tm/tn:.1%}** | {ts} | **{ts/tn:.1%}** |")
k=T27["n"]; m=k-len(T27["obj_main"]); s=m-len(T27["obj_strict_extra"])
out.append(f"| T27（ansys-claude #b8cbc7ce，单列，不计入判据） | {k} | {m} | {m/k:.1%} | {s} | {s/k:.1%} |")
out.append(f"\n主读法异议：R16.5 {', '.join(R165['obj_main'])}；T28 无；T27 {', '.join(T27['obj_main'])}。")
out.append(f"严读法另加：R16.5 {', '.join(R165['obj_strict_extra'])}；T28 {', '.join(T28['obj_strict_extra'])}；T27 {', '.join(T27['obj_strict_extra'])}。")
out.append("异议全部已核证据后采纳进台账（见 ledger_data.py 注释“核对方”）；统计按送核时冻结的版本（失败台账_送核版_20261019_1913.md，sha256 见 送核版_sha256.txt）计。")
open("核对统计.md","w",encoding="utf-8").write("\n".join(out)+"\n")
print("\n".join(out))
