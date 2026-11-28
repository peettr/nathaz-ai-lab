"""Generate A170③ step1 report strictly from 72 paired JSON records and frozen r2 records."""
import hashlib,json,math,statistics
from pathlib import Path
from scipy.stats import wilcoxon
P=Path(__file__).resolve().parent
OLD=P.parent/'D_yawfix'/'r2'/'results'
SEEDS=[112,203,317,419,523,631,733,827,941,1051,1163,1277]
CASES=('I_near','III_kzm05','III_kzm00')
GROUPS=('G1','G2L')
K={'yaw':'tower_top_yaw_absmax_kNm','tower':'tower_fore_aft_negative_magnitude_kNm','blade':'blade_root_negative_magnitude_kNm'}
def collect(root):
 out={}
 for case in CASES:
  for seed in SEEDS:
   for group in GROUPS:
    path=root/f'{case}_s{seed}_{group}.json'
    assert path.exists(),path
    row=json.loads(path.read_text())
    assert row['case']==case and row['seed']==seed and row['group']==group and row['returncode']==0 and set(K.values())<=set(row['metrics']),path
    out[(case,seed,group)]=row
 assert len(out)==72
 return out
def stats(rows,case):
 a={}
 for group in GROUPS:
  vals=[rows[(case,s,group)] for s in SEEDS]
  rate=[v['yaw_rate_max_deg_s'] for v in vals]
  rpm=[v['metrics']['rotor_speed_overshoot_vs_12p1_pct'] for v in vals]
  a[group]={'rate_median_deg_s':statistics.median(rate),'rate_max_deg_s':max(rate),'rate_exceed_count':sum(x>.31 for x in rate),'overspeed_median_pct':statistics.median(rpm),'overspeed_max_pct':max(rpm),'overspeed_gt0_count':sum(x>0 for x in rpm)}
 for short,key in K.items():
  b=[rows[(case,s,'G1')]['metrics'][key] for s in SEEDS]
  v=[rows[(case,s,'G2L')]['metrics'][key] for s in SEEDS]
  assert all(x>0 for x in b)
  reductions=[100*(x-y)/x for x,y in zip(b,v)]
  diffs=[y-x for x,y in zip(b,v)]
  a[short]={'paired_reduction_pct':reductions,'median_reduction_pct':statistics.median(reductions),'g1_median_kNm':statistics.median(b),'g2l_median_kNm':statistics.median(v),'wilcoxon_two_sided_p':float(wilcoxon(diffs,zero_method='wilcox',alternative='two-sided').pvalue) if any(diffs) else 1.0}
 a['a']=a['yaw']['median_reduction_pct']>=10
 a['b']=a['tower']['median_reduction_pct']>=-10 and a['blade']['median_reduction_pct']>=-10
 return a
def fmt(x):return f'{x:+.2f}'
def main():
 now=collect(P/'results');old=collect(OLD)
 out={'source_new':'results/*.json','source_old':str(OLD),'n':72,'cases':{},'per_run':[],'method':'paired per-seed 100*(G1-G2L)/G1; two-sided paired Wilcoxon; high precision ES NacYaw 1 s secant','c':'未重算，沿用 r2'}
 for case in CASES:
  n=stats(now,case);o=stats(old,case)
  n['r2_8deg_s']=o
  n['rate_valid']=all(n[g]['rate_exceed_count']==0 for g in GROUPS)
  out['cases'][case]=n
  for seed in SEEDS:
   for group in GROUPS:
    row=now[(case,seed,group)]
    out['per_run'].append({'case':case,'seed':seed,'group':group,'trigger_abs_s':row.get('trigger_abs_s'),'returncode':row['returncode'],'yaw_rate_max_deg_s':row['yaw_rate_max_deg_s'],'rate_exceed':row['yaw_rate_max_deg_s']>.31,'rotor_speed_overshoot_vs_12p1_pct':row['metrics']['rotor_speed_overshoot_vs_12p1_pct'],'metrics':{key:row['metrics'][key] for key in K.values()}})
 near=out['cases']['I_near'];oldnear=near['r2_8deg_s']
 improvement=near['tower']['median_reduction_pct']-oldnear['tower']['median_reduction_pct']
 out['near_tower_improvement_pp']=improvement
 out['obvious_improvement']=improvement>=5
 out['elimination']=all(v['a'] and v['b'] and v['rate_valid'] for v in out['cases'].values())
 out['strict_evaluable']=all(v['rate_valid'] for v in out['cases'].values())
 out['overspeed_g2l_increment_gt10pp']=[case for case in CASES if 100*(out['cases'][case]['G2L']['overspeed_gt0_count']-out['cases'][case]['r2_8deg_s']['G2L']['overspeed_gt0_count'])/12>10]
 (P/'metrics_A170_3_step1.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
 lines=['# A170③ 第一步：停机顺桨速率 4°/s 配对敏感性','',f'完整运行 {out["n"]}/72；每路径同一12种子，G1 与 G2L 都为 4°/s；旧 r2 为 8°/s。高精度 ES NacYaw 的 1 s 割线；正降幅为减载，负值为恶化。Wilcoxon 双侧配对 p（探索性，未多重校正）。','','| 路径 | 4°/s 偏航峰降幅 / p | 4°/s 塔底前后负峰降幅 / p | 4°/s 三叶根负峰降幅 / p | 4°/s (a)/(b) | r2 8°/s 同三项降幅及 (a)/(b) |','|---|---:|---:|---:|---|---|']
 for case in CASES:
  n=out['cases'][case];o=n['r2_8deg_s']
  def cell(d,k):return f'{fmt(d[k]["median_reduction_pct"])}% / {d[k]["wilcoxon_two_sided_p"]:.6g}'
  gate=f'{n["a"]}/{n["b"]}' if n['rate_valid'] else '不判（速率超限）'
  lines.append(f'| {case} | {cell(n,"yaw")} | {cell(n,"tower")} | {cell(n,"blade")} | {gate} | {fmt(o["yaw"]["median_reduction_pct"])}% / {fmt(o["tower"]["median_reduction_pct"])}% / {fmt(o["blade"]["median_reduction_pct"])}%; {o["a"]}/{o["b"]} |')
 lines += ['','| 路径 | 组 | 新 1 s 割线中位/最大 °/s | 新 >0.31 次数/12 | r2 1 s 割线中位/最大 °/s；超限/12 | 新转子超速相对12.1 rpm 中位/最大 % | r2 中位/最大 % |','|---|---|---:|---:|---:|---:|---:|']
 for case in CASES:
  n=out['cases'][case]
  for g in GROUPS:
   v=n[g];o=n['r2_8deg_s'][g]
   lines.append(f'| {case} | {g} | {v["rate_median_deg_s"]:.5f}/{v["rate_max_deg_s"]:.5f} | {v["rate_exceed_count"]} | {o["rate_median_deg_s"]:.5f}/{o["rate_max_deg_s"]:.5f}; {o["rate_exceed_count"]} | {v["overspeed_median_pct"]:.2f}/{v["overspeed_max_pct"]:.2f} | {o["overspeed_median_pct"]:.2f}/{o["overspeed_max_pct"]:.2f} |')
 lines += ['',f'近中心塔底前后负峰恶化相对 r2 改善 {improvement:+.2f} 个百分点；“明显改善”={out["obvious_improvement"]}（≥5 个百分点）。',f'“消除”={out["elimination"]}（近中心及两偏心路径 (a)(b) 成立且本批速率均达标）。(c) 未重算，沿用 r2；不称分段 D 通过闸门。',f'G2L 新增转子超速比例 >10 个百分点的路径：{out["overspeed_g2l_increment_gt10pp"] or "无"}。','',f'脚本 SHA256（自身）：{hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}。数字由 metrics_A170_3_step1.json 自动生成。']
 (P/'RESULTS_A170_3_step1.md').write_text('\n'.join(lines)+'\n')
 print('REPORT',json.dumps({'elimination':out['elimination'],'obvious_improvement':out['obvious_improvement'],'rate_evaluable':out['strict_evaluable']},ensure_ascii=False))
if __name__=='__main__':main()
