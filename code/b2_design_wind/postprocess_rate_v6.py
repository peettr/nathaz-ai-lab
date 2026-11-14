#!/usr/bin/env python3
"""Rerank immutable B2 H08 peak batches at preregistered HURDAT2 rate."""
import csv, json, pathlib, math
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parent
OUT=ROOT/'products_rate_v6'; OUT.mkdir(exist_ok=False)
RATE=json.loads((ROOT/'hurdat_rate_summary.json').read_text())['rate_main_per_year']
RATE_NO_LIFE=json.loads((ROOT/'hurdat_rate_summary.json').read_text())['rate_no_life_filter_per_year']
SITES=list(csv.DictReader((ROOT/'sites.csv').open()))
OLD={r['site']:r for r in csv.DictReader((ROOT/'evidence_v3/products_v3/return_levels.csv').open())}
N=len(SITES);assert N==19

def load(name):
    files=sorted((ROOT/'evidence_v3/results_v3').glob(name+'_*.npz'))
    assert files
    batches=[np.load(p) for p in files]
    ids=np.concatenate([a['ids'] for a in batches]); peaks=np.concatenate([a['peaks'] for a in batches]); ratios=np.concatenate([a['ratios'] for a in batches])
    source_years=np.concatenate([a['years'] for a in batches])
    marker=json.loads((ROOT/'evidence_v3/results_v3'/f'{name}_complete.json').read_text())
    assert len(np.unique(ids))==len(ids)==marker['counts']['selected']
    assert marker['counts']['failed']==0 and peaks.shape==(len(ids),3,N)
    if name=='raft':
        assert marker['counts']['raw']==40000
        nyrs=40000/RATE
        # RAFT ids 0..39999: deterministic surrogate year blocks at the new rate.
        years=np.floor(ids/RATE).astype(int)
        assert ids.min()>=0 and ids.max()<40000 and years.max()<math.ceil(nyrs)
    else:
        nyrs=10000;years=source_years
        assert marker['counts']['raw']==107063 and years.min()>=0 and years.max()<10000
    return ids,years,peaks,ratios,nyrs,marker['counts']['raw']

def ret(v,T,nyrs,nall,weights=None):
    pos=np.where(v>0)[0];order=pos[np.argsort(v[pos])[::-1]]
    target=(nall+1)*nyrs/(T*nall)
    if weights is None:
        if len(order)<2 or target<1 or target>len(order):return None
        return float(np.interp(target,np.arange(1,len(order)+1),v[order]))
    ww=weights[order];good=ww>0;order=order[good];ww=ww[good]
    if len(order)<2:return None
    end=np.cumsum(ww).astype('float64');start=end-ww+1
    if target<1 or target>end[-1]:return None
    return float(np.interp(target,np.column_stack((start,end)).ravel(),np.repeat(v[order],2)))

def boot(v,years,nyrs,nall,T):
    rg=np.random.default_rng(20261014);ny=math.ceil(nyrs);ans=[]
    for _ in range(300):
        counts=np.bincount(rg.integers(0,ny,size=ny),minlength=ny)
        ans.append(ret(v,T,nyrs,nall,counts[years]))
    good=np.array([a for a in ans if a is not None])
    return [float(np.quantile(good,.05)),float(np.quantile(good,.95))] if len(good)>=270 else [None,None]

def contrib(v,r,threshold):
    if threshold is None:return None
    sel=np.where(v>=threshold)[0];rr=r[sel];rr=rr[np.isfinite(rr)]
    bins=[int(np.sum(rr<1)),int(np.sum((rr>=1)&(rr<=3))),int(np.sum(rr>3))]
    return {'n':len(sel),'valid_rmw':len(rr),'missing_rmw':len(sel)-len(rr),'bins':bins,'shares':[x/len(rr) if len(rr) else None for x in bins]}

def main():
    data={n:load(n) for n in ('raft','storm')};rows=[];details={};cb=[]
    for j,s in enumerate(SITES):
        site=s['site'];prior=OLD[site]
        row={'site':site,'lat':s['lat'],'lon':s['lon'],'state':s['state'],'coast_km':prior['coast_km'],
             'asce50_ms':prior['asce50_ms'],'asce700_ms':prior['asce700_ms']}
        details[site]={}
        for name,(ids,years,peaks,ratios,nyrs,nall) in data.items():
            v=peaks[:,0,j];r=ratios[:,0,j]
            details[site][name]={}
            for T in (50,700):
                x=ret(v,T,nyrs,nall); ci=boot(v,years,nyrs,nall,T)
                row[f'{name}{T}_ms']=x;row[f'{name}{T}_ci90_lo_ms']=ci[0];row[f'{name}{T}_ci90_hi_ms']=ci[1]
                if x is not None:
                    cb.append({'site':site,'catalog':name,'return_years':T,**contrib(v,r,x)})
            row[name+'700_bias_pct']=100*(row[f'{name}700_ms']/float(prior['asce700_ms'])-1)
            if name=='raft':
                for rate in (10,14.5,20,RATE_NO_LIFE):
                    for T in (50,700):
                        details[site][name][f'rate_{rate}_v{T}']=ret(v,T,40000/rate,nall)
            for k,poci in ((1,1005),(2,1015)):
                for T in (50,700):
                    details[site][name][f'poci_{poci}_v{T}']=ret(peaks[:,k,j],T,nyrs,nall)
        rows.append(row)
    with (OUT/'return_levels.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    with (OUT/'rmw_contribution.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cb[0].keys());w.writeheader();w.writerows(cb)
    (OUT/'details.json').write_text(json.dumps(details,indent=2))
    a=np.array([r['raft700_bias_pct']/100 for r in rows]);s=np.array([r['storm700_bias_pct']/100 for r in rows]);
    med=lambda x:float(np.median(x))
    gates={'valid_stations':len(rows),'raft_rate_per_year':RATE,'raft_equivalent_years':40000/RATE,
           'gate0_storm_signed_median':med(s),'gate0_pass':bool(abs(med(s))<=.2),
           'storm_abs_median':med(abs(s)),'raft_abs_median':med(abs(a)),
           'gate1_a_pass':bool(med(abs(a))<=.15),'gate1_b_pass':bool(med(abs(a))<=1.1*med(abs(s))),
           'gate1_pass':bool(abs(med(s))<=.2 and med(abs(a))<=.15 and med(abs(a))<=1.1*med(abs(s))),
           'raft_vs_storm_abs_median':med(np.array([abs(r['raft700_ms']/r['storm700_ms']-1) for r in rows]))}
    groups={'TX-LA':list(range(0,5)),'MS-Panhandle':list(range(5,9)),'Peninsula-Keys':list(range(9,15)),'GA-NC':list(range(15,19))}
    gates['segments']={g:{'n':len(ind),'raft_signed_median':med(a[ind]),'storm_signed_median':med(s[ind]),'raft_vs_storm_signed_median':med(np.array([rows[i]['raft700_ms']/rows[i]['storm700_ms']-1 for i in ind]))} for g,ind in groups.items()}
    gates['coast']={k:{'n':len(q),'raft_abs_median':med(abs(a[q])) if q else None,'storm_abs_median':med(abs(s[q])) if q else None} for k,q in {'<10':[i for i,r in enumerate(rows) if float(r['coast_km'])<10],'10-50':[i for i,r in enumerate(rows) if 10<=float(r['coast_km'])<=50],'>50':[i for i,r in enumerate(rows) if float(r['coast_km'])>50]}.items()}
    gates['rate_sensitivity']={str(rate):{'raft_abs_median':med(abs(np.array([details[r['site']]['raft'][f'rate_{rate}_v700']/float(r['asce700_ms'])-1 for r in rows])))} for rate in (10,14.5,20,RATE_NO_LIFE)}
    gates['poci_sensitivity']={name:{str(p):med(np.array([details[r['site']][name][f'poci_{p}_v700']/r[f'{name}700_ms']-1 for r in rows])) for p in (1005,1015)} for name in ('raft','storm')}
    (OUT/'gates.json').write_text(json.dumps(gates,indent=2))
    x=np.arange(N);fig,ax=plt.subplots(figsize=(16,6));ax.plot(x,[float(r['asce700_ms']) for r in rows],'k-o',label='ASCE 7-22 (all hazards)')
    for name,color,shift in [('raft','#c25126',-.12),('storm','#27729c',.12)]:
        y=np.array([r[f'{name}700_ms'] for r in rows]);lo=np.array([r[f'{name}700_ci90_lo_ms'] for r in rows]);hi=np.array([r[f'{name}700_ci90_hi_ms'] for r in rows])
        ax.errorbar(x+shift,y,yerr=np.array([y-lo,hi-y]),fmt='o-',c=color,capsize=3,linewidth=1.5,label=name.upper()+' (90% year-block bootstrap)')
    ax.set_xticks(x,[r['site'] for r in rows],rotation=50);ax.set_ylabel('V700 (m/s), 10 m, Exposure C, 3-s gust');ax.grid(alpha=.2);ax.legend(loc='upper center',bbox_to_anchor=(.5,1.2),ncol=3);fig.subplots_adjust(bottom=.22,top=.76)
    fig.text(.5,.015,'Data: RAFT Xu et al. (2024) Zenodo 10392725; STORM Bloemendaal et al. (2020) 4TU v4; ASCE 7-22 GIS; HURDAT2 NHC (1979-2018). H08 CLIMADA 6.1.0; RAFT annual rate OBSERVED PROXY '+str(RATE)+'/y; POCI ASSUMED 1010 hPa.',ha='center',fontsize=7)
    fig.savefig(OUT/'v700_comparison.png',dpi=160);plt.close(fig)
    assert len(cb)==76
    print(json.dumps(gates,indent=2))
if __name__=='__main__':main()
