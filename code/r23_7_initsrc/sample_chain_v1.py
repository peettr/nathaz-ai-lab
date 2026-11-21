#!/usr/bin/env python3
"""Independent key-level audit of frozen R23.7 inputs; never rewrite archived scores."""
import json
from pathlib import Path
import pandas as pd
import score_v1 as s
R=Path(__file__).resolve().parent
O=Path('./22_Lab/06_Logs/a1_lowalt_wind/asos_2022train_2023test_20261014/data_v2')
A=R/'m2_2023_v1'; D=A/'assembled_v1'
TR=[R/'first_source_v1/GRAP_v100_IFS_station_v1.csv.gz',R/'second_source_v1/PANG_v100_IFS_station_v1.csv.gz',R/'hres_2022_v1/HRES_2022_station_v1.csv.gz']
TE=[A/'final_ai_v1/GRAP_v100_IFS_station_v1.csv.gz',A/'final_ai_v1/PANG_v100_IFS_station_v1.csv.gz',D/'HRES_2023_station_assembled_v1.csv.gz']
def keyset(a):return set(map(tuple,a[s.KEY].itertuples(index=False,name=None)))
def count(a):return {str(h):len(keyset(a[a.lead_h.eq(h)])) for h in (24,48)}
def stage(name,a,stages):
    k=keyset(a); prior=stages[-1].pop('_keys') if stages else None
    if prior is not None:stages[-1]['removed_to_next']=len(prior-k)
    stages.append({'stage':name,'unique_station_init_lead_keys':len(k),'by_lead':count(a),'_keys':k})
def audit(old,paths,year,train=False):
    base=s.read(O/old); base=base[base.source.eq('GFS')]
    stages=[]
    stage('old_GFS_rows_before_frozen_eligibility',base,stages)
    a=base[base.valid_utc.dt.year.eq(year)&base.lead_h.isin([24,48])].copy()
    stage('valid_year_and_24_48_leads',a,stages)
    a=a[a.metar_speed.notna()].copy();stage('paired_nonmissing_METAR',a,stages)
    if not train:
        a=a[~(a.station.eq('SRE')&a.valid_utc.between('2023-06-01','2023-09-30 23:59:59.999999'))].copy()
        stage('R23_2a_SRE_summer_removed',a,stages)
        full_keys=keyset(a)
        a=a[a.init_utc.ge(pd.Timestamp('2023-01-18',tz='UTC'))].copy()
        stage('primary_init_at_or_after_2023_01_18',a,stages)
    before=keyset(a)
    inputs={p.name+'@'+str(p.parent.relative_to(R)):s.read(p) for p in paths}
    source_keys={q.source.iloc[0]:keyset(q) for q in inputs.values()}
    for src in (s.SOURCES[0],s.SOURCES[2],s.SOURCES[4]):
        source_keys[src]=keyset(s.read(O/old).query('source==@src'))
    if not train:
        five=set.intersection(full_keys,*(source_keys[x] for x in s.FIVE))
        stages.append({'stage':'five_arm_full_year_after_SRE_and_METAR','unique_station_init_lead_keys':len(five),'by_lead':{str(h):sum(k[2]==h for k in five) for h in (24,48)}})
    for src in s.SOURCES:
        lost=before-source_keys[src]
        stages.append({'stage':'source_missing_from_preintersection','source':src,'missing_keys':len(lost),'by_lead':{str(h):sum(k[2]==h for k in lost) for h in (24,48)}})
    common=set.intersection(before,*(source_keys[x] for x in s.SOURCES))
    if not train: assert all(k[1]>=pd.Timestamp('2023-01-18',tz='UTC') for k in common)
    stages.append({'stage':'six_arm_common','unique_station_init_lead_keys':len(common),'by_lead':{str(h):sum(k[2]==h for k in common) for h in (24,48)},'removed_from_previous_eligible':len(before-common)})
    if train:
        drop={k for k in before if k[1]==pd.Timestamp('2022-12-01',tz='UTC')}
        stages.append({'stage':'PG_IFS_missing_init_2022_12_01_00_on_all_arms','eligible_before':len(drop),'already_absent_from_common':len(drop-common)})
    for r in stages:r.pop('_keys',None)
    return stages
if __name__=='__main__':
    output={'training':audit('paired_station_train.csv.gz',TR,2022,True),'test':audit('paired_station_test.csv.gz',TE,2023)}
    metrics=json.loads((D/'metrics_v1.json').read_text())
    tr=output['training'][-2];te=output['test'][-1]
    assert tr['unique_station_init_lead_keys']==metrics['counts']['train_common_keys'],(tr,metrics['counts'])
    assert te['by_lead']['24']==metrics['main']['paired_keys'],(te,metrics['main']['paired_keys'])
    five=next(r for r in output['test'] if r['stage']=='five_arm_full_year_after_SRE_and_METAR')
    assert five['by_lead']['24']==metrics['counts']['test_five_observed_keys']
    p=D/'sample_chain_v1.json'; assert not p.exists();p.write_text(json.dumps(output,ensure_ascii=False,indent=2,default=str)+'\n')
    print(json.dumps({'path':str(p),'train_common':tr['by_lead'],'test_six':te['by_lead'],'test_five':five['by_lead']},ensure_ascii=False))
