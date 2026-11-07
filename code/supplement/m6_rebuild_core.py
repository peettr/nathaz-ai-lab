#!/usr/bin/env python3
"""Rebuild frozen core pairing/forecast/aggregate without recomputing archived secondary."""
import json,hashlib
from pathlib import Path
import pandas as pd
import m6_score as s
p=Path('/content/m6');out=p/'rebuild_core';out.mkdir(exist_ok=True)
assert hashlib.sha256((p/'m6_score.py').read_bytes()).hexdigest()=='11c7f845a502406d7232c67c2308fdca51d199d55d5d71c52f95448ce66ea39c'
models=json.loads((p/'models.json').read_text());obs=s.observations(s.BOUND,pd.Timestamp(s.CFG['test_end']));fc=s.forecast('test')
rows=[]
for delay in s.CFG['delays_h']:
    train=pd.read_parquet(p/f'train_pairs_delay{delay}.parquet')
    train.issue_utc=pd.to_datetime(train.issue_utc,utc=True);train.valid_end_utc=pd.to_datetime(train.valid_end_utc,utc=True)
    if delay==4:
        d=pd.read_parquet(p/'test_predictions_delay4.parquet');assert len(d)==235041
    else:
        d=s.construct(obs,fc,'test',delay)
        assert train.valid_end_utc.max()<d.issue_utc.min()
        d=s.attach(d,models[str(delay)]);d=s.add_events(d,obs,models[str(delay)]['threshold'])
        d.to_parquet(p/f'test_predictions_delay{delay}.parquet',index=False)
    for lead in s.LEADS:rows+=s.aggregate(d,lead,delay)
    print('CORE_DELAY',delay,len(d),flush=True)
result=pd.DataFrame(rows);result.to_csv(out/'rebuilt_main.csv',index=False)
frozen=pd.read_csv(p/'frozen_main.csv').sort_values(['delay_h','lead_min','metric']).reset_index(drop=True)
rebuilt=result.sort_values(['delay_h','lead_min','metric']).reset_index(drop=True)
assert frozen.shape==rebuilt.shape and frozen[['delay_h','lead_min','metric','n','days']].equals(rebuilt[['delay_h','lead_min','metric','n','days']])
cols=['point','lo','hi'];delta=(frozen[cols]-rebuilt[cols]).abs().to_numpy().max()
assert delta<=1e-12,('MAIN_MISMATCH',delta)
(out/'parity.json').write_text(json.dumps({'rows':len(frozen),'max_abs_difference':float(delta),'tolerance':1e-12,'passed':True},indent=2))
print('PARITY_OK',len(frozen),delta,flush=True)
