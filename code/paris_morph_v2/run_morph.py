"""A1 Paris PALUPD morphology transfer. Run with .venv/bin/python run_morph.py.
Fetch IGN BD TOPO buildings in a 2 km bounding box, then reuse cached file.
Reuses previous fold predictions/airport MOS; held-out PALUPD wind only for scoring.
"""
from pathlib import Path
from datetime import datetime, timezone
import json, math
import numpy as np
import pandas as pd
import requests
from shapely.geometry import shape, Polygon, Point
from shapely.ops import transform
from shapely.validation import make_valid
from pyproj import Transformer
from sklearn.metrics import roc_auc_score
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

R=Path(__file__).resolve().parent; P=R.parent
URL='https://data.geopf.fr/wfs/ows'
LON,LAT=2.3806,48.8278
WGS_TO_L93=Transformer.from_crs(4326,2154,always_xy=True).transform
X,Y=WGS_TO_L93(LON,LAT)
FEAT=R/'ign_bdtopo_2km.geojson'

def fetch():
    if FEAT.exists(): return json.loads(FEAT.read_text())
    base=dict(SERVICE='WFS',VERSION='2.0.0',REQUEST='GetFeature',TYPENAMES='BDTOPO_V3:batiment',
              SRSNAME='CRS:84',BBOX='2.350,48.808,2.411,48.848,CRS:84',OUTPUTFORMAT='application/json')
    allf=[];s=requests.Session()
    for off in range(0,30000,1000):
        r=s.get(URL,params={**base,'STARTINDEX':off,'COUNT':1000},timeout=180)
        r.raise_for_status();j=r.json()
        if 'features' not in j:raise ValueError(f'API failure {str(j)[:500]}')
        allf.extend(j['features']);print('IGN BD TOPO',off,len(j['features']),flush=True)
        if len(j['features'])<1000:break
    ids=[f['id'] for f in allf]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate pagination')
    z={'type':'FeatureCollection','features':allf,'retrieved_utc':datetime.now(timezone.utc).isoformat(),
       'api':URL,'query':base}
    FEAT.write_text(json.dumps(z,separators=(',',':')))
    return z

def sector(center):
    # Meteorological direction FROM, 30-degree upwind annular wedge; edges densely sampled.
    ang=np.linspace(center-15,center+15,61)
    def xy(radius,a):
        rad=np.deg2rad(a);return (X+radius*np.sin(rad),Y+radius*np.cos(rad))
    outer=[xy(2000,a) for a in ang];inner=[xy(500,a) for a in ang[::-1]]
    return Polygon(outer+inner)

def morph(features):
    shapes=[]; missing=0; invalid=0
    for f in features:
        p=f['properties'];h=p.get('hauteur')
        if h is None or not np.isfinite(h) or h<=0:
            missing+=1;continue
        g=transform(WGS_TO_L93,shape(f['geometry']))
        if not g.is_valid:g=make_valid(g);invalid+=1
        if not g.is_empty:shapes.append((g,float(h)))
    records=[]
    for direction in range(0,360,30):
        clip=sector(direction);area=clip.area
        foot=0.;volume=0.;front=0.;n=0
        # Front-facing width measured on the crosswind axis; clipped boundary buildings included proportionally.
        a=math.radians(direction);cross=np.array([math.cos(a),-math.sin(a)])
        for g,h in shapes:
            if not g.intersects(clip):continue
            q=g.intersection(clip)
            if q.is_empty or q.area<=0:continue
            n+=1;foot+=q.area;volume+=q.area*h
            polys=[q] if q.geom_type=='Polygon' else [v for v in getattr(q,'geoms',[]) if v.geom_type=='Polygon']
            for pol in polys:
                cc=np.array(pol.exterior.coords)[:,:2]@cross
                front+=(max(cc)-min(cc))*h
        lp=foot/area;lf=front/area;H=volume/foot if foot else np.nan
        A=4.43;CD=1.2;kappa=.4
        dh=1+(lp-1)*A**(-lp)
        zH=(1-dh)*math.exp(-((.5*CD*(1-dh)*lf)/(kappa*kappa))**(-.5)) if lf>0 and 0<dh<1 else np.nan
        records.append(dict(sector_from_deg=direction,n_buildings=n,area_m2=area,coverage=lp,
                            frontal_density=lf,H_m=H,d_m=dh*H,z0_m=zH*H,
                            missing_height_in_2km=missing,invalid_geometry_repaired=invalid))
    return pd.DataFrame(records)

def bootstrap(g, col, nboot=5000):
    z=g.copy();z['day']=z.valid_utc.dt.floor('D')
    by=z.groupby('day').apply(lambda v:pd.Series({'m':np.abs(v[col]-v.wind).sum(),
                                                'b':np.abs(v.S0-v.wind).sum()}),include_groups=False)
    rng=np.random.default_rng(20261014+int(g.lead_h.iloc[0])+len(col))
    ix=rng.integers(0,len(by),size=(nboot,len(by)))
    draws=by.to_numpy()[ix].sum(axis=1)
    return dict(relative_pct=float((by.m.sum()/by.b.sum()-1)*100),
                ci95_pct=(100*np.quantile(draws[:,0]/draws[:,1]-1,[.025,.975])).tolist(),
                days=len(by))

def score(g,col):
    v=g[col].to_numpy();o=g.wind.to_numpy();ev=o>=8;pred=v>=8
    hit=int((ev&pred).sum());miss=int((ev&~pred).sum());fa=int((~ev&pred).sum())
    return dict(n=len(g),mae=float(np.mean(np.abs(v-o))),bias=float(np.mean(v-o)),
                auc8=float(roc_auc_score(ev,v)) if len(set(ev))==2 else None,
                csi8=hit/(hit+miss+fa) if hit+miss+fa else None,
                hits=hit,misses=miss,false_alarms=fa)

def main():
    fs=fetch();m=morph(fs['features']);m.to_csv(R/'sectors.csv',index=False)
    if (m.z0_m<=0).any() or (m.d_m>=111).any():raise ValueError('invalid urban morph profile')
    raw=pd.read_csv(P/'paris_transfer_v1'/'paired_transfer.csv.gz',parse_dates=['init_utc','valid_utc'])
    v2=pd.read_csv(P/'paris_lidar_v2'/'paired_station.csv.gz',parse_dates=['init_utc','valid_utc'])
    vv=v2[(v2.station=='PALUPD')&(v2.target_agl==100)&(v2.source.isin(['GFS','GRAP_v100_GFS']))]
    vv=vv[['source','init_utc','valid_utc','lead_h','fc_u','fc_v']].drop_duplicates()
    d=raw.merge(vv,on=['source','init_utc','valid_utc','lead_h'],validate='one_to_one')
    d=d.dropna(subset=['airport10','S0','S1','wind','fc_u','fc_v']).copy()
    # Pair forecast FROM direction; do not use local high-altitude observed direction to classify.
    d['wind_from_deg']=(np.degrees(np.arctan2(-d.fc_u,-d.fc_v))+360)%360
    d['sector_from_deg']=((d.wind_from_deg+15)//30*30).astype(int)%360
    d=d.merge(m[['sector_from_deg','z0_m','d_m']],on='sector_from_deg',validate='many_to_one')
    f03=np.log(111/.03)/np.log(10/.03)
    # S1 already trained on airport wind by each leave-month-out fold; recover that exact ground prediction.
    d['ground_mos']=d.S1/f03
    zref=.03; dref=0.;zrefheight=10.
    d['morph_factor']=np.log((111-d.d_m)/d.z0_m)/np.log((zrefheight-dref)/zref)
    d['M']=d.ground_mos*d.morph_factor
    d['M_ref_z0_0p03']=d.S1
    d['M_ref_z0_0p3']=d.ground_mos*np.log(111/.3)/np.log(10/.3)
    d['M_ref_z0_0p3_d0']=d['M_ref_z0_0p3']
    if not np.isfinite(d.M).all():raise ValueError('nonfinite predictions')
    d.to_csv(R/'paired_morph.csv.gz',index=False,compression='gzip')
    out=[];sector_scores=[]
    for (src,lead),g in d.groupby(['source','lead_h']):
        for col in ['S0','M','M_ref_z0_0p03','M_ref_z0_0p3']:
            rec=dict(source=src,lead_h=int(lead),method=col,**score(g,col))
            if col!='S0':rec['vs_S0']=bootstrap(g,col)
            out.append(rec)
        for sec,sub in g.groupby('sector_from_deg'):
            ss=dict(source=src,lead_h=int(lead),sector_from_deg=int(sec),n=len(sub),
                    mae_morph=float(np.abs(sub.M-sub.wind).mean()),mae_S0=float(np.abs(sub.S0-sub.wind).mean()),
                    bias_morph=float((sub.M-sub.wind).mean()))
            sector_scores.append(ss)
    assert all(x['n']==317 for x in out),'sample mismatch; stop rather than changing sample'
    payload=dict(records=out,sector_scores=sector_scores,morphology=m.to_dict('records'),
      definitions=dict(building='IGN BD TOPO V3 hauteur (2026 access, historical mismatch possible)',
       source='500-2000m upwind annulus, 30-degree forecast direction sectors, area-weighted H',
       macdonald='A=4.43, C_D=1.2, kappa=0.4, beta not introduced (original eq 22/23)',
       airport='z0_ref=0.03 m assumed; d_ref=0 m; z_ref=10 m assumed LFPO sensor height',
       fold='reuses transfer-v1 S1 LFPO METAR ground MOS and S0 local MOS; no held-out high-alt wind for M',
       bootstrap='5000 validation-day resamples, paired S0 vs M'),
       input_files=[str(FEAT),str(P/'paris_transfer_v1'/'paired_transfer.csv.gz'),str(P/'paris_lidar_v2'/'paired_station.csv.gz')])
    (R/'metrics.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False))
    fig,ax=plt.subplots(figsize=(10,4.6))
    for src,marker in [('GFS','o'),('GRAP_v100_GFS','s')]:
        for lead,ls in [(24,'-'),(48,'--')]:
            v=[next(q['mae'] for q in out if q['source']==src and q['lead_h']==lead and q['method']==c)
               for c in ['S0','M_ref_z0_0p03','M','M_ref_z0_0p3']]
            ax.plot(range(4),v,marker=marker,ls=ls,label=f'{src} {lead} h')
    ax.set_xticks(range(4),['local 111m MOS','assumed z0=.03','IGN morphology','assumed z0=.3'])
    ax.set_ylabel('111 m MAE (m/s)');ax.grid(alpha=.3);ax.legend(fontsize=8,ncol=2)
    fig.text(.01,.01,'Sources: IGN BD TOPO V3 (Licence Ouverte 2.0); Morrison et al. 2025 Zenodo 17710093; NOAA GFS / CIRA AIWP; IEM LFPO METAR',fontsize=7)
    fig.tight_layout(rect=(0,.04,1,1));fig.savefig(R/'morph_mae.png',dpi=170);plt.close(fig)
    print(json.dumps({'features':len(fs['features']),'morph':m[['sector_from_deg','coverage','frontal_density','H_m','z0_m','d_m']].round(3).to_dict('records'),'records':out},ensure_ascii=False))
if __name__=='__main__':main()
