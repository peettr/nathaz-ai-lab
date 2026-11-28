#!/usr/bin/env python3
"""Per-2T cold-start diagnostics from sealed native T17 producer; descriptive only."""
import csv,hashlib,json,math,pathlib,sys,os
import numpy as np
NX=int(os.environ.get('T17_TEST_NX',512));NY=int(os.environ.get('T17_TEST_NY',256));AREA=NX*NY
F,H=.00120843,64.

def analyze(d,w,final=False):
 d=pathlib.Path(d);timing=list(csv.DictReader((d/'timing.csv').open()))[0]
 T=int(timing.get('step_T') or 2*int(timing['half_T_steps']));stride=int(timing['sample_stride']);unit=float(timing['velocity_si_per_lattice'])
 lo=(w-1)*2*T;hi=w*2*T;duration=hi-lo
 rows=list(csv.DictReader((d/'ledger.csv').open()))
 ledger=[{k:float(v) for k,v in r.items()} for r in rows if lo<=float(r['step'])<=hi]
 if len(ledger)<3 or ledger[-1]['step']<hi:raise ValueError('ledger incomplete')
 def integral(step):
  for a,b in zip(ledger,ledger[1:]):
   if a['step']<=step<=b['step']:
    q=(step-a['step'])/(b['step']-a['step']);return a['ground_drag_integral_lattice']*(1-q)+b['ground_drag_integral_lattice']*q
  raise ValueError('integral endpoint missing')
 drag=(integral(hi)-integral(lo))/duration
 rho=np.mean([r['rho_mean_lattice'] for r in ledger])
 tau=drag/AREA*unit**2*rho
 ustar=(tau/rho)**.5 if tau>0 and rho>0 else float('nan')
 # Frames are appended in absolute step order. Consume only a fully flushed window.
 framebytes=2*AREA*3*4
 steps=range(stride,hi+1,stride)
 start=(lo//stride);stop=(hi//stride)
 if (d/'planes.bin').stat().st_size < stop*framebytes:raise ValueError('planes incomplete')
 planes=np.memmap(d/'planes.bin',dtype='<f4',mode='r',shape=(stop,2,NY,NX,3))
 raw=np.asarray(planes[start:stop],dtype=np.float64)
 p3,p10=raw[:,0],raw[:,1]
 if len(p10)<4:raise ValueError('too few frames')
 fl=p10-p10.mean(axis=(0,1,2));var=(fl*fl).mean(axis=(0,1,2));k=float(var.sum()/2)
 x=fl[...,0];den=float((x*x).mean());
 if den<=0:raise ValueError('zero variance')
 corr=lambda axis,n:float((x*np.roll(x,n,axis=axis)).mean()/den)
 rx,ry=corr(2,NX//2),corr(1,NY//2)
 prof=[{k:float(v) for k,v in r.items()} for r in csv.DictReader((d/'profiles.csv').open()) if lo<float(r['step'])<=hi]
 byk={int(k):[] for k in range(1,65)}
 for r in prof:byk[int(r['k'])].append(r['u_x_mean_si'])
 if any(not z for z in byk.values()):raise ValueError('incomplete profile')
 mean={k:sum(z)/len(z) for k,z in byk.items()}
 uref=.27810/.4*math.log((2.5+.024)/.024)
 e=mean[3]/uref-1
 es=[mean[j]/(.27810/.4*math.log((j-.5+.024)/.024))-1 for j in range(3,11)]
 s3=max(abs(.4*z/.27810*(mean[z+1]-mean[z])-z/(z+.024)) for z in range(3,10))
 result={'window':w,'T_range':[2*(w-1),2*w],'step_range':[lo,hi],
 'V1_ratio':tau/rho/(F*H),'tau_x_time_mean':tau,'rho':float(rho),
 'Px_begin':ledger[0]['px_lattice'],'Px_end':ledger[-1]['px_lattice'],'Px_mean':float(np.mean([r['px_lattice'] for r in ledger])),
 'k_res_z9p5':k,'k_res_over_ustar_sq':k/(.27810**2),'e_2p5':e,'S2b_rms':float(np.sqrt(np.mean(np.square(es)))),'S3_max_abs_difference':s3,
 'R_uu_x_half':rx,'R_uu_y_half':ry,'frames':len(p10),'u_star':ustar,
 'U_profile_si_mps':{str(j):mean[j] for j in range(1,65)}}
 if not all(math.isfinite(v) for v in result.values() if isinstance(v,float)):raise ValueError('nonfinite')
 if final:
  result['correlation_curve']={'x_m':{str(j):corr(2,j) for j in range(0,NX//2+1,16)},
                               'y_m':{str(j):corr(1,j) for j in range(0,NY//2+1,16)}}
  result['correlation_marks_m']=[32,64,96,128]
 return result

def main():
 d=pathlib.Path(sys.argv[1]); w=int(sys.argv[2]);out=d.parent/('window_%02d.json'%w)
 v=analyze(d,w,w>=10);out.write_text(json.dumps(v,allow_nan=False,indent=2)+'\n')
 h=hashlib.sha256(out.read_bytes()).hexdigest();(out.parent/(out.name+'.sha256')).write_text(h+'\n')
 print('WINDOW_READY',w,out.name,h,flush=True)
if __name__=='__main__':main()
