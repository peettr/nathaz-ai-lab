#!/usr/bin/env python3
"""Render frozen v4 decision metrics only from rows_v4.csv; 10k paired event bootstrap."""
import csv,json,math,statistics
from collections import defaultdict
from pathlib import Path
import numpy as np
D=Path(__file__).resolve().parent
EVENTS=('BERYL','DEBBY','DELTA','FRANCINE','HELENE','IAN','MILTON','NICOLE','ZETA')
VARIANTS=('V0','VK','PH','VK_land')
def read(name):
 with (D/name).open(newline='') as f:return list(csv.DictReader(f))
def median(x):return float(np.median(x))
def verdict(B,R):
 if abs(B)<=.10:return '基本收回'
 if B>.10:return '过冲'
 if R>=.5:return '部分收回'
 if R>=.2:return '收回有限'
 return '未收回'
def fmt(x):return f'{100*x:.2f}%'
def interval(x,percent=True):
 lo,hi=np.percentile(x,[2.5,97.5]);return f'[{fmt(lo)}, {fmt(hi)}]' if percent else f'[{lo:.3f}, {hi:.3f}]'
def main():
 rows=read('rows_v4.csv');nodes=read('node_params.csv');gate=json.loads((D/'v0_gate.json').read_text())
 assert gate['passed']
 groups=defaultdict(list)
 for r in rows:groups[(r['variant'],r['chain'],r['event'])].append(r)
 assert len(rows)==176,len(rows)
 roster={(x['event'],x['station']) for x in read('sample_list.csv') if x['status']=='include'}
 assert len(roster)==22
 for variant in VARIANTS:
  for chain in ('b','c'):
   assert {(x['event'],x['station']) for x in rows if (x['variant'],x['chain'])==(variant,chain)}==roster
   for ev in EVENTS:assert groups[(variant,chain,ev)]
 by={(variant,chain,ev):np.array([float(x['err_s']) for x in groups[(variant,chain,ev)]]) for variant in VARIANTS for chain in ('b','c') for ev in EVENTS}
 def allerrs(variant,chain,indices=range(9)):
  return np.concatenate([by[(variant,chain,EVENTS[i])] for i in indices])
 def B(variant,chain,indices=range(9)):return median(allerrs(variant,chain,indices))
 def M(variant,chain,indices=range(9)):return median(np.abs(allerrs(variant,chain,indices)))
 rng=np.random.default_rng(20261126);draws=rng.integers(0,9,size=(10000,9))
 bci={};rci={};rhoci={};out=[]
 for variant in VARIANTS:
  for chain in ('b','c'):
   b=B(variant,chain);m=M(variant,chain)
   vals=np.array([B(variant,chain,d) for d in draws]);bci[(variant,chain)]=vals
   recovered=(b-B('V0',chain))/-B('V0',chain) if variant!='V0' else 0
   if variant!='V0':
    rs=np.array([(B(variant,chain,d)-B('V0',chain,d))/-B('V0',chain,d) if B('V0',chain,d)!=0 else np.nan for d in draws]);rci[(variant,chain)]=rs[np.isfinite(rs)]
   moved=sum(abs(median(by[(variant,chain,ev)]))<abs(median(by[('V0',chain,ev)])) for ev in EVENTS)
   out.append(dict(variant=variant,chain=chain,B=b,M=m,R=recovered,moved=moved))
  rho=M(variant,'c')/M(variant,'b')
  logboot=np.array([math.log(M(variant,'c',d)/M(variant,'b',d)) for d in draws]);rhoci[variant]=logboot
  count=sum(median(np.abs(by[(variant,'c',ev)]))<=median(np.abs(by[(variant,'b',ev)])) for ev in EVENTS)
  concordance=count if rho<=1 else 9-count
  show=(np.percentile(logboot,2.5)>0 or np.percentile(logboot,97.5)<0) and concordance>=7
  for q in out:
   if q['variant']==variant:q.update(rho=rho,wins=count,concordance=concordance,show=show)
 headings=['# R23.3a-06 v4 经验公式：冻结协议结果','','仅本配置、s2b 9 事件22 eligible 站、48h OFCL/Pangu 路径与共用 OFCL 强度；不翻 s2b 原判闸。观测为固定 v1 一分钟 ASOS sknt 持续风峰（实际约2分钟持续风代理，不是严格1分钟平均）。','', '## V0 复现闸','']
 for key,label in [('b_B','(b) B'),('b_M','(b) M'),('c_M','(c) M')]:headings.append(f'- {label}: {fmt(gate["values"][key])}；s2b {fmt(gate["s2b"][key])}；差 {gate["difference_pp"][key]:+.5f} pp。')
 headings+=['','## 两链全站持续风（由 rows_v4.csv 生成）','','| 组 | 链 | B 中位偏差 | M 中位绝对误差 | B 95% CI | Q1 收回比例 R | R 95% CI | Q1 判词 | 事件中位 e 向0 /9 |','|---|---|---:|---:|---|---:|---|---|---:|']
 for q in out:
  va,ch=q['variant'],q['chain']; R=q['R']
  label=verdict(q['B'],R) if va!='V0' else '基线'
  lo,hi=np.percentile(bci[(va,ch)],[2.5,97.5])
  if va!='V0':
   possible={verdict(bb,rr) for bb in (lo,hi) for rr in np.percentile(rci[(va,ch)],[2.5,97.5])}
   if len(possible)>1:label+='；区间跨 '+ '、'.join(sorted(possible))+' 两档' if len(possible)==2 else '；区间跨多档'
  headings.append(f'| {va} | {ch} | {fmt(q["B"])} | {fmt(q["M"])} | {interval(bci[(va,ch)])} | {fmt(R) if va!="V0" else "—"} | {interval(rci[(va,ch)]) if va!="V0" else "—"} | {label} | {q["moved"]}/9 |')
 headings+=['','## Q2 路径差异（事件配对 bootstrap 10000 次、种子 20261126）','','| 组 | ρ=M_c/M_b | lnρ 95% CI | (c)≤(b) 事件数 | 能否看出 | s2b 双重闸口径（仅并列） |','|---|---:|---|---:|---|---|']
 for va in VARIANTS:
  q=next(x for x in out if x['variant']==va)
  headings.append(f'| {va} | {q["rho"]:.4f} | {interval(rhoci[va],False)} | {q["wins"]}/9 | {"能看出差别（c 更好）" if q["show"] and q["rho"]<1 else "能看出差别（c 更差）" if q["show"] else "看不出（本样本分辨力不足）"} | ρ≤1.1：{q["rho"]<=1.1}；≥6/9：{q["wins"]>=6} |')
 vk=next(x for x in out if x['variant']=='VK');ph=next(x for x in out if x['variant']=='PH')
 overall='两组公式下一致看出 AI 路径更好' if vk['show'] and ph['show'] and vk['rho']<1 and ph['rho']<1 else '两组公式下一致看出 AI 路径更差' if vk['show'] and ph['show'] and vk['rho']>1 and ph['rho']>1 else '取决于公式组，不下结论' if vk['show'] or ph['show'] else '两组均看不出（本样本分辨力不足）'
 bad=[x for x in nodes if x['nonconverged']=='1'];cut=[x for x in nodes if x['rmw_truncated']=='1']
 headings+=['',f'两组综合：{overall}。',f'节点：{len(nodes)} 条（三变体×两链×九事件×97节点）；VK/VK_land 不收敛 {len(bad)}；PH 地面 RMW <5km 截断 {len(cut)}。', 'VK_land 是敏感性，只描述不进入主判读。Liang Hu 组回归为飞行层拟合；按原论文印刷 p.370–371 回归式精度比实测低一级，一般不宜用于 TCBL 模型验证；这里仅替代业务链输入，不用于验证风场模型。VW08 的 Vm→Δp 用 H08 Eq.(7) 工程闭合，并非 VW08 原式。','']
 (D/'RESULTS_v4.md').write_text('\n'.join(headings))
 print('rows',len(rows),'nodes',len(nodes),'nonconverged',len(bad),'cut',len(cut));print('Q2',[(x['variant'],x['rho'],x['wins'],x['show']) for x in out])
if __name__=='__main__':main()
