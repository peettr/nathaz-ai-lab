#!/usr/bin/env python3
"""D420 boundary-plane -> OpenFAST BTS diagnostic interface; run on Colab CPU.
No interior 4D reconstruction: the west boundary is imposed at the rotor plane.
"""
import argparse, hashlib, json, struct, sys
from pathlib import Path
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.signal import butter, sosfiltfilt
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

Y_GRID=np.linspace(-84,84,7)
Z_GRID=np.linspace(6,174,7)
RATIOS=np.array([1., .737388498467752, .33376882226228216])

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def wood_shape(z,zm):
    # Wood/Vicroy-type single-peaked vertical envelope; not a calibrated CM1 fit.
    q=np.asarray(z)/zm
    return q*np.exp(1-q)

def profile(v50,v150,z,kind):
    """Vector-preserving interpolation/extrapolation at one time and lateral point.
    Direction linearly interpolated between two vectors; speed uses two-point shape.
    """
    s0=np.linalg.norm(v50[:2]);s1=np.linalg.norm(v150[:2])
    if kind=='power':
        alpha=np.clip(np.log(max(s1,0.1)/max(s0,0.1))/np.log(3),-.5,.8)
        factor=(z/50.)**alpha
        speed=s0*factor
        meta=float(alpha)
    else:
        # ratio f(150)/f(50)=3*exp(-100/zm); invert when physically admissible.
        ratio=np.clip(max(s1,0.1)/max(s0,0.1),.2,2.9)
        zm=np.clip(-100/np.log(ratio/3),55.,500.)
        speed=s0*wood_shape(z,zm)/wood_shape(50,zm)
        meta=float(zm)
    direction=np.arctan2(v50[1],v50[0])
    d=np.angle(np.exp(1j*(np.arctan2(v150[1],v150[0])-direction)))
    ang=direction+np.clip((z-50)/100,0,1)*d
    w=v50[2]+(v150[2]-v50[2])*np.clip((z-50)/100,0,1)
    return [speed*np.cos(ang),speed*np.sin(ang),w],meta

def bts_write(path,velocity):
    # BTS ID7, scale/offset int16, F-order component,y,z frames, r2 segment_b_run layout.
    a=np.asarray(velocity,np.float32)
    assert a.ndim==4 and a.shape[0]==3 and a.shape[2:]==(7,7)
    encoded=np.empty(a.shape,dtype='<i2'); coeff=[]
    for c in range(3):
        low=float(a[c].min())-.01;high=float(a[c].max())+.01
        scale=65000/(high-low);offset=-32500-scale*low
        encoded[c]=np.rint(np.clip(a[c]*scale+offset,-32768,32767)).astype('<i2')
        coeff.extend((scale,offset))
    label=b'D420 west boundary plane, diagnostic BTS; see cm1_to_bts.py'
    with open(path,'wb') as f:
        f.write(struct.pack('<h4l',7,7,7,0,a.shape[1]))
        f.write(struct.pack('<6f',28.,28.,.5,12.,90.,6.))
        f.write(struct.pack('<6f',*coeff));f.write(struct.pack('<l',len(label)));f.write(label)
        for i in range(a.shape[1]):f.write(encoded[:,i].tobytes(order='F'))
    raw=path.read_bytes();n=struct.unpack('<h4l',raw[:18]);assert n==(7,7,7,0,a.shape[1]);assert len(raw)==70+len(label)+a.shape[1]*294
    return coeff

def phase_pad(src,dst,n=14):
    # r2 observed OpenFAST hub lookup t+7 s; prepend 14 x 0.5 s first-frame copies.
    b=src.read_bytes();fid,nz,ny,ntwr,nt=struct.unpack('<h4l',b[:18])
    off=70+struct.unpack('<l',b[66:70])[0]
    frame=2*(3*ny*nz+3*ntwr)
    assert fid==7 and ntwr==0 and len(b)==off+nt*frame
    with dst.open('wb') as f:
        f.write(struct.pack('<h4l',fid,nz,ny,ntwr,nt+n));f.write(b[18:off]);f.write(b[off:off+frame]*n);f.write(b[off:])

def main():
    p=argparse.ArgumentParser();p.add_argument('packet');p.add_argument('output');p.add_argument('--profile',choices=['power','wood'],default='power');p.add_argument('--seed',type=int,default=112);args=p.parse_args()
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
    source=Path(args.packet)
    with np.load(source) as data:
        t=data['t_s'];stime=data['source_time_s'];pts=data['west_points_m'];v=data['west_U'];zh=data['zh_m']
        assert v.shape==(261,29,40,3) and np.array_equal(t,np.arange(261)) and np.array_equal(stime-t,np.full(261,2120))
        assert np.all(np.diff(zh)>0) and np.allclose(pts[:,:,0],7800) and np.allclose(pts[:,:,2],zh[:,None])
        yy=pts[0,:,1];assert np.all(np.diff(yy)>0)
        # Origin and native stagger: U on xf, V on yf, W on zf; west_U is collocated.
        assert data['initial_native_u'].shape==(29,42,41) and data['initial_native_v'].shape==(29,42,42)
        assert data['initial_native_w'].shape==(30,42,42)
        assert np.all(np.diff(data['native_xf_m'])>0) and np.all(np.diff(data['native_yf_m'])>0) and np.all(np.diff(data['native_zf_m'])>0)
        origin=data['origin_source_m'].tolist()
        assert np.allclose(origin,[52800.00305175781,18200.000762939453,0])
        assert np.isfinite(v).all()
        # t=0 west is independently sampled from initial native staggered fields; original packet verified upstream.
        z0,z1=float(zh[0]),float(zh[1]);assert z0<51 and z1>140 and z1<160,(z0,z1)
        positions={'near_geometric':9700.,'offset_geometric':10400.}
        metadata={'packet_sha256':sha(source),'source_origin_m':origin,'source_time_bounds_s':[float(stime[0]),float(stime[-1])],
                  'local_time_bounds_s':[float(t[0]),float(t[-1])],'source_west_x_local_m':7800.,'turbine_x_local_m':8000.,
                  'note':'west boundary time series imposed at rotor plane; no 200m advection or true interior 4D evolution; y labels geometric, not verified storm-center track',
                  'native_stagger_shapes':{k:list(data[k].shape) for k in ('initial_native_u','initial_native_v','initial_native_w')},'profiles':{},'cases':{}}
        for name,y0 in positions.items():
            # y interpolation only, physical y of turbine. Need +/-84m within 40 west samples.
            assert yy[0]<y0-84 and yy[-1]>y0+84
            low=np.empty((3,len(t),7)); high=np.empty_like(low)
            for iz,target in enumerate((z0,z1)):
                interp=RegularGridInterpolator((yy,),v[:,iz,:,:].transpose(1,0,2),bounds_error=True)
                for iy,y in enumerate(y0+Y_GRID):
                    vec=interp([y])[0]
                    (low if iz==0 else high)[:,:,iy]=vec.T
            ts=np.arange(0,260.0001,.5)
            wind=np.zeros((3,len(ts),7,7),np.float32);fit=[]
            for i,at in enumerate(ts):
                j=min(int(at),259);a=at-j
                for iy in range(7):
                    l=low[:,j,iy]*(1-a)+low[:,j+1,iy]*a
                    h=high[:,j,iy]*(1-a)+high[:,j+1,iy]*a
                    for iz,z in enumerate(Z_GRID):
                        vec,param=profile(l,h,z,args.profile);wind[:,i,iy,iz]=vec
                        if iy==3 and iz==3:fit.append(param)
            # r2 spectral synthesis on 7x7 rotor grid, then high-pass at f_c=Uref/100m.
            import segment_b_run as b
            coords=[(0.,float(y),float(z)) for y in Y_GRID for z in Z_GRID]
            b.UCOH=float(np.median(np.linalg.norm(low[:2,:,3],axis=0)))
            k=b.spectral_field(args.seed,len(ts),coords)
            hub=np.linalg.norm(wind[:2,:,3,3],axis=0)
            fc=float(np.clip(np.median(hub)/100.,.04,.35))
            sos=butter(3,fc,fs=2.,btype='highpass',output='sos')
            for c in range(3):
                fluct=sosfiltfilt(sos,k[c],axis=1)
                fluct=fluct/np.maximum(fluct.std(axis=1,keepdims=True),1e-6)
                wind[c]+=float(.1*np.median(hub))*RATIOS[c]*fluct.T.reshape(len(ts),7,7)
            raw=output/(name+'_'+args.profile+'_raw.bts');final=output/(name+'_'+args.profile+'.bts')
            coeff=bts_write(raw,wind);phase_pad(raw,final)
            np.savez_compressed(output/(name+'_diagnostic.npz'),t_s=ts,hub_u=wind[0,:,3,3],hub_v=wind[1,:,3,3],hub_w=wind[2,:,3,3],cm1_boundary_u=low[0,:,3],cm1_boundary_v=low[1,:,3])
            metadata['cases'][name]={'y_local_m':y0,'bts_sha256':sha(final),'bts_bytes':final.stat().st_size,
                'hub_speed_range_mps':[float(hub.min()),float(hub.max())], 'hp_cutoff_hz':fc,'synthetic_sigma_u_mps':float(.1*np.median(hub)),
                'profile_parameter_hub_range':[float(np.min(fit)),float(np.max(fit))], 'bts_scale_offset':coeff}
            fig,axes=plt.subplots(2,1,figsize=(9,6),sharex=True)
            speed=np.hypot(wind[0,:,3,3],wind[1,:,3,3]);ang=np.rad2deg(np.unwrap(np.arctan2(wind[1,:,3,3],wind[0,:,3,3])))
            axes[0].plot(ts,speed,label='CM1 west + synthetic <100m');axes[1].plot(ts,ang,label='CM1 wind direction')
            # Different event/time origins: only compare envelope shapes, NOT pointwise skill.
            from wind_field_probe import CASES,field
            u,v_,_=field(CASES[0],0,0,90,ts+360)
            ref=np.hypot(u,v_)
            axes[0].plot(ts,ref,label='Nguyen Case I analytic (t+360s, illustrative)',alpha=.7)
            axes[0].set_ylabel('horizontal hub speed [m/s]');axes[1].set_ylabel('atan2(v,u) [deg]');axes[1].set_xlabel('CM1 local time [s]')
            axes[0].legend(fontsize=8);axes[1].legend(fontsize=8);fig.suptitle(f'{name} {args.profile}: different event clocks, no event alignment')
            fig.tight_layout();fig.savefig(output/(name+'_series.png'),dpi=140);plt.close(fig)
        metadata['profiles'][args.profile]={'first_source_levels_m':[z0,z1], 'rotor_grid_z_m':Z_GRID.tolist(),
            'formula': 'two-point magnitude power alpha=log(U150/U50)/log(3), cap [-0.5,0.8]' if args.profile=='power' else 'Wood/Vicroy-type z/zm exp(1-z/zm), zm=-100/log((U150/U50)/3), bounded [55,500] m',
            'direction':'interpolate unwrapped angle 50-150m, clamp beyond; w linear 50-150m, clamp beyond',
            'scope':'engineering extrapolation for 6-50m and 150-174m; two levels cannot establish either shape'}
    (output/'manifest.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'profile':args.profile,'cases':metadata['cases']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
