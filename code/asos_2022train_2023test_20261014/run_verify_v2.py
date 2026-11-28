#!/usr/bin/env python3
"""A330: analyze archived re-paired ASOS rows under preregistration + addendum 1.
Execute on Colab CPU; outputs are generated entirely from paired train/test rows.
"""
import argparse, concurrent.futures, hashlib, json, os, subprocess, sys, time, traceback
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit
from scipy.stats import rankdata
from run_verify_revised import logistic

SOURCES=['FOUR_v200_GFS','PANG_v100_GFS','GRAP_v100_GFS','GFS']
AI='GRAP_v100_GFS'
SEED=20261029
REPS=1000
ROOT=Path('/content/asos_a330')
ORIG=Path('/content/asos_a330/original')
OUT=Path(os.environ.get('A330_OUTPUT','/content/asos_a330/output'))
PREREG_SHA='1cab3d68129211c0fcc7cf24744aadcdc3eeda20a6bcf6ed2b6ba28829775818'
ADDENDUM_SHA='fc8cfbc746da9aa7a023b6337ad8452c6b62a7463bbb9f87fcacc300f7e61372'

def ensure_new(path):
    if path.exists(): raise FileExistsError(f'refuse overwrite: {path}')
    path.parent.mkdir(parents=True,exist_ok=True)

def collect_2023(stations,workers=12):
    import run_forecasts as rf
    rf.LEADS=(6,12,24,36,48,72)
    pairs=[(s,d) for d in pd.date_range('2023-01-01','2024-01-01',freq='12h',inclusive='left',tz='UTC') for s in SOURCES]
    # The archived first run has precisely two missing AIWP objects; keep its common-pair cohort.
    missing={('FOUR_v200_GFS','2023101812'),('PANG_v100_GFS','2023101812')}
    def task(pair):
        s,d=pair; stamp=d.strftime('%Y%m%d%H'); folder=ROOT/'parts/2023'/s
        folder.mkdir(parents=True,exist_ok=True);path=folder/f'{s}_{stamp}.csv'; meta=folder/f'{s}_{stamp}.json'
        if (s,stamp) in missing: return 'HISTORIC_MISSING',s,stamp
        if path.exists() and meta.exists():return 'SKIP',s,stamp
        if path.exists() or meta.exists():raise ValueError(f'partial object {path}')
        t=time.monotonic()
        try:
            rows,url,nbytes=rf.gfs(d,stations) if s=='GFS' else rf.ai(d,s,stations)
            assert len(rows)==len(stations)*len(rf.LEADS)
            data=pd.DataFrame(rows,columns=['station','init_utc','lead_h','source','fc_u','fc_v','fc_u100','fc_v100'])
            tmp=path.with_suffix('.part');data.to_csv(tmp,index=False);os.replace(tmp,path)
            tmp=meta.with_suffix('.part');tmp.write_text(json.dumps({'source':s,'init':d.isoformat(),'url':url,'bytes_or_object_size':nbytes,'seconds':time.monotonic()-t}));os.replace(tmp,meta)
            return 'OK',s,stamp
        except Exception as e:
            # Source outages are not permission to infer a result. Keep the error and fail the reproduction gate later.
            (folder/f'{s}_{stamp}.error').write_text(traceback.format_exc())
            return 'ERROR',s,stamp
    counts={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures={pool.submit(task,p):p for p in pairs}
        for i,f in enumerate(concurrent.futures.as_completed(futures),1):
            status,s,stamp=f.result();counts[status]=counts.get(status,0)+1
            if i%20==0 or status=='ERROR':print('FC2023',i,len(pairs),counts,s,stamp,flush=True)
    print('FC2023_DONE',counts,flush=True)
    if counts.get('ERROR',0):raise RuntimeError(f'2023 source errors: {counts}')

def stage():
    ROOT.mkdir(parents=True,exist_ok=True);stations=pd.read_csv('/content/stations.csv')
    scripts=[
      [sys.executable,'/content/run_metar_history.py','--stations','/content/stations.csv','--out',str(ROOT/'metar')],
      [sys.executable,'/content/run_observations.py','--stations','/content/stations.csv','--year','2022','--out',str(ROOT/'observations_2022_climatology.csv')],
      [sys.executable,'/content/run_observations.py','--stations','/content/stations.csv','--year','2023','--out',str(ROOT/'observations_2023_hourly.csv')],
      [sys.executable,'/content/run_collect_bounded.py','--stations','/content/stations.csv','--out',str(ROOT/'parts'),'--workers','16','--days','15']]
    for cmd in scripts:
        print('STAGE_START',cmd[1],time.time(),flush=True)
        subprocess.run(cmd,check=True,cwd='/content');print('STAGE_DONE',cmd[1],time.time(),flush=True)
    collect_2023(stations)
    OUT.mkdir(exist_ok=True)
    cmd=[sys.executable,'/content/run_verify_revised.py','--stations','/content/stations.csv','--sources',*SOURCES,'--parts',str(ROOT/'parts'),'--metar',str(ROOT/'metar'),'--minute-mix-template',str(ROOT/'observations_{year}_hourly.csv'),'--old-2023','/content/nonexistent.csv','--out',str(ORIG)]
    # 2022 and 2023 original minute products used different basenames. A copy of a newly
    # generated VM-only input allows the unchanged original verifier to use a single template.
    source=ROOT/'observations_2022_climatology.csv';dest=ROOT/'observations_2022_hourly.csv'
    if not dest.exists():dest.write_bytes(source.read_bytes())
    print('ORIGINAL_START',time.time(),flush=True)
    subprocess.run(cmd,check=True,cwd='/content');print('ORIGINAL_DONE',time.time(),flush=True)
    analyze()

def classify(ci,margin):
    if ci[0]>-margin:return '非劣'
    if ci[1]<-margin:return '劣'
    return '分不出'

def sig(ci):
    return '显著优' if ci[0]>0 else '显著差' if ci[1]<0 else '不显著'

def metric(y,x,p,threshold,mode,clim=None):
    event=y>=threshold
    if mode=='csi':
        pred=x>=threshold;den=np.sum(event|pred)
        return np.sum(event&pred)/den if den else np.nan
    if mode=='auc':
        n1=event.sum();n0=len(event)-n1
        return (rankdata(p,method='average')[event].sum()-n1*(n1+1)/2)/(n1*n0) if n1 and n0 else np.nan
    if mode=='bss':
        bs=np.mean((p-event)**2);base=np.mean((clim-event)**2)
        return 1-bs/base if base>0 else np.nan
    if mode=='mae':return np.mean(np.abs(x-y))
    raise ValueError(mode)

def analyze():
    OUT.mkdir(parents=True,exist_ok=True)
    original=json.loads((ORIG/'metrics.json' if (ORIG/'metrics.json').exists() else ROOT/'original_metrics.json').read_text())
    input_root=Path(os.environ.get('A330_INPUT',str(ORIG if (ORIG/'paired_station_train.csv.gz').exists() else ROOT)))
    tr=pd.read_csv(input_root/'paired_station_train.csv.gz',parse_dates=['init_utc','valid_utc'])
    te=pd.read_csv(input_root/'paired_station_test.csv.gz',parse_dates=['init_utc','valid_utc'])
    for frame in (tr,te):frame['valid_utc']=pd.to_datetime(frame.valid_utc,utc=True)
    assert original['primary_selected_on_2022_24h_mae']==AI
    full_te=te.copy()
    sre=(te.station=='SRE')&te.valid_utc.between(pd.Timestamp('2023-06-01',tz='UTC'),pd.Timestamp('2023-09-30 23:59:59.999999',tz='UTC'))
    removed=te[sre]
    te=te[~sre].copy()
    original_lead_n={6:7948,12:7930,24:7917,36:7882,48:7867,72:7834}
    lead_counts=[]
    for lead,target in original_lead_n.items():
        d={s:int(((te.source==s)&(te.lead_h==lead)).sum()) for s in SOURCES}
        f={s:int(((full_te.source==s)&(full_te.lead_h==lead)).sum()) for s in SOURCES}
        e={s:int(((removed.source==s)&(removed.lead_h==lead)).sum()) for s in SOURCES}
        lead_counts.append({'lead_h':lead,'original_n_per_source':target,'primary_by_source':d,'full_by_source':f,'excluded_sre_by_source':e,'all_match_original':all(v==target for v in d.values())})
    a=te[(te.source==AI)&(te.lead_h==24)].sort_values(['station','init_utc']).reset_index(drop=True)
    b=te[(te.source=='GFS')&(te.lead_h==24)].sort_values(['station','init_utc']).reset_index(drop=True)
    assert a[['station','init_utc','lead_h']].equals(b[['station','init_utc','lead_h']])
    n=len(a); y=a.metar_speed.to_numpy();xa=a.corrected.to_numpy();xb=b.corrected.to_numpy()
    ma=np.mean(abs(xa-y));mb=np.mean(abs(xb-y))
    ca=metric(y,xa,None,8,'csi');cb=metric(y,xb,None,8,'csi')
    check={'paired_cases':n,'mae_ai':ma,'mae_gfs':mb,'csi_ai':ca,'csi_gfs':cb,'delta_csi':ca-cb}
    expected={'paired_cases':7917,'mae_ai':1.287,'mae_gfs':1.286,'csi_ai':.334,'csi_gfs':.342,'delta_csi':-.008}
    numeric_pass=all(abs(check[k]-expected[k])<=.002 for k in expected if k!='paired_cases')
    original_pass=n==7917 and numeric_pass
    passed=original_pass and all(v['all_match_original'] for v in lead_counts)
    print('REPRO_GATE',check,'PRIMARY_PASS',passed,'LEADS',lead_counts,flush=True)
    if not passed:
        fail={'status':'原预注册复现闸或逐时效配对数未过；B档不计算','reproduction':check,'expected':expected,'lead_counts':lead_counts,'prereg_sha256':PREREG_SHA,'addendum_sha256':ADDENDUM_SHA}
        (OUT/'metrics_v2.json').write_text(json.dumps(fail,ensure_ascii=False,indent=2))
        (OUT/'results_v2_B.md').write_text('# B 档停止：复现闸未过\n\n'+json.dumps(fail,ensure_ascii=False,indent=2)+'\n')
        return
    # Each bootstrap draw resamples whole UTC verifying days, holding the paired methods together.
    rng=np.random.default_rng(SEED);records=[];top=[];thresholds=[]
    key=['station','init_utc']
    lead_keys=[]
    for lead in (24,48):
        by_source=[set(map(tuple,te[(te.source==s)&(te.lead_h==lead)][key].itertuples(index=False,name=None))) for s in SOURCES]
        lead_keys.append(set.intersection(*by_source))
    intersection=lead_keys[0]&lead_keys[1]
    intersection_n=len(intersection)
    use_intersection=False
    print('INTERSECTION_PRIMARY',intersection_n,flush=True)
    def paired(lead,minute=False):
        cols=['station','init_utc','lead_h','valid_utc','metar_speed','minute_speed','minute_count','persistence','corrected','climatology','prob_wind_8','prob_wind_10']
        left=te[(te.source==AI)&(te.lead_h==lead)][cols].rename(columns={'corrected':'ai','prob_wind_8':'p_ai_8','prob_wind_10':'p_ai_10'})
        right=te[(te.source=='GFS')&(te.lead_h==lead)][['station','init_utc','lead_h','corrected','prob_wind_8','prob_wind_10']].rename(columns={'corrected':'gfs','prob_wind_8':'p_gfs_8','prob_wind_10':'p_gfs_10'})
        g=left.merge(right,on=['station','init_utc','lead_h'],validate='one_to_one').dropna(subset=['ai','gfs','metar_speed','p_ai_8','p_gfs_8'])
        if minute:g=g[g.station.isin(['GOK','OKC','PWA'])]
        return g.reset_index(drop=True)
    def evaluate(g,ycol,kind,threshold,margin,xai='ai',xgfs='gfs',pai=None,pgfs=None,pclim=None):
        # NaNs in minute speed and probability are jointly excluded, not treated as non-events.
        required=[ycol,xai,xgfs]+([pai,pgfs] if pai else [])+([pclim] if pclim else [])
        g=g.dropna(subset=required).reset_index(drop=True)
        yy=g[ycol].to_numpy();aa=g[xai].to_numpy();bb=g[xgfs].to_numpy()
        pa=g[pai].to_numpy() if pai else None;pb=g[pgfs].to_numpy() if pgfs else None
        pc=g[pclim].to_numpy() if pclim else None
        def calc(ix):
            if kind=='mae':
                va=metric(yy[ix],aa[ix],None,threshold,kind);vb=metric(yy[ix],bb[ix],None,threshold,kind)
                return 1-va/vb
            return metric(yy[ix],aa[ix],pa[ix] if pa is not None else None,threshold,kind,pc[ix] if pc is not None else None)-metric(yy[ix],bb[ix],pb[ix] if pb is not None else None,threshold,kind,pc[ix] if pc is not None else None)
        days=g.valid_utc.dt.floor('D').to_numpy();unique,inv=np.unique(days,return_inverse=True)
        groups=[np.flatnonzero(inv==i) for i in range(len(unique))]
        point=calc(np.arange(len(g)));samples=[]
        for _ in range(REPS):
            draw=rng.integers(0,len(unique),len(unique));ix=np.concatenate([groups[i] for i in draw]);samples.append(calc(ix))
        samples=np.array(samples);samples=samples[np.isfinite(samples)]
        if len(samples)<.9*REPS:raise RuntimeError(f'bootstrap undefined {kind} {threshold} {len(samples)}')
        ci=np.quantile(samples,[.025,.975]).tolist()
        out={'n':len(g),'verifying_days':len(unique),'point':float(point),'ci95':ci,'margin':margin,'verdict':classify(ci,margin),'description':sig(ci),'ai':float(metric(yy,aa,pa,threshold,kind,pc)),'gfs':float(metric(yy,bb,pb,threshold,kind,pc))}
        if kind=='mae':out['mae_ratio_ai_over_gfs']=out['ai']/out['gfs']
        records.append({'criterion':kind,'lead_h':int(g.lead_h.iloc[0]),'threshold':threshold,'target':ycol,'ai_column':xai,'gfs_column':xgfs,'formula':'Δ=1−MAE_AI/MAE_GFS' if kind=='mae' else f'Δ={kind.upper()}_AI−{kind.upper()}_GFS',**out})
        return records[-1]
    secondary_intersection=[];original_gates=[]
    for lead in [24,48]:
        full=paired(lead)
        g=full.copy()
        for baseline,margin in [('gfs',.05),('persistence',-.15),('climatology',-.15)]:
            rr=evaluate(g,'metar_speed','mae',0,margin,xgfs=baseline)
            rr['criterion']='original_gate_'+baseline
            rr['formula']=f'Δ=1−MAE_AI/MAE_{baseline}'
            original_gates.append(rr)
        for t in [8,10]:
            # Refit frozen-original climatology logistic on 2022 train, source[0] only.
            train=tr[tr.source==SOURCES[0]]
            coef,nt=logistic(train.climatology.to_numpy(),(train.metar_speed.to_numpy()>=t).astype(float))
            g[f'p_clim_{t}']=expit(coef[1]+coef[0]*g.climatology.to_numpy())
            for kind,margin in [('csi',.05),('bss',.05),('auc',.02)]:
                if kind=='csi' and t==10:continue
                evaluate(g,'metar_speed',kind,t,margin,pai=f'p_ai_{t}' if kind!='csi' else None,pgfs=f'p_gfs_{t}' if kind!='csi' else None,pclim=f'p_clim_{t}' if kind=='bss' else None)
            if t==8 and lead==24:
                # Evaluate sensitivity cohorts independently; never mutate a main record.
                for label,frame in [('full_8144',full_te),('four_source_intersection',full_te)]:
                    la=frame[(frame.source==AI)&(frame.lead_h==lead)][['station','init_utc','lead_h','valid_utc','metar_speed','corrected','climatology','prob_wind_8']].rename(columns={'corrected':'ai','prob_wind_8':'p_ai_8'})
                    rb=frame[(frame.source=='GFS')&(frame.lead_h==lead)][['station','init_utc','lead_h','corrected','prob_wind_8']].rename(columns={'corrected':'gfs','prob_wind_8':'p_gfs_8'})
                    gi=la.merge(rb,on=['station','init_utc','lead_h'],validate='one_to_one').dropna().reset_index(drop=True)
                    if label=='four_source_intersection':
                        keys_by=[set(map(tuple,full_te[(full_te.source==ss)&(full_te.lead_h==ll)][key].itertuples(index=False,name=None))) for ss in SOURCES for ll in (24,48)]
                        allkeys=set.intersection(*keys_by)
                        gi=gi[gi[key].apply(tuple,axis=1).isin(allkeys)].reset_index(drop=True)
                    gi['p_clim_8']=expit(coef[1]+coef[0]*gi.climatology.to_numpy())
                    for kind,margin in [('csi',.05),('bss',.05),('auc',.02)]:
                        rr=evaluate(gi,'metar_speed',kind,8,margin,pai='p_ai_8' if kind!='csi' else None,pgfs='p_gfs_8' if kind!='csi' else None,pclim='p_clim_8' if kind=='bss' else None)
                        rr['criterion']=kind+'_'+label+'_sensitivity';secondary_intersection.append(rr)
        if lead==24:
            k=int((g.metar_speed>=8).sum());assert k>0
            for s in SOURCES:
                if s==AI: gs=g;pcol='p_ai_8'
                elif s=='GFS':gs=g;pcol='p_gfs_8'
                else:
                    extra=te[(te.source==s)&(te.lead_h==lead)][['station','init_utc','lead_h','prob_wind_8']]
                    gs=g.merge(extra,on=['station','init_utc','lead_h'],validate='one_to_one');pcol='prob_wind_8'
                    assert len(gs)==len(g) and gs[pcol].notna().all()
                    assert gs[key].reset_index(drop=True).equals(g[key].reset_index(drop=True))
                    assert gs.metar_speed.reset_index(drop=True).equals(g.metar_speed.reset_index(drop=True))
                ordered=gs.sort_values([pcol,'station','init_utc'],ascending=[False,True,True],kind='stable')
                hits=int((ordered.head(k).metar_speed>=8).sum())
                days=gs.valid_utc.dt.floor('D').to_numpy();unique,inv=np.unique(days,return_inverse=True)
                groups=[np.flatnonzero(inv==i) for i in range(len(unique))]
                events=(gs.metar_speed.to_numpy()>=8)
                captures=[]
                for _ in range(REPS):
                    ix=np.concatenate([groups[i] for i in rng.integers(0,len(unique),len(unique))]);kk=int(events[ix].sum())
                    if kk:
                        # stable tie-break by station then initialization; repeated day draws remain separate rows
                        sub=gs.iloc[ix].sort_values([pcol,'station','init_utc'],ascending=[False,True,True],kind='stable')
                        captures.append(float((sub.head(kk).metar_speed>=8).sum()/kk))
                top.append({'source':s,'k':k,'hits':hits,'capture_rate':hits/k,'ci95':np.quantile(captures,[.025,.975]).tolist(),'tie_break':'prob descending; station/init ascending'})
                for pct in (.01,.05,.10):
                    kk=max(1,int(np.ceil(len(gs)*pct)))
                    hh=int((ordered.head(kk).metar_speed>=8).sum())
                    top.append({'source':s,'fraction':pct,'k':kk,'hits':hh,'event_count':k,'capture_rate':hh/k,'random_expected':kk/len(gs),'tie_break':'prob descending; station/init ascending'})
        for t in [8,10]:
            for s in SOURCES:
                train=tr[(tr.source==s)&(tr.lead_h==lead)].dropna(subset=['corrected','metar_speed'])
                vals=np.sort(train.corrected.unique());target=int((train.metar_speed>=t).sum())
                # Include threshold above max for zero forecasts; first sorted candidate wins ties.
                choices=np.r_[vals,np.nextafter(vals[-1],np.inf)]
                sorted_train=np.sort(train.corrected.to_numpy())
                pred_n=len(sorted_train)-np.searchsorted(sorted_train,choices,side='left')
                ix=int(np.argmin(abs(pred_n-target)));tau=float(choices[ix])
                if s==AI:test_pred=g.ai
                elif s=='GFS':test_pred=g.gfs
                else:
                    extra=te[(te.source==s)&(te.lead_h==lead)][['station','init_utc','lead_h','corrected']]
                    joined=g[['station','init_utc','lead_h']].merge(extra,on=['station','init_utc','lead_h'],validate='one_to_one')
                    assert len(joined)==len(g) and joined.corrected.notna().all()
                    test_pred=joined.corrected
                g[f'tau_{s}_{t}']=tau
                actual=int((test_pred>=tau).sum());events=int((g.metar_speed>=t).sum())
                thresholds.append({'lead_h':lead,'threshold':t,'source':s,'train_tau':tau,'train_pred_n':int(pred_n[ix]),'train_event_n':target,'test_pred_n':actual,'test_event_n':events,'test_frequency_bias':actual/events if events else None})

            # B3 uses each source's fixed train-year tau, not a shared 8 m/s cutoff.
            ga=g.copy();ga['ai_tau_flag']=np.where(ga.ai>=ga[f'tau_{AI}_{t}'],float(t),0.)
            ga['gfs_tau_flag']=np.where(ga.gfs>=ga[f'tau_GFS_{t}'],float(t),0.)
            r=evaluate(ga,'metar_speed','csi',t,.05,xai='ai_tau_flag',xgfs='gfs_tau_flag');r['criterion']='csi_tau_train_frequency_bias_1'
        gm=g[g.station.isin(['GOK','OKC','PWA'])].copy()
        excluded=int((gm.minute_count<45).sum())+int(gm.minute_count.isna().sum())
        eligible=gm[gm.minute_count>=45].copy();r=evaluate(eligible,'minute_speed','mae',8,.05);r['criterion']='minute_mae';r['excluded_minute_count_lt45_or_missing']=excluded
        if lead==24:
            r=evaluate(eligible,'minute_speed','csi',8,.05);r['criterion']='minute_csi'
    primary=[r for r in records if r['lead_h']==24 and r['target']=='metar_speed' and r['threshold']==8 and r['criterion'] in ('csi','bss','auc') and r['ai_column']=='ai']
    assert len(primary)==3,primary
    assert len(original_gates)==6
    first_second=all(x['verdict']=='非劣' for x in original_gates)
    verdict='不可替代（本配置）' if any(x['verdict']=='劣' for x in primary+original_gates) else '可替代（本配置）' if first_second and all(x['verdict']=='非劣' for x in primary) else '分不出'
    station_24=te[(te.source==AI)&(te.lead_h==24)].groupby('station').size().to_dict()
    ledger_path=ROOT/'station_year_ledger_final.json';ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else []
    station_comparison=[{'station':s,'new_24h_pairs':int(count),'original_2023_observation_hours_not_pair_count':next((v['observation_hours'] for v in ledger if v['year']==2023 and v['station']==s),None)} for s,count in sorted(station_24.items())]
    original_text=(ROOT/'results.md').read_text() if (ROOT/'results.md').exists() else ''
    import re
    old_minute=re.findall(r'^\|GFS\|24\|corrected\|(\d+)\|',original_text,re.M)
    ledger_reuse=[{'station':v['station'],'year':v['year'],'reused_preliminary_station_rows':v.get('reused_preliminary_station_rows')} for v in ledger if 'reused_preliminary_station_rows' in v]
    payload={'status':'completed','prereg_sha256':PREREG_SHA,'addendum_sha256':ADDENDUM_SHA,'post_hoc':True,'seed':SEED,'bootstrap_reps':REPS,'bootstrap_unit':'UTC verifying day','reproduction':check,'expected':expected,'reproduction_passed_addendum':passed,'reproduction_passed_original':original_pass,'lead_counts':lead_counts,'intersection_24_48_all_four_n':intersection_n,'intersection_as_primary':False,'primary_cohort_n':next(r['n'] for r in primary),'sensitivity_24h_8mps':secondary_intersection,'station_24h_diagnostic':station_comparison,'ledger_reuse':ledger_reuse,'original_minute_table_24h_n':int(old_minute[-1]) if len(old_minute)>=2 else None,'original_criteria_1_2':original_gates,'original_criteria_1_2_all_supported':first_second,'records':records,'thresholds':thresholds,'top_k':top,'primary_24h_8mps':primary,'overall':verdict,'train_rows_per_source':len(tr)//len(SOURCES),'test_rows_per_source':len(te)//len(SOURCES)}
    (OUT/'metrics_v2.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False))
    fmt=lambda x:f'{x:.4f}'
    lines=['# R23.2a ASOS B 档补判（六审裁决）','','看过 2023 初版结果（10-14）后、B 档开算前（10-29 12:33）写定的事后规则；不能称盲法检验。名义 10 m，实际测高未逐站核实。预注册 SHA-256：'+PREREG_SHA+'；补定 1 SHA-256：'+ADDENDUM_SHA+'。','## 原预注册复现闸','|量|原目标|还原主样本实测|绝对偏差|','|---|---:|---:|---:|']
    for k,v in expected.items():lines.append(f'|{k}|{v}|{check[k]:.6f}|{abs(check[k]-v):.6f}|')
    lines += [f'原读法：配对数 {n}=7917 且五项数值偏差均≤0.002，通过；补定 1 宽松读法也通过，但本次主判采用原读法。','|时效 h|原 n/源|全样本 n/源|SRE 2023-06~09 剔除 n/源|还原 n/源|相等|','|---:|---:|---:|---:|---:|---|']
    for v in lead_counts:
        s=AI;lines.append(f"|{v['lead_h']}|{v['original_n_per_source']}|{v['full_by_source'][s]}|{v['excluded_sre_by_source'][s]}|{v['primary_by_source'][s]}|{v['all_match_original']}|")
    lines += [f'四源×24/48 h 主样本交集 n={intersection_n}；敏感性另用未剔除全样本与其四源交集。',f'按 UTC 验证日整组自助法 {REPS} 次，种子 {SEED}，95% 百分位区间。','', '## 原①②：对 GFS 5% 非劣，且对持续性和十年气候值改善≥15%']
    for r in original_gates:lines.append(f"- {r['lead_h']} h {r['criterion']}：{r['formula']}={fmt(r['point'])}，95% CI [{fmt(r['ci95'][0])}, {fmt(r['ci95'][1])}]，门槛 {(-r['margin']):.2f}：{r['verdict']}。")
    lines+=['','## B1–B4']
    for r in records:
        if r['criterion'].startswith('original_gate_') or '_sensitivity' in r['criterion']:continue
        lines.append(f"- {r['criterion']} {r['lead_h']} h {r['target']}"+('（全样本）' if r['criterion']=='minute_mae' else f" ≥{r['threshold']} m/s")+f"，n={r['n']}：{r['formula']}={fmt(r['point'])}（AI={fmt(r['ai'])}，GFS={fmt(r['gfs'])}），95% CI [{fmt(r['ci95'][0])}, {fmt(r['ci95'][1])}]，非劣界 −{r['margin']}：{r['verdict']}；零差描述 {r['description']}。"+(f" MAE_AI/MAE_GFS={fmt(r['mae_ratio_ai_over_gfs'])}。" if r['criterion']=='minute_mae' else '')+(f" minute_count<45/缺失剔除 {r['excluded_minute_count_lt45_or_missing']}。" if r['criterion']=='minute_mae' else ''))
    lines+=['','B1 24 h CSI 对裕度 m=0.03/0.05/0.07 的敏感性（同一区间）：']
    b1=next(r for r in primary if r['criterion']=='csi')
    lines.append('；'.join(f"m={m:.2f}：{classify(b1['ci95'],m)}" for m in [.03,.05,.07])+'。')
    lines+=['','未剔除 8144 全样本与四源×24/48 h 交集 B1/B2（8 m/s，24 h）敏感性：']
    for r in secondary_intersection:lines.append(f"- {r['criterion']}，n={r['n']}：{r['formula']}={fmt(r['point'])}，95% CI [{fmt(r['ci95'][0])}, {fmt(r['ci95'][1])}]：{r['verdict']}。")

    lines+=['','B2 的 BSS=1−BS_source/BS_clim，BS_clim 为同一配对上 2022 拟合的 climatology_prob 的 Brier；AUC 按该源 2022 拟合的 prob_wind_t 排序。10 m/s 仅描述，48 h 次要。','', 'B3 2022 训练年频率偏差=1 的近似阈值（最小整数计数偏差；相同偏差取较小 τ），原样移用 2023：']
    for v in thresholds:lines.append(f"- {v['source']} {v['lead_h']} h ≥{v['threshold']}：τ={v['train_tau']:.6f} m/s；2022 预报/观测计数={v['train_pred_n']}/{v['train_event_n']}；2023 预报/观测计数={v['test_pred_n']}/{v['test_event_n']}，频率偏差={v['test_frequency_bias']:.4f}。")
    lines+=['','Top-k：k=2023 24 h 同一配对实际 ≥8 m/s 事件数，概率降序；并列按站名/起报时刻升序。']
    for v in top:
        if 'fraction' in v:lines.append(f"- {v['source']} 前 {v['fraction']:.0%}：k={v['k']}，命中={v['hits']}/{v['event_count']}，捕获率={v['capture_rate']:.4f}，随机期望={v['random_expected']:.4f}。")
        else:lines.append(f"- {v['source']}：k=事件数={v['k']}，命中={v['hits']}，捕获率={v['capture_rate']:.4f}，95% CI [{fmt(v['ci95'][0])}, {fmt(v['ci95'][1])}]，随机期望={v['k']/n:.4f}。")
    lines+=['','## 配对差异诊断','全样本相对旧主样本的逐时效增量与 SRE 2023-06~09 剔除数逐一相等，详见上表。24 h 增量事件 ≥8 m/s 数='+str(int(((removed.source==AI)&(removed.lead_h==24)&(removed.metar_speed>=8)).sum()))+'。','原 10-14 复用的 preliminary 序列按 2022 单年气候值非空过滤；SRE 2022 年 6–9 月缺测，其 2023 年 6–9 月被误删。重配对改用 2013–2022 气候值，恢复了这些行。ledger 的 reused_preliminary_station_rows 字段如下（仅非空项）：']
    for v in ledger_reuse:
        if v['reused_preliminary_station_rows']:lines.append(f"- {v['station']} {v['year']}：{v['reused_preliminary_station_rows']}")
    lines+=['','## 总判定',f'{verdict}。原①②统计支持：{first_second}；B1、B2 主判：'+ '；'.join(f"{v['criterion']}={v['verdict']}" for v in primary)+'。', '原判据③原读法“未通过”：点估计低于 0 且区间跨 0；A 档区间读法“分不出”。B 档事后补定不能倒称原判据通过。',f'裕度敏感性：B1 m=0.07 为{classify(b1["ci95"],.07)}；若三项均非劣且①②支持，总判为可替代。ΔAUC 的 −0.02 界无推导，界前已知点差约 −0.002；取 m=0.01 时为{classify(next(v for v in primary if v["criterion"]=="auc")["ci95"],.01)}。','', '## 评测规矩三条逐项确认','① 订正/逻辑回归/τ/选源只用 2022 且只用预报场；持续性基线取整点 ±30 min 最近 METAR，可能用到起报后至多 30 min 观测（只利于基线）；比较按相同起报时刻、未计发布延迟。','② Top-k 捕获率：部分适用；前 1%/5%/10% 和事件数 k 均已补报，仅描述、不进总判。','③ 覆盖率按灾种分开：不适用；不产出预报分位数区间、无灾种标注。','', '主口径仅 12 机场站名义 10 m METAR 2 min（实际测高未逐站核实）；B4 仅 GOK/OKC/PWA 的有效时刻中心 ±30 min 一分钟资料、minute_count≥45，属敏感性且不进总判。绝对作业达标、06/18 UTC 有效时刻（18 UTC 为当地午后）与城区高度均不据此推断。']
    (OUT/'results_v2_B.md').write_text('\n'.join(lines)+'\n')
    print('B_DONE',verdict,len(records),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['stage','analyze']);args=p.parse_args()
    if args.command=='stage':stage()
    else:analyze()
