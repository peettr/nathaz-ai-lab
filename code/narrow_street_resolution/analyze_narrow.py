"""Read-only paired urban point audit; outputs only beside this script."""
from pathlib import Path
import csv, json, math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
C1=ROOT/'06_Logs/wp1b_ibm/resolution_crop_v2/C1v2_offset_samples.json'
C05=ROOT/'06_Logs/wp1b_ibm/resolution_c05/C05_offset_samples_a_r10.json'
FEATURE=ROOT/'06_Logs/method_study/deadpoints_diag/points_80_su.csv'
PLANE=ROOT/'06_Logs/method_study/B2s_nearwall_sampling/plane_z2.npz'
A={int(r['id']):r for r in json.loads(C1.read_text())['rows']}
B={int(r['id']):r for r in json.loads(C05.read_text())['rows']}
F={int(r['id']):r for r in csv.DictReader(FEATURE.open())}
assert len(A)==len(B)==55 and set(A)==set(B) and set(A)<=set(F)
rows=[]
for i in sorted(A):
    a=A[i];b=B[i];f=F[i]
    assert abs(float(a['after'])-float(b['after']))<1e-10
    s1=float(a['sample']['plus_dx']['exp_ratio']);s05=float(b['sample']['plus_dx']['exp_ratio']);obs=float(a['after'])
    width=float(f['width_min_m']) if f['width_min_m'] else math.nan
    wall=float(f['wall_m'])
    g='unknown' if not math.isfinite(width) else '<4' if width<4 else '4-8' if width<8 else '8-15' if width<15 else '>=15'
    rows.append({'id':i,'x_m':float(f['x_m']),'y_m':float(f['y_m']),'width_min_m':width,'width_group':g,'wall_m':wall,'wall_lt1':wall<1,
      'obs_W':obs,'C1_Sstar':s1,'C05_Sstar':s05,'C1_ratio':s1/obs,'C05_ratio':s05/obs,
      'delta_ratio':(s05-s1)/obs,'delta_Sstar':s05-s1,'C1_abs_err':abs(s1-obs),'C05_abs_err':abs(s05-obs),
      'delta_abs_err':abs(s05-obs)-abs(s1-obs),'effect':'improve' if abs(s05-obs)<abs(s1-obs)-1e-12 else 'worsen' if abs(s05-obs)>abs(s1-obs)+1e-12 else 'tie'})
with (OUT/'paired_points_55.csv').open('w',newline='') as h:
    w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def agg(rs):
    n=len(rs)
    if not n:return None
    return {'n':n,'ids':[r['id'] for r in rs], 'C1_mean_point_ratio':sum(r['C1_ratio'] for r in rs)/n,
      'C05_mean_point_ratio':sum(r['C05_ratio'] for r in rs)/n,
      'delta_mean_point_ratio':sum(r['delta_ratio'] for r in rs)/n,
      'C1_ratio_of_means':sum(r['C1_Sstar'] for r in rs)/sum(r['obs_W'] for r in rs),
      'C05_ratio_of_means':sum(r['C05_Sstar'] for r in rs)/sum(r['obs_W'] for r in rs),
      'C1_MAE':sum(r['C1_abs_err'] for r in rs)/n,'C05_MAE':sum(r['C05_abs_err'] for r in rs)/n,
      'improve':sum(r['effect']=='improve' for r in rs),'worsen':sum(r['effect']=='worsen' for r in rs),'tie':sum(r['effect']=='tie' for r in rs)}
summary={'width':{g:agg([r for r in rows if r['width_group']==g]) for g in ['<4','4-8','8-15','>=15','unknown']},
 'wall':{'<1':agg([r for r in rows if r['wall_lt1']]),'>=1':agg([r for r in rows if not r['wall_lt1']])},'all':agg(rows),
 'pair':{'C1':str(C1),'C05':str(C05),'features':str(FEATURE),'observable':'Sstar, not Su; no coarse/fine Su saved'}}
wide=[r for r in rows if r['width_group']=='>=15']
summary['contrasts']={g:summary['width'][g]['delta_mean_point_ratio']-agg(wide)['delta_mean_point_ratio'] if summary['width'][g] else None for g in ['<4','4-8','8-15']}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False))

p=np.load(PLANE);su=p['Su'];flags=p['flags'];orig=p['physical_xy_origin'];
assert su.shape==(500,500) and flags.shape==su.shape and int(p['physical_z_m'])==2
# Plane stored as y,x, physical origin -1,-1 (the +1 cell registration).
fig,ax=plt.subplots(figsize=(10,9));image=np.ma.masked_where((flags&1)!=0,su/3.9286416)
im=ax.imshow(image,origin='lower',extent=[orig[0],orig[0]+500,orig[1],orig[1]+500],vmin=0,vmax=1.6,cmap='viridis',interpolation='nearest')
ax.contour((flags&1)!=0,levels=[0.5],colors='white',linewidths=.15,origin='lower',extent=[orig[0],orig[0]+500,orig[1],orig[1]+500])
points=[F[i] for i in sorted(F)]; xx=[float(r['x_m']) for r in points]; yy=[float(r['y_m']) for r in points]; vv=[float(r['Su_obs']) for r in points]
sc=ax.scatter(xx,yy,c=vv,vmin=0,vmax=2,cmap='coolwarm',edgecolors='black',linewidths=.25,s=22)
for i in [50,74]: ax.text(float(F[i]['x_m'])+3,float(F[i]['y_m'])+3,str(i),color='red',fontsize=10,weight='bold')
fig.colorbar(im,ax=ax,label='B2s Su/Uref (fluid cells)');fig.colorbar(sc,ax=ax,label='Probe Su/observed W')
ax.set(xlabel='Global x (m)',ylabel='Global y (m)',title='B2s z=2 m true scalar speed and 80 observed probes');fig.tight_layout();fig.savefig(OUT/'B2s_plane_z2_Su_map.png',dpi=150);plt.close(fig)
print(json.dumps({'summary':summary,'map':str(OUT/'B2s_plane_z2_Su_map.png')},indent=2))
