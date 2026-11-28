"""Two-stage blending-height correction; reuse v2 paired forecasts, no fitting on test winds.
Run: ../paris_morph_v2/.venv/bin/python run_morph_v3.py
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

R=Path(__file__).resolve().parent
V2=R.parent/'paris_morph_v2'

def score(g,col):
    o=g.wind.to_numpy(); p=g[col].to_numpy(); y=o>=8; f=p>=8
    h=int(np.sum(y&f)); m=int(np.sum(y&~f)); a=int(np.sum(~y&f))
    return dict(n=len(g),mae=float(np.abs(p-o).mean()),bias=float((p-o).mean()),
                auc8=float(roc_auc_score(y,p)) if np.unique(y).size==2 else None,
                csi8=h/(h+m+a) if h+m+a else None,hits=h,misses=m,false_alarms=a)

def paired_ci(g,col,seed):
    z=g.copy();z['day']=z.valid_utc.dt.floor('D')
    b=z.groupby('day').apply(lambda q: pd.Series({'m':np.abs(q[col]-q.wind).sum(),
                                                   's0':np.abs(q.S0-q.wind).sum()}),include_groups=False)
    rng=np.random.default_rng(seed)
    ix=rng.integers(0,len(b),size=(5000,len(b)))
    draws=b.to_numpy()[ix].sum(axis=1)
    return dict(relative_pct=float(100*(b.m.sum()/b.s0.sum()-1)),
                ci95_pct=(100*np.quantile(draws[:,0]/draws[:,1]-1,[.025,.975])).tolist(),days=len(b))

def main():
    d=pd.read_csv(V2/'paired_morph.csv.gz',parse_dates=['init_utc','valid_utc'])
    assert len(d)==1268 and all(len(g)==317 for _,g in d.groupby(['source','lead_h']))
    assert np.allclose(d.ground_mos*d.morph_factor,d.M,atol=1e-10)
    methods={'S0':None,'v2_single_stage':None,'assumed_0p03':None,'assumed_0p3':None}
    d['v2_single_stage']=d.M;d['assumed_0p03']=d.M_ref_z0_0p03;d['assumed_0p3']=d.M_ref_z0_0p3
    for zb in (60,100,200):
        clearance=zb-d.d_m-2*d.z0_m
        col=f'M_zb{zb}_ref0p03'
        d[col]=np.where(clearance>0,
             d.ground_mos*(np.log(zb/.03)/np.log(10/.03)) *
             (np.log((111-d.d_m)/d.z0_m)/np.log((zb-d.d_m)/d.z0_m)),np.nan)
        methods[col]=dict(zb_m=zb,z0_ref_m=.03)
    for ref in (.01,.1):
        key='0p01' if ref==.01 else '0p1';col=f'M_zb60_ref{key}'
        d[col]=d.ground_mos*(np.log(60/ref)/np.log(10/ref))*\
               (np.log((111-d.d_m)/d.z0_m)/np.log((60-d.d_m)/d.z0_m))
        methods[col]=dict(zb_m=60,z0_ref_m=ref)
    # guard all sectors, not only sampled sectors, and all scored rows
    sectors=pd.read_csv(V2/'sectors.csv')
    excluded={str(zb):sectors.loc[zb-sectors.d_m<=2*sectors.z0_m,'sector_from_deg'].astype(int).tolist() for zb in (60,100,200)}
    for zb in (60,100,200):
        col=f'M_zb{zb}_ref0p03'
        assert d[col].notna().all() or excluded[str(zb)]
    d.to_csv(R/'paired_morph_v3.csv.gz',index=False,compression='gzip')
    records=[];by_sector=[]
    for (src,lead),g in d.groupby(['source','lead_h']):
        for j,col in enumerate(methods):
            q=g.dropna(subset=[col]);rec=dict(source=src,lead_h=int(lead),method=col,**score(q,col),excluded_n=len(g)-len(q))
            if col!='S0':rec['vs_S0']=paired_ci(q,col,20261014+int(lead)+j*103+(1 if src=='GFS' else 2))
            records.append(rec)
        for sec,sub in g.groupby('sector_from_deg'):
            by_sector.append(dict(source=src,lead_h=int(lead),sector_from_deg=int(sec),n=len(sub),
                    mae_zb60=float(np.abs(sub.M_zb60_ref0p03-sub.wind).mean()),
                    bias_zb60=float((sub.M_zb60_ref0p03-sub.wind).mean()),
                    mae_S0=float(np.abs(sub.S0-sub.wind).mean())))
    payload=dict(records=records,sector_scores=by_sector,excluded_sector_centers_deg=excluded,
            definitions=dict(main='U_LFPO10 * ln(zb/z0ref)/ln(10/z0ref) * ln((111-d)/z0)/ln((zb-d)/z0)',
             airport='z0ref=.03 m assumed; sensitivities .01/.1 m; d_ref=0; sensor 10 m assumed',
             fold='exactly v2 S0 and LFPO ground MOS, validation winds used only for scoring',
             bootstrap='5000 paired validation-day resamples; fixed RNG seed per source/lead/method',
             exclusion='skip sector if zb-d<=2z0; do not fill missing predictions'),
            methods=methods,inputs=[str(V2/'paired_morph.csv.gz'),str(V2/'sectors.csv')])
    (R/'metrics.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    fig,ax=plt.subplots(figsize=(9,4.5))
    for src,marker in [('GFS','o'),('GRAP_v100_GFS','s')]:
        for lead,ls in [(24,'-'),(48,'--')]:
            q=[next(x for x in records if x['source']==src and x['lead_h']==lead and x['method']==k)['mae']
               for k in ['S0','v2_single_stage','M_zb60_ref0p03','M_zb100_ref0p03','M_zb200_ref0p03','assumed_0p03','assumed_0p3']]
            ax.plot(range(len(q)),q,marker=marker,linestyle=ls,label=f'{src} {lead}h')
    ax.set_xticks(range(7),['S0','old single','zb60','zb100','zb200','z0=.03','z0=.3'],rotation=20)
    ax.set_ylabel('PALUPD 111m MAE (m/s)');ax.grid(alpha=.25);ax.legend(ncol=2,fontsize=8)
    fig.text(.01,.005,'Data: IGN BD TOPO V3 morphology; Morrison et al. 2025 / Zenodo 17710093; NOAA GFS / CIRA AIWP; IEM LFPO METAR. Two-stage: Blocken 2018 (Verkaik 2006).',fontsize=6.8)
    fig.tight_layout(rect=(0,.04,1,1));fig.savefig(R/'morph_v3_mae.png',dpi=160);plt.close(fig)
    print(json.dumps({'records':len(records),'excluded':excluded,'gfs24':[(r['method'],round(r['mae'],4),round(r.get('vs_S0',{}).get('relative_pct',0),2)) for r in records if r['source']=='GFS' and r['lead_h']==24]}))
if __name__=='__main__':main()
