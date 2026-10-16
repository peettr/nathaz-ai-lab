#!/usr/bin/env python3
"""H6 paired peak audit; no wind-height/gust conversion or parameter fitting."""
import csv,json,math
from pathlib import Path
import numpy as np,pandas as pd,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import requests
P=Path(__file__).resolve().parent;H4=P.parent/'h4'
URL='https://services.dat.noaa.gov/arcgis/rest/services/nws_damageassessmenttoolkit/DamageViewer/FeatureServer/0/query'
DAYS=['20240601','20250709']

def score(g,col,truth):
    d=g[col].to_numpy(dtype=float)-g[truth].to_numpy(dtype=float)
    return {'n':len(d),'bias_ms':round(float(d.mean()),3),'rmse_ms':round(float(np.sqrt(np.mean(d*d))),3),'mae_ms':round(float(np.mean(abs(d))),3)}

def dat_audit():
    out=[]
    for start,end in [('2024-06-01','2024-06-02'),('2025-07-08','2025-07-10')]:
        where=f"stormdate >= TIMESTAMP '{start} 00:00:00' AND stormdate < TIMESTAMP '{end} 00:00:00' AND efscale = 'TSTM/Wind'"
        params={'f':'json','geometry':'-98.5,31.5,-95.5,34','geometryType':'esriGeometryEnvelope','spatialRel':'esriSpatialRelIntersects','inSR':4326,'where':where,'outFields':'objectid,stormdate,windspeed,efscale,lat,lon','returnGeometry':'false','resultRecordCount':1000}
        r=requests.get(URL,params=params,timeout=45);r.raise_for_status();data=r.json()
        if 'error' in data:raise ValueError(data['error'])
        out.append({'date_range_utc':[start,end],'query_url':r.url,'count':len(data['features']),'exceededTransferLimit':data.get('exceededTransferLimit',False),'features':[x['attributes'] for x in data['features']]})
    return out

def main():
    audit=json.loads((P/'radar_scan_audit_h6.json').read_text())
    assert all(a['processed']==a['volumes_listed'] and not a['failed'] for a in audit.values()),'incomplete radar audit'
    radar=pd.read_csv(P/'radar_station_scans_h6.csv',dtype={'event':str,'station':str})
    radar['radial_abs_ms']=pd.to_numeric(radar['radial_abs_ms'])
    peaks=pd.read_csv(H4/'peaks_h4v3.csv');peaks['event']=peaks.event.str.replace('-','',regex=False)
    peaks=peaks[peaks.event.isin(DAYS)].copy()
    best={'20240601':'ok75','20250709':'idw'}  # H4 prereg, respective event best interpolation
    peak_obs=[];all_obs=[]
    for d in DAYS:
        w=json.loads((H4/f'window_{d}_h4.json').read_text())
        raw=pd.read_csv(H4/f'raw_minute_{d}_h4.csv.gz')
        raw['ts']=pd.to_datetime(raw['valid(UTC)'],utc=True)
        raw=raw[(raw.ts>=pd.Timestamp(w['window_start']))&(raw.ts<=pd.Timestamp(w['window_end']))]
        for station,g in raw.groupby('station'):
            if (peaks.event.eq(d)&peaks.station.eq(station)).any():
                m=pd.to_numeric(g.sknt,errors='coerce');z=pd.to_numeric(g.gust_sknt,errors='coerce')
                if m.notna().any() and z.notna().any():
                    peak_obs.append({'event':d,'station':station,'continuous_peak_utc':g.loc[m.idxmax(),'ts'].isoformat(),'gust_peak_utc':g.loc[z.idxmax(),'ts'].isoformat()})
        all_obs.append(raw)
    obs=pd.concat(all_obs,ignore_index=True)
    obs['event']=obs.ts.dt.strftime('%Y%m%d')
    obs['continuous_ms']=pd.to_numeric(obs.sknt,errors='coerce')*0.514444
    obs['gust_ms']=pd.to_numeric(obs.gust_sknt,errors='coerce')*0.514444
    po=pd.DataFrame(peak_obs)
    grouped=radar.groupby(['event','station']).agg(radar_peak_ms=('radial_abs_ms','max'),scan_n=('radial_abs_ms','size'),beam_center_agl_m=('beam_center_agl_m','median'),radar_range_km=('radar_range_km','median')).reset_index()
    paired=grouped.merge(peaks,on=['event','station'],how='inner').merge(po,on=['event','station'],how='left')
    paired['h4_interp_cont_ms']=paired.apply(lambda r:r[best[r.event]],axis=1)
    paired['h4_interp_gust_ms']=paired.apply(lambda r:r['gust_'+best[r.event]],axis=1)
    radar['scan_ts']=pd.to_datetime(radar.scan_utc,utc=True)
    obs_groups={(d,s):g for (d,s),g in obs.groupby(['event','station'])}
    near={}
    for (d,s),g in radar.groupby(['event','station']):
        for variable,field in [('continuous','continuous_ms'),('gust','gust_ms')]:
            o=obs_groups.get((d,s)); valid=o[o[field].notna()] if o is not None else None
            if valid is None or valid.empty:continue
            ts=valid.ts.astype('int64').to_numpy(); vv=valid[field].to_numpy()
            delta=np.abs(g.scan_ts.astype('int64').to_numpy()[:,None]-ts[None,:])/60e9
            good=(delta.min(axis=1)<=3)
            # Only descriptive scan-time comparison; nearest valid minute per scan.
            near[(d,s,variable)]={'matched_scans':int(good.sum()),'obs_peak_in_matched_minutes_ms':float(vv[np.argmin(delta,axis=1)[good]].max()) if good.any() else None,'radar_peak_in_matched_scans_ms':float(g.radial_abs_ms.to_numpy()[good].max()) if good.any() else None}
    metrics={'source':'NOAA NEXRAD Level II via unidata-nexrad-level2 public S3; IEM 1-min via H4; H4 LOO peaks','audit':audit,'n_h4_eligible_by_day':{d:int((peaks.event==d).sum()) for d in DAYS},'h4_best_method_by_day':best,'radar_pairing':{},'dat':dat_audit()}
    for d in DAYS+['combined']:
        g=paired if d=='combined' else paired[paired.event==d]
        metrics['radar_pairing'][d]={'n_station_events':len(g),'scan_n_range':[int(g.scan_n.min()),int(g.scan_n.max())] if len(g) else [],'beam_agl_m_range':[round(float(g.beam_center_agl_m.min()),1),round(float(g.beam_center_agl_m.max()),1)] if len(g) else [],'continuous':{'radar_radial':score(g,'radar_peak_ms','obs'),'h4_interp':score(g,'h4_interp_cont_ms','obs')},'gust':{'radar_radial_not_same_quantity':score(g,'radar_peak_ms','gust'),'h4_interp':score(g,'h4_interp_gust_ms','gust')}}
    paired['radar_scan_covered_cont_peak']=paired.apply(lambda r:any(abs(pd.Timestamp(r.continuous_peak_utc)-ts)<=pd.Timedelta(minutes=3) for ts in radar[(radar.event==r.event)&(radar.station==r.station)].scan_ts) if isinstance(r.continuous_peak_utc,str) else False,axis=1)
    paired['radar_scan_covered_gust_peak']=paired.apply(lambda r:any(abs(pd.Timestamp(r.gust_peak_utc)-ts)<=pd.Timedelta(minutes=3) for ts in radar[(radar.event==r.event)&(radar.station==r.station)].scan_ts) if isinstance(r.gust_peak_utc,str) else False,axis=1)
    metrics['peak_time_with_valid_radar_scan_3min']={'continuous':int(paired.radar_scan_covered_cont_peak.sum()),'gust':int(paired.radar_scan_covered_gust_peak.sum())}
    for variable in ['continuous','gust']:
        matched=[v for (d,s,q),v in near.items() if q==variable and v['matched_scans']>0]
        metrics['nearest_3min_'+variable]={'station_events':len(matched),'matched_scans':sum(v['matched_scans'] for v in matched),'radar_peak_minus_obs_peak_on_matched_scans_ms':score(pd.DataFrame(matched),'radar_peak_in_matched_scans_ms','obs_peak_in_matched_minutes_ms') if matched else None}
    paired.to_csv(P/'paired_station_h6.csv',index=False)
    (P/'metrics_h6.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False)+'\n')
    fig,ax=plt.subplots(1,2,figsize=(11,5))
    for i,(truth,interp,label) in enumerate([('obs','h4_interp_cont_ms','1-min continuous peak'),('gust','h4_interp_gust_ms','5-s gust peak (not same quantity as radar)')]):
        for d,m in [('20240601','o'),('20250709','s')]:
            g=paired[paired.event==d];ax[i].scatter(g[truth],g.radar_peak_ms,marker=m,label=f'{d} |Vr|')
            ax[i].scatter(g[truth],g[interp],marker=m,facecolors='none',edgecolors='gray',label=f'{d} H4 interpolation')
        ax[i].plot([0,40],[0,40],'k--',lw=.7);ax[i].set(xlabel='ASOS observed peak (m/s)',ylabel='radar |Vr| or H4 prediction (m/s)',title=label,xlim=(0,40),ylim=(0,40));ax[i].legend(fontsize=7)
    fig.suptitle('KFWS lowest velocity sweep; radar beam-height radial component is NOT 10-m gust')
    fig.text(.01,.01,'NOAA NEXRAD Level II public Unidata S3 mirror; IEM ASOS 1-minute; H4 LOO interpolation',fontsize=8)
    fig.tight_layout(rect=(0,.04,1,.94));fig.savefig(P/'radar_vs_station_h6.png',dpi=130);plt.close(fig)
    print(json.dumps({d:metrics['radar_pairing'][d] for d in DAYS+['combined']},indent=2))
    print('peak time covered',metrics['peak_time_with_valid_radar_scan_3min'],'DAT',[(x['date_range_utc'],x['count']) for x in metrics['dat']])
if __name__=='__main__':main()
