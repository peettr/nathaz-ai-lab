#!/usr/bin/env python3
"""A170② frozen order-statistics report from actual per-run JSON archive."""
import json,statistics,tarfile,hashlib,os
from pathlib import Path
HERE=Path(__file__).resolve().parent
SEEDS=list(range(1301,1337));WOOD=SEEDS[:12]
FIELDS={'yaw':'tower_top_yaw_absmax_kNm','tower':'tower_fore_aft_negative_magnitude_kNm','blade':'blade_root_negative_magnitude_kNm'}
BASE={'yaw':13.892,'tower':-8.633,'blade':2.092}
def read_archive(p):
 with tarfile.open(p) as tf:
  return {Path(m.name).name:json.load(tf.extractfile(m)) for m in tf if m.isfile() and m.name.endswith('.json')}
def cmp(rows,group,seeds):
 pair=[];excluded=[]
 for seed in seeds:
  lhs=rows.get(f'P1_{group[0]}_s{seed}_G1.json');rhs=rows.get(f'P1_{group[0]}_s{seed}_{group[1]}.json')
  if lhs is None or rhs is None or any(x.get('returncode')!=0 or x.get('yaw_rate_max_deg_s',float('inf'))>.31 for x in (lhs,rhs)):
   excluded.append(seed)
  else:pair.append((seed,lhs,rhs))
 out={'valid_seeds':[x[0] for x in pair],'excluded_seeds':excluded,'n_valid':len(pair),'n_not_judged':len(excluded),'metrics':{}}
 for k,f in FIELDS.items():
  v=[100*(a['metrics'][f]-b['metrics'][f])/a['metrics'][f] for _,a,b in pair]
  order=sorted(v); interval=[order[11],order[24]] if len(v)>=30 else None
  if interval is None:verdict='不判'
  elif k=='yaw':verdict='成立' if interval[0]>=10 else '不成立' if interval[1]<10 else '说不清'
  else:verdict='成立' if interval[0]>=-10 else '不成立' if interval[1]<-10 else '说不清'
  out['metrics'][k]={'median_pct':statistics.median(v) if v else None,'interval_R12_R25_pct':interval,'verdict':verdict,'per_seed':dict(zip([x[0] for x in pair],v))}
 out['a']=out['metrics']['yaw']['verdict'];states=[out['metrics'][k]['verdict'] for k in ('tower','blade')]
 out['b']='不判' if '不判' in states else '不成立' if '不成立' in states else '成立' if states==['成立','成立'] else '说不清'
 return out

def main():
 p=Path(os.environ.get('A170_RESULTS_ARCHIVE',str(HERE/'colab_p1_1112'/'final_checkpoint.tar.gz')))
 if not p.is_file():raise FileNotFoundError(p)
 rows=read_archive(p)
 expected=[f'P1_power_s{s}_{g}.json' for s in SEEDS for g in ('G1','G2','G2Lc')]+[f'P1_wood_s{s}_{g}.json' for s in WOOD for g in ('G1','G2Lc')]
 missing=[k for k in expected if k not in rows]
 if missing:raise RuntimeError(f'incomplete per-run JSON: {len(missing)} missing; examples {missing[:8]}')
 out={'prereg':'PREREG_A170_2_CM1真实入流复核.md','P1_source_sha256':'e55cf7ea02fa5fda56bf276883fb874ac2ac4145c9a4d5cf1f70d25d06f877fb',
      'per_run':{k:rows[k] for k in expected},'comparison':{},'group_summary':{},'trigger_times':{}}
 lines=['# A170② CM1 D420 W3 真四维入流 P1 载荷复核','',
        '冻结：P1 通过 90m 3s≥27m/s；P2 未过不跑；全部降幅逐种子配对，偏航 1s 割线 >0.31°/s 或求解失败不判。','',
        '| 廓线 | 比较 | 指标 | 有效对 | 不判 | 中位降幅 % | [R(12), R(25)] % | 判定 |','|---|---|---|---:|---:|---:|---|---|']
 for profile,gs,seeds in [('power',('G2Lc','G2'),SEEDS),('wood',('G2Lc',),WOOD)]:
  for g in gs:
   c=cmp(rows,(profile,g),seeds);out['comparison'][f'{profile}_{g}']=c
   for k in FIELDS:
    x=c['metrics'][k];inter=x['interval_R12_R25_pct']; interval=('['+', '.join(f'{a:.3f}' for a in inter)+']') if inter else '不可计算'
    lines.append(f"| {profile} | {g} vs G1 | {k} | {c['n_valid']} | {c['n_not_judged']} | {x['median_pct']:.3f} | {interval} | {x['verdict']} |" if x['median_pct'] is not None else f'| {profile} | {g} vs G1 | {k} | 0 | {c["n_not_judged"]} | — | — | 不判 |')
   lines.append(f"| {profile} | 汇总 | (a)/(b) | {c['n_valid']} | {c['n_not_judged']} | — | — | {c['a']}/{c['b']} |")
  for g in ('G1',)+gs:
   rs=[rows[f'P1_{profile}_s{s}_{g}.json'] for s in seeds]
   ok=[r for r in rs if r.get('returncode')==0]
   rates=[r['yaw_rate_max_deg_s'] for r in ok]
   out['group_summary'][f'{profile}_{g}']=dict(successful=len(ok),rate_median_deg_s=statistics.median(rates),rate_max_deg_s=max(rates),rate_over_0p31_count=sum(v>.31 for v in rates),
      overspeed_median_pct=statistics.median(r['metrics']['rotor_speed_overshoot_vs_12p1_pct'] for r in ok),overspeed_max_pct=max(r['metrics']['rotor_speed_overshoot_vs_12p1_pct'] for r in ok))
   out['trigger_times'][f'{profile}_{g}']={str(s):rows[f'P1_{profile}_s{s}_{g}.json']['trigger_abs_s'] for s in seeds}
 lines+=['','| 廓线与组 | 成功 | 偏航速率 1s 割线中位/最大 °/s | >0.31 次数 | 转子超速幅度中位/最大 % |','|---|---:|---:|---:|---:|']
 for name,g in out['group_summary'].items():lines.append(f"| {name} | {g['successful']} | {g['rate_median_deg_s']:.5f}/{g['rate_max_deg_s']:.5f} | {g['rate_over_0p31_count']} | {g['overspeed_median_pct']:.3f}/{g['overspeed_max_pct']:.3f} |")
 c=out['comparison']['power_G2Lc'];base=BASE
 same=(c['a']=='说不清' and c['b']=='说不清' and all(abs(c['metrics'][k]['median_pct']-base[k])<=5 for k in FIELDS))
 out['pattern_same_as_A170_4']=same
 lines+=['',f"与 A170④ 同格局：{'是' if same else '否'}；基准三个中位依次 13.892%、−8.633%、2.092%，同时要求 (a)/(b) 均说不清、每项差≤5个百分点。",
         'Wood 仅12种子：冻结 n=36 [R(12),R(25)] 不可计算；仅报配对中位，不赋95%区间判定。',
         '时间来源：CM1 原模型秒 1860–2700；未缩放风速，超速幅度为相对12.1rpm的幅度而非计数。']
 meta={'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'checkpoint_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 out['provenance']=meta
 (HERE/'metrics_A170_2.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 lines.append('制表脚本 SHA256：'+meta['script_sha256'])
 (HERE/'RESULTS_A170_2.md').write_text('\n'.join(lines)+'\n')
 print('wrote',len(expected),meta)
if __name__=='__main__':main()
