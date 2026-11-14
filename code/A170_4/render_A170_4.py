#!/usr/bin/env python3
"""Recompute frozen A170④ gates directly from pulled per-run JSON archives.
Never fill missing runs or infer a gate from partial pairs.
"""
import json, statistics, tarfile, hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD=[112,203,317,419,523,631,733,827,941,1051,1163,1277]
NEW=list(range(1301,1325)); SEEDS=OLD+NEW
FIELDS={'yaw':'tower_top_yaw_absmax_kNm','tower':'tower_fore_aft_negative_magnitude_kNm','blade':'blade_root_negative_magnitude_kNm'}

def read_archive(path):
 with tarfile.open(path) as tf:
  return {f.name:json.load(tf.extractfile(f)) for f in tf if f.isfile() and f.name.endswith('.json')}
def metric(row,k):return row['metrics'][FIELDS[k]]
def verdict(lo,hi,kind):
 if kind=='a':return '成立' if lo>=10 else '不成立' if hi<10 else '说不清'
 return '成立' if lo>=-10 else '不成立' if hi< -10 else '说不清'
def percentile(vals):
 vals=sorted(vals)
 return [vals[11], vals[24]] if len(vals)==36 else None

def main():
 old=json.loads((HERE/'r2_reuse_I_near.json').read_text())
 new={}
 # Use the verified phase-1 recovery and complete phase-2 final archive only.
 for p in (HERE/'phase1/recovery_1111_0635.tar.gz', HERE/'phase2/final_checkpoint_lead_1111.tar.gz'):
  if not p.is_file(): raise FileNotFoundError(p)
  new.update(read_archive(p))
 merged={}
 for s in SEEDS:
  for g in ('G1','G2','G2Lc','G2L'):
   if g=='G2L' and s not in OLD:continue
   key=f'I_near_s{s}_{g}.json'; merged[key]=(old if s in OLD and g!='G2Lc' else new).get(key)
 missing=[k for k,v in merged.items() if v is None]
 if missing:raise RuntimeError(f'incomplete {len(missing)} keys: '+str(missing))
 assert len(merged)==120
 results={'source_old_sha256':hashlib.sha256((HERE/'r2_reuse_I_near.json').read_bytes()).hexdigest(),
          'prereg_sha256':'a8beda2423580bf3f151f4fab299563dbbb05a200a65611b4b01e0905f112a0c',
          'seed_count':36,'comparison':{},'per_run':merged,'original_12_G2Lc_vs_G2L':{},'c':'未重算'}
 lines=['# A170④：近中心盘面等效触发，36 种子','',
        '冻结判据：区间取 n=36 降幅有序值 [R(12), R(25)]；失败或高精度 1 s 割线 >0.31 的运行不判，剩余 <30 对整体不判。',
        '']
 for g in ('G1','G2','G2Lc'):
  rr=[merged[f'I_near_s{s}_{g}.json'] for s in SEEDS]
  ok=[r['yaw_rate_max_deg_s'] for r in rr if r.get('returncode')==0]
  summary={'successful':len(ok),'rate_median':statistics.median(ok),'rate_max':max(ok),'rate_over_count':sum(x>.31 for x in ok),
           'overspeed_median_pct':statistics.median(r['metrics']['rotor_speed_overshoot_vs_12p1_pct'] for r in rr if r.get('returncode')==0),
           'overspeed_max_pct':max(r['metrics']['rotor_speed_overshoot_vs_12p1_pct'] for r in rr if r.get('returncode')==0)}
  results.setdefault('group_summary',{})[g]=summary
  lines.append(f"{g}：速率中位/最大 {summary['rate_median']:.5f}/{summary['rate_max']:.5f} °/s；超 0.31 共 {summary['rate_over_count']}；超速幅度中位/最大 {summary['overspeed_median_pct']:.3f}/{summary['overspeed_max_pct']:.3f}%。")
 lines+=['','| 比较 | 指标 | 有效配对 | 不判数 | 中位降幅 % | 95% 次序区间 % | 判定 |','|---|---|---:|---:|---:|---|---|']
 for g in ('G2Lc','G2'):
  pair=[]; excluded=[]
  for s in SEEDS:
   a,b=merged[f'I_near_s{s}_G1.json'],merged[f'I_near_s{s}_{g}.json']
   if any(r.get('returncode')!=0 or r.get('yaw_rate_max_deg_s',float('inf'))>.31 for r in (a,b)):excluded.append(s)
   else:pair.append((s,a,b))
  comp={'valid_seeds':[s for s,_,_ in pair],'excluded_seeds':excluded,'metrics':{},'a':None,'b':None}
  for k in FIELDS:
   values=[100*(metric(a,k)-metric(b,k))/metric(a,k) for _,a,b in pair]
   interval=percentile(values)
   state=None if interval is None else verdict(*interval,'a' if k=='yaw' else 'b')
   comp['metrics'][k]={'per_seed_reduction_pct':dict(zip([s for s,_,_ in pair],values)),'median_pct':statistics.median(values) if values else None,'interval_95_order_pct':interval,'verdict':state}
   fmt=lambda x:'—' if x is None else f'{x:.3f}'
   lines.append(f"| {g} vs G1 | {k} | {len(pair)} | {len(excluded)} | {fmt(comp['metrics'][k]['median_pct'])} | {('['+fmt(interval[0])+', '+fmt(interval[1])+']') if interval else '少于36对，冻结区间不可计算'} | {state or '不判'} |")
  comp['a']=comp['metrics']['yaw']['verdict']
  states=[comp['metrics'][k]['verdict'] for k in ('tower','blade')]
  comp['b']=None if None in states else '不成立' if '不成立' in states else '成立' if states==['成立','成立'] else '说不清'
  results['comparison'][g]=comp
  lines.append(f"{g}： (a) {comp['a'] or '不判'}；(b) {comp['b'] or '不判'}；(c) 未重算。")
 for k in FIELDS:
  delta=[metric(merged[f'I_near_s{s}_G2Lc.json'],k)-metric(merged[f'I_near_s{s}_G2L.json'],k) for s in OLD]
  results['original_12_G2Lc_vs_G2L'][k]={'median_absolute_metric_difference':statistics.median(delta),'per_seed':dict(zip(OLD,delta))}
 d=[]
 for s in OLD:
  lc=merged[f'I_near_s{s}_G2Lc.json']['trigger_abs_s'];l=merged[f'I_near_s{s}_G2L.json']['trigger_abs_s'];d.append(None if lc is None or l is None else lc-l)
 results['original_12_G2Lc_vs_G2L']['trigger_delta_s']={'per_seed':dict(zip(OLD,d)),'median':statistics.median(x for x in d if x is not None) if any(x is not None for x in d) else None}
 lines+=['',f"原12种子 G2Lc−G2L 触发时刻差中位：{results['original_12_G2Lc_vs_G2L']['trigger_delta_s']['median']} s；逐种子及三载荷差见 JSON。",
          '仅适用于冻结预注册的 Case I 合成入流、此控制器与 8°/s 顺桨；(c) 未重算。']
 output=HERE/'metrics_A170_4.json';output.write_text(json.dumps(results,ensure_ascii=False,indent=2))
 (HERE/'RESULTS_A170_4.md').write_text('\n'.join(lines)+'\n')
 print(output,HERE/'RESULTS_A170_4.md')
if __name__=='__main__':main()
