#!/usr/bin/env python3
"""Render M5 decision-compliant report from archived tables; no scientific recomputation."""
import csv, pathlib, hashlib
R=pathlib.Path(__file__).resolve().parent; S=R/'supplement2'
def table(name):
    with (S/name).open(newline='') as f:return list(csv.DictReader(f))
def fmt(row,key='point',digits=3):
    return f"{float(row[key]):.{digits}f} [{float(row['lo']):.{digits}f}, {float(row['hi']):.{digits}f}]"
def get(rows,h,metric):
    return next(x for x in rows if int(x['fhr'])==h and x['metric']==metric)
def main():
    original=(R/'results.md').read_text()
    supplement=(R/'supplement/supplement.md').read_text()
    gates=table('boundary_gates.csv'); metrics=table('secondary_ci.csv'); sites=table('station_auc.csv');cov=table('station_coverage.csv');inc=table('station_increment.csv');threshold=table('native_thresholds.csv')
    assert len(gates)==8 and len(sites)==48 and len(cov)==48 and len(inc)==48 and len(threshold)==12
    assert all(float(x['hi'])<0 for x in gates[:4]) is not None
    # Preserve frozen tables but explicitly supersede obsolete prose; post-hoc is separately labeled.
    frozen=original.split('## 瑞士主判与 MAE',1)[1]
    frozen='## 瑞士主判与 MAE'+frozen
    frozen=frozen.replace('强风阈值为每站训练期 P95。','冻结实现的强风阈值为每站×时效六小时间隔训练配对观测 P95（与预注册"该站全体原生 10 分钟观测 P95"不一致）；原生 P95 的并列值在后文事后补算。')
    frozen=frozen.replace('Top-k 的事件合并口径尚未实现，不能把按条捕获率冒充按事件；随机期望需基于同一检验集合的事件率核算，本轮未在归档表中生成。','冻结脚本仅实现按条 Top-k；按事件及随机期望已事后补算，见下节。随机按条期望为 k%（精确为 ceil(Nk)/N）。')
    frozen=frozen.replace('6 h 发布延迟敏感性：归档','6 h 延迟按构造无信息量：固定 init 与 fhr，仅改 issue 标签而不改预测，故与 4 h 数值相同；4 h 发布延迟仍是假设。归档')
    frozen=frozen.replace('强风按事件 Top-k 与随机期望缺口须明确标为未完成；本报告不能声称预注册第 6 节逐项全部完成。','冻结评分脚本没有按事件 Top-k 与随机期望；审后事后补算已并报，不能当作冻结脚本原输出。')
    frozen=frozen.replace('此为未经独立审查的实验报告','经独立六审 e83a060b、有保留支持的实验报告')
    # Provenance and predeclared verdict appear before all numerical tables.
    intro='''# R23.2-03 M5 降尺度层首试 · 六审后定稿（10-27 EDT）

本报告以六审 e83a060b 裁决为准。冻结结果与事后补算严格分层；冻结脚本 `m5_score.py`、配置、预注册未改。所有科学判断限本配置、瑞士冻结 12 站和这个冬季；下列敏感性不回写原主判。审查裁决 `04_Decisions/R23.2_M5结果_审查e83a060b_裁决_20261027.md`。

## 冻结结果（预注册主判）

主判 D(L)=(MAE_D2−MAE_T0)/MAE_T0，L=fhr−4 h，整日同网联合重抽 1000 次。四档 95% 上界均 <0，达到预注册至少一档通过的条件，止损未触发；T0 却比原始 R 更差，因此不能仅以 D2 对 T0 的 33% 差值表述降尺度收益。D2 对原始 R 的事后差值、逐站差异和边界敏感性见下节。`output_swiss/gate.json`、`output_swiss/swiss_scores_delay4.csv`、`supplement/supplement_metrics.csv`。

'''
    post=['## 事后补算（10-27，结果已见后补定；不参加原主判）','',
        '源：`review_m5/score_stage/output/swiss_predictions_delay4.parquet`、`pairs/score_stage_archive.tgz` 的训练/检验配对与冻结预测、`pairs/train_complete_20261027.tgz` 中原生 10 分钟站点观测；不重取 GFS。脚本 `m5_postreview.py` 与数值表均在本目录 `supplement2/`。每个时效用同网同 UTC 检验日作为块、1000 次有放回重抽；站内 AUC 每次先按站计算，再对可定义站算术平均。事件跨日 ID 固定，重复抽日不拆事件。', '',
        '### 训练—检验边界敏感性', '',
        '第一档只过滤 issue_utc≥2024-01-01 00:00 UTC，沿用冻结预测；第二档对每 fhr 的 LOSO 系数仅用 valid_end 早于该 fhr 最早检验 issue 的训练行重拟合，按原设计矩阵预测原检验行（原生阈值不参与拟合）。两者均事后补定，原判仍以全部冻结行与原拟合为准；D 区间是配对日块，不是模型重拟合不确定性。数值源 `supplement2/boundary_gates.csv`、`supplement2/refit_cutoffs.csv`。', '',
        '| fhr h | 过滤 issue≥1月1日 D [95%] / n | 训练边界重拟合 D [95%] / n |', '|---:|---:|---:|']
    for h in (6,12,24,48):
        a=next(x for x in gates if x['tag']=='issue_ge_Jan1' and int(x['fhr'])==h);b=next(x for x in gates if x['tag']=='refit_train_before_first_issue' and int(x['fhr'])==h)
        post.append(f"| {h} | {fmt(a,'D')} / {a['n']} | {fmt(b,'D')} / {b['n']} |")
    post+=['','### 站内与合并强风 AUC', '',
        '站内 AUC 先在各站以本站事件阈值计算，再对 12 站等权平均；合并 AUC 则将各站绝对风速混排，二者并非同一排序对象。以下均以原生 10 分钟训练观测 P95 事后重算；与冻结合并 AUC 的阈值差异另见下一节。站内 12 站原值见 `supplement2/station_auc.csv`，区间及合并值见 `supplement2/secondary_ci.csv`。', '',
        '| fhr | 方法 | 站内均值 AUC [95%] | 合并 AUC [95%] | 冻结合并 AUC 点值 |','|---:|---|---:|---:|---:|']
    for h in (6,12,24,48):
        for m in ('R','T0','D1','D2','M','M+D1'):
            a=get(metrics,h,'station_mean_AUC_'+m); b=get(metrics,h,'AUC_'+m)
            post.append(f"| {h} | {m} | {fmt(a)} | {fmt(b)} | {float(a['original_point']):.3f} |")
    post+=['','### 阈值实现偏离与 Top-k', '',
        '冻结阈值按站×fhr 的六小时间隔训练配对观测 P95，而预注册要求本站训练期全部原生 10 分钟观测 P95。以下原生阈值为事后纠偏，不改原判：每站的原生样本数与阈值见 `supplement2/native_thresholds.csv`；六方法四档 AUC、按条 Top-k 的冻结点值与原生阈值点值及原生日块 95% 区间见 `supplement2/secondary_ci.csv`，按事件的原生阈值事后结果也在同一 CSV。事件仍按本站原生连续超阈 10 分钟行（相邻超阈间隔 ≤40 min）合并；分母只含评分行命中的事件。旧阈值的按事件结果见 `supplement/supplement_metrics.csv`，不可混作同阈值的配对差值。', '',
        '| fhr | 方法 | AUC 冻结点值→原生 P95 [95%] | Top5 按条 冻结点值→原生 P95 [95%] | Top5 按事件 原生 P95 [95%] |', '|---:|---|---:|---:|---:|']
    for h in (6,12,24,48):
        for m in ('R','T0','D1','D2','M','M+D1'):
            a=get(metrics,h,'AUC_'+m); b=get(metrics,h,'Top5_'+m); c=get(metrics,h,'eventTop5_'+m)
            post.append(f"| {h} | {m} | {float(a['original_point']):.3f}→{fmt(a)} | {float(b['original_point']):.3f}→{fmt(b)} | {fmt(c)} |")
    post+=['', '### 分站覆盖率与 M+D1 增量', '',
        '逐站名义 80%/90% 经验残差区间覆盖率六列见 `supplement2/station_coverage.csv`（四档×12站），不是单站校准概率。D2 合并名义 90% 只覆盖约 0.852–0.857，80% 约 0.729–0.736（`output_swiss/swiss_scores_delay4.csv`）。M+D1 相对 M 的逐站 MAE 差见 `supplement2/station_increment.csv`；dz<0 的 BLA/GOS/ROB/BUF/SAM 因 V1≡R，按构造无新增线性特征（数值误差近零），不得外推谷地。合并相对增量为 −11.5/−10.8/−9.8/−7.5%（按原 `output_swiss/swiss_scores_delay4.csv` 绝对差除以 M 的 MAE）。', '',
        '### 随机排序期望、巴黎与 CorrDiff', '',
        '按条随机 Top-k 期望=ceil(Nk)/N，约 k%；按事件按每事件评分行数解析计算，四档 1/5/10% 为 0.012/0.060/0.118，出处 `supplement/supplement.md` 及 `supplement/supplement_metrics.csv` 点值；该 CSV 的 random_event_top* 区间错误，不引用。巴黎副臂仅描述：M 点值优于 R100，H_log 点 MAE 低于 M，但 fhr24 的 ρ 区间跨 1，H_2seg100 与 H_log 近乎重合并非独立证据；实际观测只覆盖至 2024-02-06，不作本站订正优劣判断（`pairs/paris_score_final/paris_metrics.csv`）。CorrDiff 只读可行性见 `corrdiff_feasibility.md`，本轮未跑。', '',
        '### 裁决后限定结论', '']
    passes=all(float(x['hi'])<0 for x in gates)
    if passes:
        verdict='两档事后边界敏感性的四个时效上界也均 <0；这只是对所测边界泄漏处理的稳健性，不提升原判或扩大适用域。'
    else:
        verdict='事后边界敏感性至少一档上界≥0，原判仍按冻结规则成立，但对边界处理不稳健；不能把原判当作无条件的起报时刻可用预测。'
    post.append('在 GFS 0.25°、发布延迟 4 h（未验证假设）、瑞士冻结 12 站、2023 年 10–12 月训练、2024 年 1–3 月检验的配置下，逐站留一时，D2 的 10 分钟平均风速合并 MAE 比原始 GFS 低约 27–28%，比预注册朴素迁移 T0 低约 33%；冻结四档 95% 上界均 <0，预注册主判通过。T0 比原始 GFS 更差；对原始 GFS 的分站改善只在 7/12（48 h 8/12），改善集中在高出模式地面的两个山脊站，山口类不如 T0、谷地类不如原始 GFS。'+verdict+'结论仅针对平均风速点预报，不能表述为强风预警改善或全面变差；D2 区间欠覆盖，不可用于单站风险表述。')
    # Frozen original prose still contains superseded caveats: explicitly mark table region as historical and prevent duplicate final reading.
    # Append numeric tables only, avoiding old incorrect prose after the tables.
    extra=supplement.split('## 相对原始 R 的 MAE 差',1)[1].split('## delay6 与限制',1)[0]
    body=intro+frozen+'\n\n'+'\n'.join(post)+'\n\n## 审后合并原副指标明细（事后实现 10-27）\n\n## 相对原始 R 的 MAE 差'+extra+'\n'
    (R/'results.md').write_text(body)
    print('REPORT_WRITTEN',len(body),'boundary_all_upper_negative',passes)
if __name__=='__main__':main()
