#!/usr/bin/env python3
"""Supplement: reproduce R23.2a's 2022-fitted climatology-logit BSS denominator."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit
import score_v1 as s
R=Path(__file__).resolve().parent; D=R/'m2_2023_v1/assembled_v1'
O=Path('./22_Lab/06_Logs/a1_lowalt_wind/asos_2022train_2023test_20261014/data_v2')
TR=[R/'first_source_v1/GRAP_v100_IFS_station_v1.csv.gz',R/'second_source_v1/PANG_v100_IFS_station_v1.csv.gz',R/'hres_2022_v1/HRES_2022_station_v1.csv.gz']
TE=[R/'m2_2023_v1/final_ai_v1/GRAP_v100_IFS_station_v1.csv.gz',R/'m2_2023_v1/final_ai_v1/PANG_v100_IFS_station_v1.csv.gz',D/'HRES_2023_station_assembled_v1.csv.gz']
if __name__=='__main__':
    oldtr=s.read(O/'paired_station_train.csv.gz');oldte=s.read(O/'paired_station_test.csv.gz')
    orig=oldtr[oldtr.source.eq('GRAP_v100_GFS')]
    slope,intercept=s.logistic(orig.climatology.to_numpy(),(orig.metar_speed.to_numpy()>=8).astype(float))
    assert np.isfinite([slope,intercept]).all()
    train,test,_,_=s.prepare(O/'paired_station_train.csv.gz',O/'paired_station_test.csv.gz',TR,TE)
    reference=oldte[oldte.source.eq('GFS')][s.KEY+['climatology']].drop_duplicates(s.KEY)
    out={'method':'R23.2a run_verify_v2.py lines 190-194: one logistic fit on 2022 GRAP_v100_GFS climatology, all archived training leads; 2023 climatology feature from archived R23.2a table','training_rows':len(orig),'logit_slope':slope,'logit_intercept':intercept,'cohorts':{}}
    for label,frame,sources in [('primary_six_2023_01_18',test[test.init_utc.ge(pd.Timestamp('2023-01-18',tz='UTC'))],s.SOURCES),('full_year_five',test,s.FIVE)]:
        out['cohorts'][label]={}
        for lead in (24,48):
            a=s.intersect(frame[frame.lead_h.eq(lead)],sources)
            obs=a[a.source.eq(sources[0])][s.KEY+['metar_speed']].merge(reference,on=s.KEY,validate='one_to_one')
            assert obs.climatology.notna().all()
            y=(obs.metar_speed.to_numpy()>=8).astype(float)
            pbase=expit(intercept+slope*obs.climatology.to_numpy());base=float(np.mean((pbase-y)**2))
            results={}
            for source in sources:
                g=a[a.source.eq(source)][s.KEY+['prob8']].merge(obs[s.KEY],on=s.KEY,validate='one_to_one')
                g=g.sort_values(s.KEY);truth=obs.sort_values(s.KEY)
                assert np.array_equal(g[s.KEY].to_numpy(),truth[s.KEY].to_numpy())
                yy=(truth.metar_speed.to_numpy()>=8).astype(float)
                bs=float(np.mean((g.prob8.to_numpy()-yy)**2));results[source]={'brier':bs,'BSS_vs_R23_2a_2022_fitted_climatology':1-bs/base}
            out['cohorts'][label][str(lead)]={'n':len(obs),'reference_brier':base,'arms':results}
    path=D/'descriptive_r232a_v1.json';assert not path.exists();path.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'path':str(path),'training_rows':len(orig),'main_BSS':{k:round(v['BSS_vs_R23_2a_2022_fitted_climatology'],6) for k,v in out['cohorts']['primary_six_2023_01_18']['24']['arms'].items()}},ensure_ascii=False))
