"""Synthetic-only end-to-end scorer test, not part of R4 blind sample."""
import csv,json,pathlib,subprocess,sys
R=pathlib.Path(__file__).parent/'synthetic_selftest_1108d';R.mkdir(exist_ok=False)
events,controls,rows=[],[],[]
for i in range(100):
    eid=str(i); day=f'2024-07-{i%20+1:02d}'
    e=dict(order=i,id=eid,station='TEST',utc=day+'T12:00:00',obs_kt=50,year=2024)
    c=dict(order=i,event_id=eid,station='TEST',utc=day+'T13:00:00',max_kt=40,year=2024,phase='near')
    events.append(e);controls.append(c)
    for kind,idx in [('event',2*i),('control',2*i+1)]:
        def peak(v):return dict(ms=v)
        rows.append(dict(unit_index=idx,kind='baseline',seed=None,status='ok',event_id=eid,fg_wide=peak(27 if kind=='event' else 20),fg_narrow=peak(27 if kind=='event' else 20),hrrr_formula_wide=peak(27 if kind=='event' else 20)))
        for seed in range(101,111):
            v=28 if kind=='event' else 19
            methods={name:dict(wide=peak(v),narrow=peak(v)) for name in ('diagnostic','factor16777','hrrrcast_without_vvel')}
            rows.append(dict(unit_index=idx,kind='member',seed=seed,status='ok',event_id=eid,methods=methods))
for name,records in [('events.csv',events),('controls.csv',controls)]:
    with (R/name).open('x',newline='') as f:
        w=csv.DictWriter(f,records[0].keys());w.writeheader();w.writerows(records)
with (R/'rows.jsonl').open('x') as f:
    for row in rows:f.write(json.dumps(row)+'\n')
cmd=[sys.executable,str(pathlib.Path(__file__).parent/'r4_score.py'),'--events',str(R/'events.csv'),'--controls',str(R/'controls.csv'),'--input',str(R/'rows.jsonl'),'--output',str(R/'score.json')]
proc=subprocess.run(cmd,capture_output=True,text=True,check=True)
result=json.loads((R/'score.json').read_text())
assert result['cohort']['event']==100 and result['cohort']['control']==100
assert result['gates']['verdict']=='不判' and result['gates']['false_uninformative']
assert result['topk']['ai']['10']['event_count']==10
assert result['coverage_thunderstorm']['event']['n']==100
assert all(v['valid_draws']==5000 for v in result['report_only'].values())
(R/'test_output.txt').write_text(proc.stdout+'assertions=passed\n')
print((R/'test_output.txt').read_text())
