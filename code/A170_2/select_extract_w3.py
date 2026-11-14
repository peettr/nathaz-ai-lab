#!/usr/bin/env python3
"""Read-only W3 selection and small native-stagger subwindow extraction.
Run with module load python/3.12.15 on CRC; no OpenFAST calculation.
"""
import argparse, hashlib, json, time
from pathlib import Path
import h5py
import numpy as np

EXPECTED='448008bd92e119e6d6cddbe78344b7455d3bb388bc4143dacd86a9044b51cabd'

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()

def span(a,lo,hi):
    ix=np.flatnonzero((a>=lo)&(a<=hi))
    if not len(ix):raise ValueError(f'empty coordinate slice {lo}..{hi}')
    return slice(max(0,int(ix[0])-1),min(len(a),int(ix[-1])+2))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('source');ap.add_argument('outdir');ap.add_argument('--preverified-sha',default=EXPECTED)
    a=ap.parse_args();src=Path(a.source);out=Path(a.outdir)
    if not out.is_dir() or any(out.iterdir()):raise ValueError('Require existing empty output directory')
    start=time.monotonic()
    with h5py.File(src,'r') as f:
        time_s=f['time'][:];xh=f['xh'][:].astype('f8');xf=f['xf'][:].astype('f8');yh=f['yh'][:].astype('f8');yf=f['yf'][:].astype('f8');zh=f['zh'][:].astype('f8');zf=f['zf'][:].astype('f8')
        assert f['u'].shape==(841,10,162,199) and f['v'].shape==(841,10,162,198)
        assert np.allclose(np.diff(time_s),1) and time_s[0]==1860 and time_s[-1]==2700
        assert abs(zh[0]-.05)<.001 and abs(zh[1]-.15)<.001
        assert len(yf)==len(yh) and np.all(np.diff(xh)>0) and np.all(np.diff(yh)>0)
        nt=len(time_s);ny=len(yh);nx=len(xh)
        speeds=np.empty((nt,ny,nx),dtype='f4');directions=np.empty_like(speeds)
        # A time chunk contains all heights. Each iteration discards unwanted levels.
        for t in range(nt):
            u=f['u'][t,0,:,:].astype('f8');v=f['v'][t,0,:,:].astype('f8')
            uc=(u[:,:-1]+u[:,1:])/2
            vlo=np.searchsorted(yf,yh,side='right')-1
            vlo=np.clip(vlo,0,len(yf)-2)
            weight=(yh-yf[vlo])/(yf[vlo+1]-yf[vlo])
            vc=v[vlo,:]+weight[:,None]*(v[vlo+1,:]-v[vlo,:])
            speeds[t]=np.hypot(uc,vc).astype('f4')
            directions[t]=np.arctan2(vc,uc).astype('f4')
            if t%100==0:print(json.dumps({'frame':t,'elapsed_s':round(time.monotonic()-start,1)}),flush=True)
        peak_idx=speeds.argmax(axis=0);peak_speed=speeds.max(axis=0)
        p1_flat=int(peak_speed.argmax());p1y,p1x=np.unravel_index(p1_flat,(ny,nx))
        distance=np.hypot((xh[None,:]-xh[p1x]),(yh[:,None]-yh[p1y]))
        eligible=(peak_speed>=25)&(distance>=1)
        assert eligible.any(),'No P2 grid point satisfies peak and distance'
        # Circular direction difference over peak +/- 60s: maximum pairwise
        # angular separation via max of |angle(exp(i*(theta_i-theta_j)))|.
        # This is robust to the 360-degree branch cut, unlike max-min unwrap.
        score=np.full((ny,nx),-np.inf,dtype='f8');turn=np.zeros((ny,nx),dtype='f4')
        for iy,ix in np.argwhere(eligible):
            k=int(peak_idx[iy,ix]);d=directions[max(0,k-60):min(nt,k+61),iy,ix].astype('f8')
            # maximum circular separation obtained from pairwise comparisons
            delta=np.arctan2(np.sin(d[:,None]-d[None,:]),np.cos(d[:,None]-d[None,:]))
            turn[iy,ix]=np.degrees(np.max(np.abs(delta)))
            score[iy,ix]=float(peak_speed[iy,ix])*turn[iy,ix]
        p2y,p2x=np.unravel_index(int(score.argmax()),(ny,nx))
        points={}
        for label,(iy,ix) in {'P1':(p1y,p1x),'P2':(p2y,p2x)}.items():
            x=float(xh[ix]);y=float(yh[iy]);k=int(peak_idx[iy,ix])
            # 90-m speed by two-level power law, alpha capped per existing interface.
            # Need time series at the chosen location, not just the peak frame.
            uu=np.empty((nt,2),dtype='f8');vv=np.empty_like(uu)
            j=int(np.clip(np.searchsorted(yf,y,side='right')-1,0,len(yf)-2));wy=(y-yf[j])/(yf[j+1]-yf[j])
            for z in range(2):
                u=f['u'][:,z,iy,ix:ix+2].mean(axis=-1)
                v0=f['v'][:,z,j,ix];v1=f['v'][:,z,j+1,ix]
                uu[:,z]=u;vv[:,z]=v0+wy*(v1-v0)
            s50=np.hypot(uu[:,0],vv[:,0]);s150=np.hypot(uu[:,1],vv[:,1]);alpha=np.clip(np.log(np.maximum(s150,.1)/np.maximum(s50,.1))/np.log(3),-.5,.8)
            s90=s50*(90/50)**alpha
            mean3=np.convolve(s90,np.ones(3)/3,mode='valid')
            peak90=float(mean3.max());where90=int(mean3.argmax())+1
            # wind direction must be independently interpolated; this is speed envelope for gate only.
            points[label]={'xh_km':x,'yh_km':y,'grid_iy_ix':[int(iy),int(ix)],'peak50_mps':float(peak_speed[iy,ix]),'peak50_time_s':float(time_s[k]),'direction_turn_max_deg_pm60s':float(turn[iy,ix]),'score_mps_deg':float(score[iy,ix]) if label=='P2' else None,'distance_from_P1_km':float(distance[iy,ix]),'max90m_3s_mean_mps':peak90,'max90m_3s_time_s':float(time_s[where90]),'gate_ge27':bool(peak90>=27)}
            # Native staggered spatial slabs: 2 km upstream, 0.3 km downstream,
            # +/- 300 m lateral, all native levels; covers moving +/-84-m plane.
            xs=span(xh,x-2.,x+.3);xfs=span(xf,x-2.,x+.3);ys=span(yh,y-.3,y+.3);yfs=span(yf,y-.3,y+.3)
            target=out/(label+'_native.npz')
            np.savez_compressed(target,time_s=time_s,xh_km=xh[xs],xf_km=xf[xfs],yh_km=yh[ys],yf_km=yf[yfs],zh_km=zh,zf_km=zf,u=f['u'][:,:,ys,xfs],v=f['v'][:,:,yfs,xs],w=f['w'][:,:,ys,xs])
            points[label]['extract_file']=target.name;points[label]['extract_sha256']=sha(target);points[label]['extract_bytes']=target.stat().st_size
            print(json.dumps({'extracted':label,'bytes':target.stat().st_size,'elapsed_s':round(time.monotonic()-start,1)}),flush=True)
        result={'source':str(src),'source_sha256_verified_prior':a.preverified_sha,'grid':'u(time,zh,yh,xf), v(time,zh,yf,xh), w(time,zf,yh,xh); x/y in original km; time model seconds','selection':'P1 max over W3 50m collocated speed; P2 peak>=25 and >=1km, maximize peak speed times max pairwise circular separation in peak +/-60s','gate':'max 3-s boxcar (valid) of 90m speed, power alpha=log(U150/U50)/log(3) clipped [-.5,.8], threshold >=27 m/s','points':points,'elapsed_s':time.monotonic()-start}
        (out/'selection.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'done':True,'points':points,'elapsed_s':round(result['elapsed_s'],1)},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
