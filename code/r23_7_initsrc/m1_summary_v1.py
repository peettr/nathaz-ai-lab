#!/usr/bin/env python3
"""Assemble immutable M1 handoff from read-back ledgers and frozen gate outputs."""
import json,hashlib,pathlib,datetime
p=pathlib.Path(__file__).parent
read=lambda f:json.loads((p/f).read_text())
repro=read('reproduction_v1.json');power=read('power_gate_v1.json');budget=read('cu_reestimate_v1.json')
gc=read('first_source_v1/GRAP_v100_IFS_ledger_v1.json')
pg=read('second_source_v1/PANG_v100_IFS_ledger_v2.json')
hres=read('hres_2022_v1/HRES_2022_ledger_v1.json')
assert repro['pass'] and power['pass']
for d in (gc,pg,hres):
    assert len(d['ledger'])==d['expected_objects']==360
    assert d['ok']+d['missing']+d['error']==360
    assert d['rows']==24*d['ok']
assert (gc['ok'],pg['ok'],hres['ok'])==(360,359,360)
assert power['rows_per_source']==4016 and power['N22_verification_days']==180
assert all(repro[s]['n']==7917 for s in ('GRAP_v100_GFS','PANG_v100_GFS','GFS'))
assert set((p/'hres_2022_v1').glob('HRES_2022*'))
ledger_names={'GC·IFS':'first_source_v1/GRAP_v100_IFS_ledger_v1.json','PG·IFS':'second_source_v1/PANG_v100_IFS_ledger_v2.json','HRES':'hres_2022_v1/HRES_2022_ledger_v1.json'}
missing={s:[{'init_utc':r['init_utc'],'url':r['url'],'error':r.get('error')} for r in d['ledger'] if r['status']!='ok'] for s,d in zip(ledger_names,(gc,pg,hres))}
files=('m1_worker_v2.py','m1_launcher_v1.py','cu_reestimate_v1.py','hres_2022_v1.py','hres_launcher_v1.py','power_gate_v1.py','ledger_amend_v1.py','m1_summary_v1.py')
sha={x:hashlib.sha256((p/x).read_bytes()).hexdigest() for x in files}
start=datetime.datetime.fromisoformat('2026-11-08T12:51:33-05:00')
stop=datetime.datetime.fromisoformat('2026-11-08T13:39:20-05:00')
seconds=(stop-start).total_seconds()
first_unit_s=gc['wall_seconds']/gc['ok']
rate=budget['assumptions']['cpu_CU_per_hour_planning']
result={'session':{'name':'r237-m1-cpu-v1','hardware':'Colab CPU Standard','started':'11-08 12:51:33 EST','stopped':'11-08 13:39:20 EST','elapsed_allocation_seconds':seconds,'stopped_confirmed_by_sessions_absence':True},'sources_2022':{s:{'expected':360,'retrieved':d['ok'],'missing':d['missing'],'error':d['error'],'rows':d['rows'],'ledger':str(p/ledger_names[s]),'station_csv_gz':str(p/f) } for (s,d,f) in [('GC·IFS',gc,'first_source_v1/GRAP_v100_IFS_station_v1.csv.gz'),('PG·IFS',pg,'second_source_v1/PANG_v100_IFS_station_v1.csv.gz'),('HRES',hres,'hres_2022_v1/HRES_2022_station_v1.csv.gz')]},'missing_objects':missing,'budget':{'measured_first_source_wall_seconds':gc['wall_seconds'],'measured_first_source_seconds_per_object':first_unit_s,'planning_rate_CU_per_hour_not_metered':rate,'first_source_CU_per_object_at_planning_rate':first_unit_s*rate/3600,'first_source_CU_at_planning_rate':gc['wall_seconds']*rate/3600,'full_campaign_forecast_CU_with_M2':budget['estimated_total_CU_not_metered'],'cap_CU':16,'forecast_under_cap_under_explicit_assumptions':not budget['cap_breached_under_assumptions'],'actual_task_CU_unavailable_due_to_concurrent_allocations':True,'account_shared_balance_start':1410.28,'account_shared_balance_end':1392.27,'own_allocation_duration_CU_at_planning_rate':seconds*rate/3600,'forecast_file':str(p/'cu_reestimate_v1.json')},'reproduction':{s:{'MAE_m_s':repro[s]['refit_mae'],'paired_count':repro[s]['n'],'difference_from_archive_m_s':repro[s]['difference']} for s in ('GRAP_v100_GFS','PANG_v100_GFS','GFS')},'reproduction_pass':repro['pass'],'power':{k:power[k] for k in ('paired_station_keys','N22_verification_days','N23_calendar_days_2023_01_18_to_12_31','h22','h23','C22_point','C22_bootstrap_ci95','pass')},'power_file':str(p/'power_gate_v1.json'),'script_sha256':sha,'no_2023_IFS_or_HRES_opened':True,'result':'M1 gates pass; M2 not run under this delegation'}
out=p/'m1_summary_v1.json'
with out.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps(result,ensure_ascii=False,indent=2))
