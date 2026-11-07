#!/usr/bin/env python3
"""H2f: Francine land-only LOO; rescore old H2d peaks read-only."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import ast,json,math
from pathlib import Path
import numpy as np,pandas as pd
from scipy.linalg import solve
from scipy.optimize import minimize_scalar
R=Path(__file__).resolve().parent
METHODS=['idw','ok75','okfit','era','era_resok75','era_resokfit','holland','holland_resok75','holland_resokfit']
BASE=['idw','ok75','okfit']
FUSE=['era_resok75','era_resokfit','holland_resok75','holland_resokfit']
REG=['DELTA','ZETA','IDA','NICHOLAS','IAN','NICOLE','IDALIA','DEBBY','HELENE','MILTON']
INDEPENDENT=[e for e in REG if e!='NICHOLAS']+['FRANCINE']
# Reuse H2d evaluation functions without executing its top-level write or changing settings.
src=ast.parse((R/'evaluate_clean_h2d.py').read_text())
wanted={'score','distmat','fit_range','okw','predict','coverage','peaks_for','summary'}
functions=[node for node in src.body if isinstance(node,ast.FunctionDef) and node.name in wanted]
assert {n.name for n in functions}==wanted
exec(compile(ast.Module(body=functions,type_ignores=[]),str(R/'evaluate_clean_h2d.py'),'exec'))
AUDIT=pd.read_csv(R/'station_clean_h2f.csv').set_index('station')
status=AUDIT.status.to_dict()
def norm(s):return s if ':' in s else 'TX:'+s

def verdict(gain,wins,n,strong=False):
    if gain is None or n<8:return '不可评'
    if gain>=.2 and wins/n>=2/3:return '强风站值得融合' if strong else '值得'
    if gain>=.1 or wins/n>=2/3:return '有条件'
    return '插值够用'
def compare(q,strong=False):
    n=len(q);scores={}
    for method in BASE+FUSE:
        v=score(q[method],q.obs)
        scores[method]=v
    base=min(BASE,key=lambda m:scores[m]['rmse'] if scores[m]['rmse'] is not None else math.inf)
    fusion=min(FUSE,key=lambda m:scores[m]['rmse'] if scores[m]['rmse'] is not None else math.inf)
    a=scores[base]['rmse'];b=scores[fusion]['rmse']
    gain=1-b/a if n>=8 and a else None
    wins=int(((q[fusion]-q.obs).abs()<(q[base]-q.obs).abs()).sum()) if n>=8 else None
    return dict(stations=n,baseline=base,best_fusion=fusion,baseline_metrics=scores[base],fusion_metrics=scores[fusion],gain=gain,station_wins=wins,verdict=verdict(gain,wins,n,strong),all_methods=scores)
if __name__=='__main__':
    assert not (R/'metrics_h2f.json').exists()
    g=pd.read_csv(R/'grid_francine_h2f.csv.gz',parse_dates=['hour'])
    assert set(g.station).issubset(status)
    x=g[g.station.map(status)=='land'].copy()
    sea=g[g.station.map(status)=='platform'].copy()
    unknown=g[g.station.map(status)=='unknown_cover'].copy()
    cover,missing=coverage(x)
    p,fits=predict(x)
    p['eligible']=p.station.map(cover);p['pool']='land'
    pk=peaks_for(p);pk['pool']='land'
    p.to_csv(R/'predictions_francine_h2f.csv.gz',index=False,compression='gzip')
    pk.to_csv(R/'peaks_francine_h2f.csv',index=False)
    pd.DataFrame(missing).to_csv(R/'missing_francine_h2f.csv',index=False)
    prior=pd.read_csv(R/'peaks_clean_h2d.csv')
    prior=prior[prior.pool=='land']
    q=pd.concat([prior,pk],ignore_index=True)
    # Previous aggregate must be independently reproduced before extension.
    old=json.loads((R/'metrics_clean_h2d.json').read_text())['land_metrics']['COMBINED']
    ten=compare(q[q.event.isin(REG)])
    assert ten['stations']==old['stations'] and ten['baseline']==old['baseline'] and ten['best_fusion']==old['best_fusion']
    assert abs(ten['gain']-old['gain'])<1e-10 and ten['station_wins']==old['station_wins']
    independent_old=json.loads((R/'metrics_h2b.json').read_text())['strong']['INDEPENDENT_EVALUABLE']
    nine=compare(q[(q.event.isin(INDEPENDENT[:-1])) & (q.obs>=12)],True)
    assert nine['stations']==independent_old['stations'] and abs(nine['gain']-independent_old['gain'])<1e-9 and nine['station_wins']==independent_old['wins']
    main={e:compare(q[q.event==e]) for e in REG+['FRANCINE','BERYL']}
    main['TEN']=ten;main['TEN_PLUS_FRANCINE']=compare(q[q.event.isin(REG+['FRANCINE'])])
    strong={e:compare(q[(q.event==e)&(q.obs>=12)],True) for e in INDEPENDENT+['NICHOLAS','BERYL']}
    strong['NINE_INDEPENDENT']=nine
    strong['TEN_INDEPENDENT_PLUS_FRANCINE']=compare(q[(q.event.isin(INDEPENDENT))&(q.obs>=12)],True)
    # The old ten-event and nine-independent results are exact anchors.
    old_main=old
    payload={'metadata':{'source_grids':'grid_francine_h2f.csv.gz; H2d prior peaks read-only','source_audit':'station_clean_h2f.csv: H2d audit + 6 Francine-only sites','pool':'land-only; platform separated, unknown excluded','times':'UTC','wind':'hourly METAR sustained; gust separately','francine_window':'landfall +/-12h','coverage':'valid hours >=75% plus report within +/-2h of H08 model peak','main_events':REG+['FRANCINE'],'independent_strong_events':INDEPENDENT,'already_seen':['BERYL','NICHOLAS'],'method_selection':'within subset minimum test RMSE, optimistic','fit_counts_francine':fits,'francine_land_sites':int(x.station.nunique()),'francine_platform_sites':int(sea.station.nunique()),'francine_unknown_cover_sites':int(unknown.station.nunique()),'francine_excluded_sites':g.loc[~g.station.isin(x.station)&~g.station.isin(sea.station)&~g.station.isin(unknown.station),'station'].nunique(),'francine_coverage_missing':missing,'b_v1_assumptions':'2-min/5-s conversion and 500m neutral constant-flux reference height are pre-run assumptions (v1/PREREG_v1.md); not literature measured values','b_v1_root_results_used':False},'main':main,'strong':strong,'francine_hourly':{method:score(p.loc[p.eligible,method],p.loc[p.eligible,'obs']) for method in METHODS},'francine_distance_groups':summary(p,pk,missing,['FRANCINE'])['distance_groups'],'francine_water_platform':{'candidate_sites':int(sea.station.nunique()),'qualified_by_coverage':int(sum(coverage(sea)[0].values())) if len(sea) else 0,'not_pooled_with_land':True},'comparison_anchors':{'old_ten_stations':old_main['stations'],'old_ten_gain':old_main['gain'],'old_nine_independent_strong_stations':independent_old['stations'],'old_nine_independent_strong_gain':independent_old['gain']}}
    (R/'metrics_h2f.json').open('x').write(json.dumps(payload,indent=2,ensure_ascii=False)+'\n')
    for key,val in [('francine',main['FRANCINE']),('eleven',main['TEN_PLUS_FRANCINE']),('francine_strong',strong['FRANCINE']),('independent_ten_strong',strong['TEN_INDEPENDENT_PLUS_FRANCINE'])]:
        print(key,val['stations'],val['baseline'],val['best_fusion'],val['baseline_metrics']['rmse'],val['fusion_metrics']['rmse'],val['gain'],val['station_wins'],val['verdict'],flush=True)
    print('site pools',x.station.nunique(),sea.station.nunique(),unknown.station.nunique(),'missing',len(missing),flush=True)
