"""Common-grid shift test and explicit coordinate-registration diagnostics."""
import pathlib,json,numpy as np
P=pathlib.Path('/content/l264diag04');T=P/'texas'; F=T/'predictions'; meta=json.loads((T/'window.json').read_text())
westy,westx=meta['west_offset']; shifty,shiftx=westy,westx+150; h,w=meta['shape']; d=shiftx-westx
assert 0<d<w
out={'source':'AERO-ODE 99516ae9cf / HF weights; NOAA HRRR 2024-04-01 f00 HGT, VGTYP and coordinates','west_offset':[westy,westx],'shift_offset':[shifty,shiftx],'shared_grid_cells':h*(w-d),'forecast_leads':[1,24,72],'metrics':{}}
def stat(a,b):
    z=np.asarray(a,dtype=np.float64)-np.asarray(b,dtype=np.float64)
    return {'rmse':float(np.sqrt(np.mean(z*z))),'mean_difference':float(z.mean()),'p95_absolute_difference':float(np.quantile(abs(z),.95)),'max_absolute_difference':float(abs(z).max())}
for net,channels in [('air',{'Z925':4}),('surface',{'T2m':3,'U10':1})]:
    with np.load(F/f'shift_original_{net}_01.npz',allow_pickle=False) as z: original=z['pred']
    with np.load(F/f'shift_shift_{net}_01.npz',allow_pickle=False) as z: moved=z['pred']
    assert original.shape[0]==moved.shape[0]==73 and original.shape[-2:]==moved.shape[-2:]==(h,w)
    for name,c in channels.items():
        out['metrics'][name]={str(lead):stat(original[lead,c,:,d:],moved[lead,c,:,:w-d]) for lead in [1,24,72]}
    del original,moved
coords={name:np.load(T/(name+'.npy'),mmap_mode='r') for name in ('noaa_lat','noaa_lon')}
for name in coords:
    ref=np.load(P/'AERO_ODE/AERO_Surface_WD/Hrrr_rb/data'/('hrrr_west_lat.npy' if name=='noaa_lat' else 'hrrr_west_lon.npy'))
    assert ref.shape==(h,w)
    noaa=coords[name][westy:westy+h,westx:westx+w]
    gap=(noaa-ref+180)%360-180 if name=='noaa_lon' else noaa-ref
    out[name+'_author_west_max_abs_degree']=float(np.max(np.abs(gap)))
    shifted=coords[name][shifty:shifty+h,shiftx:shiftx+w]
    out[name+'_shared_grid_max_abs_degree']=float(np.max(abs(noaa[:,d:]-shifted[:,:w-d])))
# Explicit orientation: output index (0,0) is NOAA first row/column; y increases northward here.
lat=coords['noaa_lat'];lon=coords['noaa_lon']
out['west_lat_delta_y_deg']=float(lat[westy+1,westx]-lat[westy,westx]);out['west_lon_delta_x_deg']=float(((lon[westy,westx+1]-lon[westy,westx]+180)%360)-180)
(T/'shift_diagnostics.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2),flush=True)
import h5py,matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
with h5py.File(P/'AERO_ODE/AERO_Surface_WD/Hrrr_rb/data/west_geo_interpolate.h5') as f:author_geo=np.asarray(f['fields'][0])
noaa_geo=np.load(T/'HGT.npy',mmap_mode='r')[westy:westy+h,westx:westx+w]
fig,ax=plt.subplots(1,3,figsize=(13,4),constrained_layout=True)
for a,img,title in zip(ax,[author_geo,noaa_geo,noaa_geo-author_geo],['Author west terrain','NOAA HRRR same-grid terrain','NOAA minus author']):
    m=a.imshow(img,origin='lower');a.set_title(title);a.set_xlabel('x (east)');a.set_ylabel('y (north)');fig.colorbar(m,ax=a,shrink=.7)
fig.suptitle('Sources: AERO-ODE HF west static HDF5; NOAA HRRR HGT:surface 2024-04-01 f00')
fig.savefig(T/'terrain_alignment_diag.png',dpi=130);plt.close(fig)
