"""Render archived Colab M5 scores; no fitting/bootstrap on 工作站."""
import csv, io, json, tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
ARCH=ROOT/'pairs/score_stage_archive.tgz'
PARIS=ROOT/'pairs/paris_score_final/paris_metrics.csv'
with tarfile.open(ARCH) as tar:
    def item(name): return tar.extractfile('output/'+name).read().decode()
    gate=json.loads(item('gate.json'))
    swiss=list(csv.DictReader(io.StringIO(item('swiss_scores_delay4.csv'))))
    delay6=list(csv.DictReader(io.StringIO(item('swiss_scores_delay6.csv'))))
    terrain=list(csv.DictReader(io.StringIO(item('swiss_terrain_mae.csv'))))
paris=list(csv.DictReader(PARIS.open()))
def pick(rows,fhr,metric):
    return next(r for r in rows if r['fhr']==str(fhr) and (r.get('metric') or r.get('method_metric'))==metric)
def val(r,ci=False):
    v=f"{float(r['point']):.3f}"
    if ci and r.get('lo') and r.get('hi'):v+=f" [{float(r['lo']):.3f}, {float(r['hi']):.3f}]"
    return v
h=[6,12,24,48]
lines=['# R23.2-03 M5 降尺度层首试结果（10-27，EDT）','',
 '主判：在这套配置、瑞士冻结 12 站的 2024 年 1–3 月检验期，四个时效的 D=(MAE_D2−MAE_T0)/MAE_T0 日块自助 95% 区间上界均小于 0；满足预注册「至少一档」的通过条件，未触发止损。此为未经独立审查的实验报告，不外推其他区域或季节。', '',
 '来源：`pairs/score_stage_archive.tgz`（Colab 评分退出码 0；训练/检验配对 17,604/17,432 行；含 `output/swiss_scores_delay4.csv`、`output/swiss_scores_delay6.csv`、`output/swiss_terrain_mae.csv` 和 `output/gate.json`）。瑞士每时效 4,358 条检验配对、91 个检验日、1000 次整日网络联合重抽。所有区间为 95%，MAE 单位 m/s。方法和判据见冻结预注册第 4–7 节。','',
 '## 瑞士主判与 MAE','',
 '| fhr h (L h) | R MAE | T0 MAE | D1 MAE | D2 MAE | M MAE | M+D1 MAE | D (95% CI) |','|---|---:|---:|---:|---:|---:|---:|---:|']
for f in h:
    a=[val(pick(swiss,f,'MAE_'+m)) for m in ['R','T0','D1','D2','M','M+D1']]
    lines.append('| '+f'{f} ({f-4})'+' | '+' | '.join(a+[val(pick(swiss,f,'D'),True)])+' |')
lines += ['', '## 瑞士副指标（delay 4 h）','',
 '恢复比例 ρ=(MAE_T0−MAE_D2)/(MAE_T0−MAE_M)；Δ(M+D1)=MAE_M+D1−MAE_M；增量「a→b」均为 MAE_b−MAE_a。下表每格为点值 [95% 日块区间]。','',
 '| fhr | ρ | D1 对 T0 相对差 | Δ(M+D1) | R→T0 | T0→D2 | R→M | M→M+D1 |','|---|---:|---:|---:|---:|---:|---:|---:|']
for f in h:
    ms=['rho','D1_T0','M+D1_minus_M','MAE_R_to_T0','MAE_T0_to_D2','MAE_R_to_M','MAE_M_to_M+D1']
    lines.append('| '+str(f)+' | '+' | '.join(val(pick(swiss,f,m),True) for m in ms)+' |')
lines += ['', '强风阈值为每站训练期 P95。AUC、Top-k 捕获率（按条）的全部方法点值与日块 95% 区间均在归档 CSV；这里列出 T0、D2、M 的 AUC 和 Top 1/5/10% 捕获率。Top-k 的事件合并口径尚未实现，不能把按条捕获率冒充按事件；随机期望需基于同一检验集合的事件率核算，本轮未在归档表中生成。','',
 '| fhr | 方法 | AUC [95% CI] | Top1 [95% CI] | Top5 [95% CI] | Top10 [95% CI] |','|---|---|---:|---:|---:|---:|']
for f in h:
 for m in ['T0','D2','M']:
    lines.append('| '+str(f)+' | '+m+' | '+' | '.join(val(pick(swiss,f,k+'_'+m),True) for k in ['AUC','Top1','Top5','Top10'])+' |')
lines += ['', '覆盖率：瑞士冷季全部暂归非对流（假设），每时效 n=4,358；下表均为实测覆盖率点值，80%/90% 名义档的完整日块区间在归档 CSV。','',
 '| fhr | T0 80/90 | D2 80/90 | M 80/90 |','|---|---:|---:|---:|']
for f in h:
 lines.append('| '+str(f)+' | '+' | '.join('/'.join(val(pick(swiss,f,'cover'+p+'_'+m)) for p in ['80','90']) for m in ['T0','D2','M'])+' |')
lines += ['', '地形分组：每类 3 站；下表只报 T0/D2 MAE，不以三站小样本作组间推断；六方法与每组样本量详见 `output/swiss_terrain_mae.csv`。','',
 '| fhr | 地形 | n | T0 | D2 |','|---|---|---:|---:|---:|']
for r in terrain:lines.append(f"| {r['fhr']} | {r['terrain']} | {r['n']} | {float(r['MAE_T0']):.3f} | {float(r['MAE_D2']):.3f} |")
lines += ['', '6 h 发布延迟敏感性：归档 `output/swiss_scores_delay6.csv` 的四档 D 点值与 delay 4 h 一致（下表）。fhr=6 时 issue=init+6 h，名义提前量为 0；本档不能称提前预报。原始表对 delay6 未产生区间，不将 delay4 区间移用。','',
 '| fhr | delay4 D | delay6 D | delay6 提前量 h |','|---|---:|---:|---:|']
for f in h:lines.append(f"| {f} | {val(pick(swiss,f,'D'))} | {val(pick(delay6,f,'D'))} | {f-6} |")
lines += ['', '## 巴黎 111 m 副臂（不参加主判）','',
 '来源：`pairs/paris_score_final/paris_metrics.csv`、`paris_manifest.json`、`paris_score.exit`（0）。训练配对 2,228，检验配对 1,568；四个时效各 392 条、98 个有效检验日，日块 1000 次。虽然请求 2023-11 至 2024-02，PALUPD 观测在本次实际只到 2024-02-06 18:50 UTC；有效配对最晚 02-06 18:00 UTC，不能声称完整冬季。季节不同且单站，只描述不下结论。','',
 '| fhr | R100 MAE | H_log MAE | H_2seg 60 m MAE | H_2seg 100/200 m MAE | M MAE | ρ H_log / 2seg60 |','|---|---:|---:|---:|---:|---:|---:|']
for f in h:
    get=lambda m: val(pick(paris,f,m),True)
    lines.append(f"| {f} | {get('MAE_R100')} | {get('MAE_H_log')} | {get('MAE_H_2seg_60')} | {get('MAE_H_2seg_100')} / {get('MAE_H_2seg_200')} | {get('MAE_M')} | {get('rho_H_log')} / {get('rho_H_2seg_60')} |")
lines += ['', '## CorrDiff 可行性与边界','',
 '只读核查见 `corrdiff_feasibility.md`：台湾现成权重不覆盖瑞士/巴黎/OKC；美国 GEFS→HRRR 商品卡覆盖 OKC 地理域，但输入不是本轮 GFS，许可与单次推理耗时未核实。本轮未下载权重、未作推理。','',
 '## 归档与限制','',
 '- Colab 会话 `r23-2-m5-cpu` 已在 10-27 14:12 EDT 停止并复核不在会话列表；巴黎评分的 keepalive `state=done`、`final_pull_state=ok`、退出码 0。',
 '- 冻结瑞士评分脚本和配置哈希见两份实验卡；巴黎副臂由 `m5_paris_score.py` 独立评分。配对检查点在 `pairs/`，每阶段已归档；未重跑瑞士评分。',
 '- 本任务没有独立 CU 账单；首项 2.009 h，整轮 0.394 CU 是按旧共享账户边际费率的事前条件投影，不当成实耗。',
 '- 强风按事件 Top-k 与随机期望缺口须明确标为未完成；本报告不能声称预注册第 6 节逐项全部完成。巴黎观测阶段退出码文件为空，但九个月观测 CSV 已逐件哈希核对，后续 GFS 与副臂评分均退出 0。',
 '- 结论只限该配置、这 12 站、这个冬季；给 Liang Hu 使用“结论成立/可写论文”措辞前按中心规则先独立六审。','']
out=ROOT/'results.md'
assert not out.exists(), 'refuse overwrite existing report'
out.write_text('\n'.join(lines),encoding='utf8')
print('WROTE',out,'lines',len(lines),'gate',gate)
