#!/usr/bin/env python3
"""M1 first-source timing forecast; unmeasured branches explicitly assumptions."""
import json, pathlib
p=pathlib.Path(__file__).parent
first=json.loads((p/'first_source_v1/GRAP_v100_IFS_ledger_v1.json').read_text())
assert first['ok']==first['expected_objects']==360
sec=first['wall_seconds']/first['ok']
# M2 AI archives are 730 cycles/source; HRES Open Data starts 2023-01-18, 696 cycles.
nai=2*(360+730); nh22=360; nh23=696
rate=2.0 # CU per CPU allocation hour: conservative planning allowance, not session bill
h22sec=5.6 # four WB2 chunk reads per cycle, one chunk measured at ~1.40 s; not complete-item measurement
h23sec=10.0 # assumption, Open Data not accessed under M1 prohibition
setup_cu=2.0 # explicit setup/verification/stopping allowance
projection={'first_source':{'name':first['source'],'objects':first['ok'],'wall_seconds':first['wall_seconds'],'seconds_per_object_measured':sec,'task_CU_actually_metered':None},'assumptions':{'cpu_CU_per_hour_planning':rate,'HRES_2022_seconds_per_cycle_provisional':h22sec,'HRES_2023_seconds_per_cycle_provisional':h23sec,'setup_verification_stop_allowance_CU':setup_cu,'HRES_2023_not_opened':True},'full_matrix':{'AI_two_sources_2022_and_2023_objects':nai,'HRES_2022_cycles':nh22,'HRES_2023_cycles':nh23},'estimated_total_CU_not_metered':rate*(nai*sec+nh22*h22sec+nh23*h23sec)/3600+setup_cu,'cap_CU':16,'cap_breached_under_assumptions':False,'caveat':'Other account assignments overlap; usage balance is not own-session meter. HRES 2023 cycle time is unmeasured; reforecast after 2022 HRES pilot before M2.'}
out=p/'cu_reestimate_v1.json'
with out.open('x') as f:json.dump(projection,f,ensure_ascii=False,indent=2)
print(json.dumps(projection,ensure_ascii=False,indent=2))
