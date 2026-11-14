"""Synthetic 200-unit branch coverage; no frozen cohort records are read."""
import csv, json, pathlib, subprocess, sys
root=pathlib.Path(__file__).parent
src=root/'synthetic_selftest_1108d'
base=[json.loads(line) for line in (src/'rows.jsonl').read_text().splitlines()]
outdir=root/'synthetic_selftest_v3_full_1108';outdir.mkdir(exist_ok=True)
assert len(base)==2200
# AI false alarms / hit / peak are manipulated independently. Each synthetic case
# always contains the complete 100+100 cohorts and all ten members per unit.
scenarios={
 'pass': {'event_ai':28,'event_h':27,'control_ai':19,'control_h':20},
 'fail_hit': {'event_ai':20,'event_h':27,'control_ai':19,'control_h':20},
 'fail_false': {'event_ai':28,'event_h':27,'control_ai':27,'control_h':20},
 'fail_peak': {'event_ai':25,'event_h':30,'control_ai':19,'control_h':20},
 'undecided': {'event_ai':28,'event_h':27,'control_ai':19,'control_h':20,'control_h_zero':True},
 'exploratory': {'event_ai':28,'event_h':27,'control_ai':19,'control_h':20,'flag':'--s0-gate'},
}
# Pass vs undecided: pass has HRRR alarms in 20 control days, AI zero;
# undecided has neither arm alarm. Ensure every day's cluster includes both arms.
results={}
for name,cfg in scenarios.items():
 rows=json.loads(json.dumps(base));sub=outdir/name;sub.mkdir(exist_ok=True)
 if (sub/'score.json').exists():
  result=json.loads((sub/'score.json').read_text());gate=result['gates'];results[name]={'verdict':gate['verdict'],'gates':gate,'draws':result['main']['valid_draws'],'event':result['cohort']['event'],'control':result['cohort']['control']};print(name,gate['verdict'],'(preserved)',flush=True);continue
 for row in rows:
  event=row['unit_index']%2==0; order=row['unit_index']//2
  if row['kind']=='baseline':
   h=cfg['event_h'] if event else (27 if name=='pass' and order<20 else cfg['control_h'])
   for k in ('fg_wide','fg_narrow','hrrr_formula_wide'):row[k]['ms']=h
  else:
   v=cfg['event_ai'] if event else cfg['control_ai']
   for method in row['methods'].values():
    for window in method.values():window['ms']=v
 if (sub/'rows.jsonl').exists():
  saved=[json.loads(line) for line in (sub/'rows.jsonl').read_text().splitlines()]
  assert saved==rows,(name,'existing synthetic matrix differs')
 else:
  with (sub/'rows.jsonl').open('x') as f:
   for row in rows:f.write(json.dumps(row)+'\n')
 cmd=[sys.executable,str(root/'r4_score_v3.py'),'--events',str(src/'events.csv'),'--controls',str(src/'controls.csv'),'--input',str(sub/'rows.jsonl'),'--output',str(sub/'score.json')]
 if cfg.get('flag'):cmd.append(cfg['flag'])
 p=subprocess.run(cmd,capture_output=True,text=True)
 assert p.returncode==0,(name,p.stderr)
 result=json.loads((sub/'score.json').read_text());gate=result['gates'];results[name]={'verdict':gate['verdict'],'gates':gate,'draws':result['main']['valid_draws'],'event':result['cohort']['event'],'control':result['cohort']['control']}
 assert result['cohort']['event']==result['cohort']['control']==100
 assert result['main']['valid_draws']==5000
 assert all(x['valid_draws']==5000 for x in result['report_only'].values())
 assert result['coverage_thunderstorm']['event']['n']==100 and result['coverage_thunderstorm']['control']['n']==100
 assert set(result['topk']['ai'])=={'10','25','50','100'}
 print(name,gate['verdict'],flush=True)
assert {k:v['verdict'] for k,v in results.items()}=={'pass':'通过','fail_hit':'不通过','fail_false':'不通过','fail_peak':'不通过','undecided':'不判','exploratory':'探索性'}
(outdir/'assertions.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
print('ALL_BRANCH_ASSERTIONS_PASSED',outdir/'assertions.json',flush=True)
