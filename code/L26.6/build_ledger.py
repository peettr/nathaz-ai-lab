"""由 ledger_data.py 生成 失败台账.md；统计全部由程序计算。"""
import collections, importlib.util, sys, pathlib
here = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("d", here / "ledger_data.py"); d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
R = d.R
cfd = [r for r in R if r["type"] != "环境" and not r["id"].startswith("A")]
t27 = [r for r in R if r["id"].startswith("A")]
env = [r for r in R if r["type"] == "环境"]
def silent_yes(r): return r["silent"].startswith("是")
def table(rows):
    h = "| 编号 | 线 | 日期 | 事件 | 作业 | 失败类型 | 静默 | 步骤 | 发现者 | 性质 | 代价 | 证据（文件:行） |\n|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    return h + "".join(f"| {r['id']} | {r['line']} | {r['date']} | {r['event']} | {r['jobs']} | {r['type']} | {r['silent']} | {r['step']} | {r['finder']} | {r['nature']} | {r['cost']} | {r['ev']} |\n" for r in rows)
def counts(rows, key, order=None):
    c = collections.Counter(r[key] for r in rows)
    ks = order or sorted(c, key=lambda k: -c[k])
    return " / ".join(f"{k} {c.get(k,0)}" for k in ks if c.get(k,0))
def cross(rows, k1, k2):
    a = sorted({r[k1] for r in rows}); b = sorted({r[k2] for r in rows})
    s = f"| {k1}＼{k2} | " + " | ".join(b) + " |\n|" + "---|" * (len(b) + 1) + "\n"
    for x in a:
        s += f"| {x} | " + " | ".join(str(sum(1 for r in rows if r[k1]==x and r[k2]==y)) for y in b) + " |\n"
    return s
STEPS = ["几何","网格","边界与入流","求解设置","提交运行","后处理","诊断判读"]
out = []
out.append("# L26.6 CFD 自动化失败台账（本平台 10-06～10-19 记录到的）\n")
out.append("> 本表由 `build_ledger.py` 从 `ledger_data.py` 生成，数字全部程序计算。分类由 L26.6 Lead 判定（不交 Gemini，工单 0204）。结论只限本平台本时段的记录，不外推为 CFD 智能体一般失败率。\n")
out.append("路径缩写：CFD=`16_PETW/02_Subprojects/CFD_Automation`；D=`CFD/04_Decisions`；LES=`D/CAARC_LES_phase_20261009.md`；F=`28_Fluent`；A=`27_Ansys_Mechanical`；04_Reviews 指 `CFD/04_Reviews`。均在 `./` 下。\n")
out.append("**入账口径**：同一机制、同一天内的连续作业合为一条（作业号列全）；同一错误隔天复发仍合为一条并标“复发”。只是计划改变、主动取消的不入账；节点故障、平台重启等单列“环境”，不计入判据条数。选取方式：三路只读检索（CFD 决策记录/项目页/审查、T28 决策与算例报告、T27 决策）摘出约 150 个候选事件，Lead 逐条读证据行，保留有明确现象和根因记录、对流程有代表性的条目；未入账的见文末。\n")
out.append(f"## 一、统计（CFD：R16.5 + T28，共 {len(cfd)} 条）\n")
out.append(f"- 静默（作业正常结束或无报错，结果错）：{sum(silent_yes(r) for r in cfd)} / {len(cfd)}\n")
out.append(f"- 失败类型：{counts(cfd,'type')}\n")
out.append(f"- 发生步骤：{counts(cfd,'step',STEPS)}\n")
out.append(f"- 发现者：{counts(cfd,'finder')}\n")
out.append(f"- 性质：{counts(cfd,'nature')}\n")
sil = [r for r in cfd if silent_yes(r)]
out.append(f"\n### 静默失败的发现者（{len(sil)} 条）\n{counts(sil,'finder')}\n")
out.append(f"\n### 静默失败的步骤\n{counts(sil,'step',STEPS)}\n")
out.append("\n### 失败类型 × 发现者\n" + cross(cfd, "type", "finder"))
out.append("\n### 步骤 × 性质\n" + cross(cfd, "step", "nature"))
out.append(f"\n## 二、CFD 台账（{len(cfd)} 条）\n" + table(cfd))
out.append(f"\n## 三、环境类（{len(env)} 条，不计判据）\n" + table(env))
out.append(f"\n## 四、T27 Ansys 结构有限元（{len(t27)} 条，非 CFD，单列对照）\n")
out.append(f"- 静默 {sum(silent_yes(r) for r in t27)} / {len(t27)}；类型：{counts(t27,'type')}；发现者：{counts(t27,'finder')}；性质：{counts(t27,'nature')}\n\n" + table(t27))
(here / "失败台账.md").write_text("".join(out), encoding="utf-8")
print("cfd", len(cfd), "t27", len(t27), "env", len(env), "silent", len(sil))
