#!/usr/bin/env python3
"""Render frozen M4 output CSVs; no model refit or scoring."""
import csv, json, html
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output_v3'
LEADS=(10,20,30,60,120,180,240,300,360)
METHODS=('P','F','B','O','C','R')
def rows(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def f(v,n=3):
    return '—' if v in ('',None) else f'{float(v):.{n}f}'
def table(header, values):
    return '| '+' | '.join(header)+' |\n|'+ '|'.join(['---']*len(header))+'|\n'+''.join('| '+' | '.join(map(str,v))+' |\n' for v in values)
def mae(net,src,delay):
    rr=rows(OUT/f'{net}_{src}_delay{delay}_mae.csv')
    assert len(rr)==54, (net,src,delay,len(rr))
    assert {(int(x['lead_min']),x['method']) for x in rr}=={(l,m) for l in LEADS for m in METHODS}
    return {(int(x['lead_min']),x['method']):x for x in rr}
def sec(net,src,delay):return rows(OUT/f'{net}_{src}_delay{delay}_secondary.csv')
base={n:mae(n,'GFS',4) for n in ('OKC','Swiss')}
assert (ROOT/'pipeline_v4.exit').read_text().strip()=='0'
assert (OUT/'stop_loss.txt').read_text().strip()=='False'
allfiles=list(OUT.glob('*'))
assert len(allfiles)==25, len(allfiles)
parts=[]
def add(s=''):parts.append(s+'\n')
add('## 最终结果（10-25 06:30 EDT；附于原中间状态后，原文保留供溯源）')
add('本节取代本文件上方“尚未读取检验期”的旧中间状态。Colab `r23-2-m4-v3` 流水线退出码 0，保活 `done` 且 `final_pull_state=ok`；评分 CSV 全部落盘，`stop_loss.txt=False`。会话已 stop 并查为不存在。逐阶段配对包存 `pairs/`，合并 final checkpoint 为 312 MB、超单文件拉取上限而未拉；不影响已经拉回的逐阶段包与全部小结果。')
add('口径：D(L)=[MAE_B−min(MAE_P,MAE_F)]/min(MAE_P,MAE_F)，分母及 min 在每次按检验日整块重抽中重新计算；1000 次重抽、分位数 2.5%–97.5%。负值为相对较好者的 MAE 改善，只有 D 上界 <0 才算“更好”。GFS 延迟 4 h 是未获历史逐文件发布时间证实的假设；3/6 h 仅敏感性。瑞士 C′为跨月退化副参照，按原 C 定义瑞士不可算。')
add('主判：两个网的九个提前量 D 上界均小于 0，因此预注册的“至少一个网一档上界 <0”在本配置下通过、两网全档上界 ≥0 的止损未触发。这只描述本次 OKC 2023 和瑞士 2024-01–03 的这套 GFS 0.25°＋线性订正＋指数融合配置，不作因果归因或外推。未经独立审查，不称“可写论文”。')
add('### 主判 D(L) 与 95% 日块区间')
for net in base:
    d=base[net]
    add(net+'：')
    add(table(['L/min','N','MAE_P','MAE_F','MAE_B','D','D_lo','D_hi'],[(l,d[l,'B']['n'],f(d[l,'P']['mae']),f(d[l,'F']['mae']),f(d[l,'B']['mae']),f(d[l,'B']['D'],4),f(d[l,'B']['D_lo'],4),f(d[l,'B']['D_hi'],4)) for l in LEADS]))
add('### 六条 MAE 曲线（m/s；每格 点估计 [日块95%下限,上限]）')
for net in base:
    d=base[net];add(net+'：')
    add(table(['L/min']+list(METHODS),[[l]+[f(d[l,m]['mae'])+' ['+f(d[l,m]['lo'])+','+f(d[l,m]['hi'])+']' for m in METHODS] for l in LEADS]))
add('原始逐行精度：`output_v3/{OKC,Swiss}_GFS_delay4_mae.csv`。')
add('### 强风排序与 Top-k（阈值为各站训练期 P95）')
for net in base:
    s=sec(net,'GFS',4)
    s=[x for x in s if x['metric']=='auc_topk']
    assert len(s)==81, (net,len(s))
    add(net+'：每个 L、方法给 AUC；k=1/5/10% 依次为“条捕获率/事件捕获率”，随机期望给条/事件；事件按完整观测序列相隔不超过 30 min 合并。')
    rr=[]
    for l in LEADS:
        by={(int(x['lead_min']),x['method'],x['k_fraction']):x for x in s}
        for m in ('P','F','B'):
            xs=[by[l,m,str(k)] for k in (.01,.05,.1)]
            rr.append((l,m,f(xs[0]['auc']),xs[0]['strong_rows'],xs[0]['events'])+tuple(f(x['topk_rows'])+'/'+f(x['topk_events']) for x in xs))
    add(table(['L','法','AUC','强风条','事件','1%条/事件','5%条/事件','10%条/事件'],rr))
    first=by[10,'B','0.01']
    add('随机排序期望按每一档 eligible 行数和事件长度从 CSV 读取，逐档表见 `output_v3/'+net+'_GFS_delay4_secondary.csv`；例如 L=10 min：k=1% 的条/事件期望 '+f(first['random_expectation_rows'])+'/'+f(first['random_expectation_events'])+'。')
add('### 区间覆盖率（F、B；网内残差为主、同站敏感性）')
for net in base:
    s=[x for x in sec(net,'GFS',4) if x['metric']=='coverage']
    assert s
    add(net+'：名义 80%/90%；每格覆盖比例 (N条，E个强风事件)。台风在两网无样本；瑞士非对流标签为假设。事件数少于 30 的格只报数不作判读。')
    rr=[]
    for l in LEADS:
        for m in ('F','B'):
            for grouping in ('net','site'):
                for hazard in (('all','convective','nonconvective') if net=='OKC' else ('all','nonconvective_assumed')):
                    bucket=[x for x in s if int(x['lead_min'])==l and x['method']==m and x['grouping']==grouping and x['hazard']==hazard]
                    assert len(bucket)==2,(net,l,m,grouping,hazard,bucket)
                    by={int(float(x['nominal'])):x for x in bucket}
                    x=by[80];y=by[90]
                    rr.append((l,m,grouping,hazard,f(x['coverage'])+'/'+f(y['coverage']),x['n'],x['events']))
    add(table(['L','法','残差','灾种','80/90','N条','E强风事件'],rr))
add('### 两种转折时刻')
add(table(['网','MAE_F≤MAE_P 最短 L','O: c1<c2 最短 L'],[(n,json.loads((OUT/f'{n}_GFS_delay4_turning.json').read_text())['F_le_P'],json.loads((OUT/f'{n}_GFS_delay4_turning.json').read_text())['O_c1_lt_c2']) for n in base]))
add('### AIWP 副臂（发布延迟 6 h 假设；F_AI 与 B_AI 的 MAE，日块95%区间）')
for net in base:
    d=mae(net,'AIWP',6)
    add(net+'：')
    add(table(['L','N','F_AI [lo,hi]','B_AI [lo,hi]'],[(l,d[l,'B']['n'],f(d[l,'F']['mae'])+' ['+f(d[l,'F']['lo'])+','+f(d[l,'F']['hi'])+']',f(d[l,'B']['mae'])+' ['+f(d[l,'B']['lo'])+','+f(d[l,'B']['hi'])+']') for l in LEADS]))
add('### GFS 发布延迟 3 h 与 6 h 敏感性（不参加主判）')
for net in base:
    a=mae(net,'GFS',3);b=mae(net,'GFS',6)
    add(net+'：')
    add(table(['L','3h D [lo,hi]','6h D [lo,hi]'],[(l,f(a[l,'B']['D'],4)+' ['+f(a[l,'B']['D_lo'],4)+','+f(a[l,'B']['D_hi'],4)+']',f(b[l,'B']['D'],4)+' ['+f(b[l,'B']['D_lo'],4)+','+f(b[l,'B']['D_hi'],4)+']') for l in LEADS]))
add('### 可复核范围与限制')
add('原始评分输出为 `output_v3/` 的 25 个小文件；每组 9 提前量×6 方法，覆盖率和排序逐档 CSV 都留在该目录。冻结评分 `m4_score.py` SHA256 c392602440660b6391edc7ca72d719e4874b2bcb00b9bdf2d9fd48fbf6ee5ad6；`config.json` SHA256 56caad7694c5b3df9830a940651c72f7af7bd9efebee6bdeb434ea3e6c3e2b6f，核对未变。`score_guard.py` 逐行检查截止不晚于 issue 且 init＋假设延迟不晚于 issue。AUC/Top-k 输出没有置信区间，接口 v0.1 第 6 节要求的“分段增量”区间因此未全部满足；不得宣称这一项已完成。最终 312 MB 整包未落 工作站，训练、检验逐段小包已保存；若要逐行复算需从小包重组。')
report='\n'.join(parts)
# Preserve the existing intermediate result verbatim; append final findings only.
p=ROOT/'results.md'
old=p.read_text()
if '## 最终结果（10-25 06:30 EDT' in old:raise RuntimeError('final report already appended')
with p.open('a') as f:f.write('\n'+report)
print('appended final section',len(report),'chars',len(allfiles),'output files')
