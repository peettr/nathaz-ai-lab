#!/usr/bin/env python3
"""Post-review descriptive diagnostics only; frozen score_v1 remains authoritative."""
import json, math
from pathlib import Path
import numpy as np
import pandas as pd
import score_v1 as s
R=Path(__file__).resolve().parent
O=Path('./22_Lab/06_Logs/a1_lowalt_wind/asos_2022train_2023test_20261014/data_v2')
A=R/'m2_2023_v1'; D=A/'assembled_v1'
TR=[R/'first_source_v1/GRAP_v100_IFS_station_v1.csv.gz',R/'second_source_v1/PANG_v100_IFS_station_v1.csv.gz',R/'hres_2022_v1/HRES_2022_station_v1.csv.gz']
TE=[A/'final_ai_v1/GRAP_v100_IFS_station_v1.csv.gz',A/'final_ai_v1/PANG_v100_IFS_station_v1.csv.gz',D/'HRES_2023_station_assembled_v1.csv.gz']
def threshold_scores(g,t):
    x=g.corrected.to_numpy(dtype=float);y=g.metar_speed.to_numpy(dtype=float)
    assert np.isfinite(x).all() and np.isfinite(y).all()
    xe=np.maximum(x-t,0);ye=np.maximum(y-t,0)
    term=ye**2-xe**2-2*(y-x)*xe
    ob=y>=t;fc=x>=t
    H=int((ob&fc).sum());M=int((ob&~fc).sum());F=int((~ob&fc).sum());TN=int((~ob&~fc).sum());n=len(y)
    sums={'hit':float(term[ob&fc].sum()),'miss':float(term[ob&~fc].sum()),'false_alarm':float(term[~ob&fc].sum()),'correct_negative':float(term[~ob&~fc].sum())}
    total=float(term.sum());assert abs(total-sum(sums.values()))<1e-8
    return {'n':n,'threshold_mps':t,'threshold_rule':'forecast and observation >= threshold','twMSE':float(term.mean()),'unconditional_MSE':float(np.mean((x-y)**2)),'H':H,'M':M,'F':F,'correct_negative':TN,'MR':M/(H+M) if H+M else None,'FAR':F/(H+F) if H+F else None,'FB':(H+F)/(H+M) if H+M else None,'score_sum_by_category':sums,'twMSE_share_by_category':{k:v/total if total else None for k,v in sums.items()},'conditional_owMSE':float(np.mean((x[ob]-y[ob])**2)) if ob.any() else None,'conditional_denominator':H+M,'forecast_event_denominator':H+F}
def topk(g,archived):
    g=g.sort_values(['prob8','station','init_utc'],ascending=[False,True,True],kind='stable').reset_index(drop=True)
    p=g.prob8.to_numpy();event=(g.metar_speed.to_numpy()>=8);total=int(event.sum());out={}
    for k in (.01,.05,.10):
        n=max(1,math.ceil(len(g)*k));prior=archived[str(k)]
        assert prior['selected']==n
        cut=p[n-1];higher=int((p>cut).sum());ties=int((p==cut).sum());chosen=n-higher
        hits=int(event[:n].sum())
        tieevents=int(event[higher:higher+ties].sum())
        lowest=int(event[:higher].sum()+max(0,chosen-(ties-tieevents)))
        highest=int(event[:higher].sum()+min(chosen,tieevents))
        out[str(k)]={'selected':n,'boundary_probability':float(cut),'boundary_tied_rows':ties,'boundary_selected_rows':chosen,'boundary_tied_events':tieevents,'R23_2a_station_then_init_hits':hits,'R23_2a_capture':hits/total if total else None,'score_v1_hits':prior['captured_events'],'score_v1_capture':prior['capture_rate'],'difference_hits':hits-prior['captured_events'],'possible_hits_at_boundary_min':lowest,'possible_hits_at_boundary_max':highest,'random_expected':n/len(g)}
    return out
if __name__=='__main__':
    train,test,_,_=s.prepare(O/'paired_station_train.csv.gz',O/'paired_station_test.csv.gz',TR,TE)
    archive=json.loads((D/'metrics_v1.json').read_text())
    out={'status':'post_review_descriptive_only_not_for_verdict','input_frozen_score':'score_v1.py','thresholds_mps':[8,10],'thresholds_origin':'R23.2a run_verify_v2.py lines 240-258; post-review reporting choices, not preregistered R23.7 gates','BSS_reference':'pooled observed 2022 six-arm training event frequency for corresponding lead versus 2023 evaluation cohort event frequency','cohorts':{}}
    for label,frame,sources in [('primary_six_2023_01_18',test[test.init_utc.ge(pd.Timestamp('2023-01-18',tz='UTC'))],s.SOURCES),('full_year_five',test,s.FIVE)]:
        out['cohorts'][label]={}
        for lead in (24,48):
            a=s.intersect(frame[frame.lead_h.eq(lead)],sources)
            tr=s.intersect(train[train.lead_h.eq(lead)],sources)
            traintruth=tr[tr.source.eq(sources[0])];testtruth=a[a.source.eq(sources[0])]
            rate22=float((traintruth.metar_speed>=8).mean());rate23=float((testtruth.metar_speed>=8).mean());events=int((testtruth.metar_speed>=8).sum())
            assert 0<rate22<1 and 0<rate23<1
            cell={'n':len(testtruth),'events_8mps':events,'climatology_2022':{'n':len(traintruth),'events':int((traintruth.metar_speed>=8).sum()),'event_rate':rate22},'sample_2023':{'n':len(testtruth),'events':events,'event_rate':rate23},'arms':{}}
            for source in sources:
                g=a[a.source.eq(source)].copy();assert len(g)==len(testtruth)
                y=(g.metar_speed.to_numpy()>=8).astype(float);p=g.prob8.to_numpy();bs=float(np.mean((p-y)**2))
                arm={'brier':bs,'BSS_vs_2022_climatology':1-bs/float(np.mean((rate22-y)**2)),'BSS_vs_2023_sample_rate':1-bs/(rate23*(1-rate23)),'thresholds':{str(t):threshold_scores(g,t) for t in (8,10)}}
                if label=='primary_six_2023_01_18' and lead==24:
                    prev=archive['descriptive_8mps']['arms'][source]
                    assert abs(arm['BSS_vs_2023_sample_rate']-prev['bss_vs_event_climatology'])<1e-7,(source,arm['BSS_vs_2023_sample_rate'],prev['bss_vs_event_climatology'],bs,rate23)
                    arm['top_k']=topk(g,prev['top_k'])
                cell['arms'][source]=arm
            out['cohorts'][label][str(lead)]=cell
    path=D/'descriptive_v2.json';assert not path.exists();path.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'path':str(path),'cohorts':{k:{h:{'n':v['n'],'events':v['events_8mps']} for h,v in d.items()} for k,d in out['cohorts'].items()},'topk_differences':{k:{p:v['difference_hits'] for p,v in d['top_k'].items()} for k,d in out['cohorts']['primary_six_2023_01_18']['24']['arms'].items()}},ensure_ascii=False))
