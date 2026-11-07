"""Colab-only timing diagnostic derived from immutable B2 gate protocol."""
from pathlib import Path
import json, os, sys, shutil, subprocess, time, math, struct
import numpy as np
P=Path('/content/a3_b3_1015'); B=P/'a3_b_1014'; sys.path.insert(0,str(B/'code'))
import segment_b_run as b, segment_a_run as a
b.BASE=B/'base';b.ROOT=P/'scan_runs';b.SRC=B/'base/ff_smoke_feedback';b.FAST=P/'bin/openfast';b.LIB=P/'rosco210_ff_build_rate_B2/libdiscon.so';a.CURVE=B/'base/segment_a_v4_curve.txt'
b.ROOT.mkdir(exist_ok=True)
def lpf(x,dt,fc=.10):
 y=np.empty_like(x);y[0]=x[0];c=1-np.exp(-2*np.pi*fc*dt)
 for i in range(1,len(x)):y[i]=y[i-1]+c*(x[i]-y[i-1])
 return y
def out_std(path):
 with path.open() as f:
  for _ in range(6):next(f)
  names=next(f).split()
 d=np.loadtxt(path,skiprows=8,usecols=[names.index('RotSpeed')],ndmin=1)
 return float(np.std(d))
def run(seed,delta,gain):
 key=f's{seed}_d{delta:+d}_g{gain:.1f}'.replace('+','p').replace('-','m'); dest=b.ROOT/key
 assert not dest.exists(), 'refuse overwrite '+str(dest)
 shutil.copytree(b.SRC,dest,ignore=shutil.ignore_patterns('*.out','*.outb','*.sum','*.dbg','*.ech','*.log','*.wnd','preview.txt'))
 windroot=P/f'turb16_s{seed}';windroot.mkdir(exist_ok=True)
 inp=windroot/'TurbSim.inp'; raw=(P/'TurbSim_template_B2.inp').read_text()
 changes={'RandSeed1':str(seed),'NumGrid_Z':'7','NumGrid_Y':'7','TimeStep':'0.5','AnalysisTime':'660','UsableTime':'"ALL"','HubHt':'90','GridHeight':'168','GridWidth':'168','TurbModel':'"IECKAI"','IECturbc':'"A"','IEC_WindType':'"NTM"','URef':'16','WrADFF':'True'}
 lines=[]
 for line in raw.splitlines():
  parts=line.split()
  if len(parts)>1 and parts[1] in changes:line=changes[parts[1]]+'   '+line[line.find(parts[1]):]
  lines.append(line)
 if not inp.exists():inp.write_text('\n'.join(lines)+'\n')
 fieldfile=windroot/'TurbSim.bts'
 if not fieldfile.exists():
  with (windroot/'turbsim.log').open('w') as f:r=subprocess.run([str(P/'bin/turbsim'),str(inp)],cwd=windroot,stdout=f,stderr=subprocess.STDOUT,timeout=600)
  assert r.returncode==0,(windroot/'turbsim.log').read_text()[-1500:]
 rawbytes=fieldfile.read_bytes();ident,nz,ny,ntwr,nt=struct.unpack('<h4l',rawbytes[:18]); info=struct.unpack('<l',rawbytes[66:70])[0];off=70+info;frame=2*(3*ny*nz+3*ntwr)
 assert ident in (7,8) and ntwr==0 and len(rawbytes)==off+nt*frame
 with (dest/'wind.bts').open('wb') as f:
  f.write(struct.pack('<h4l',ident,nz,ny,ntwr,nt+14));f.write(rawbytes[18:off]);f.write(rawbytes[off:off+frame]*14);f.write(rawbytes[off:])
 dt=struct.unpack('<f',rawbytes[26:30])[0];scales=struct.unpack('<6f',rawbytes[42:66]);u=np.empty((nt,ny,nz))
 for j in range(nt):u[j]=(np.frombuffer(rawbytes,dtype='<i2',count=3*ny*nz,offset=off+j*6*ny*nz).reshape((3,ny,nz),order='F')[0]-scales[1])/scales[0]
 yy,zz=np.meshgrid(np.linspace(-84,84,ny),np.linspace(6,174,nz),indexing='ij');rotor=u[:,(yy**2+(zz-90)**2)<=63**2].mean(axis=1)
 t=np.arange(nt)*dt;lead=6.;buffer=max(0.,lead-1/(2*np.pi*.1)-.22-.5)
 future=np.interp(t+lead,t,rotor,right=rotor[-1]);filtered=lpf(future,dt);sig=np.interp(t-buffer+delta,t,filtered,left=filtered[0],right=filtered[-1])
 with (dest/'preview.txt').open('w') as f:
  f.write('# simulator absolute time [s], preview [m/s]\n')
  for ti,ui in zip(t,sig):f.write(f'{ti:.3f} {ui:.6f}\n')
 a.replace_key(dest/'NREL-5MW.fst','TMax','600.0');a.replace_key(dest/'NREL-5MW.fst','TStart','100.0');a.replace_key(dest/'NREL-5MW.fst','OutFileFmt','1')
 a.replace_key(dest/'NRELOffshrBsline5MW_Onshore_ServoDyn.dat','DLL_FileName',f'"{b.LIB}"')
 inflow=dest/'NRELOffshrBsline5MW_InflowWind.dat';a.replace_key(inflow,'WindType','3');a.replace_key(inflow,'FileName_BTS','"wind.bts"')
 a.replace_discon(dest/'DISCON.IN','SD_Mode','0')
 for k,v in [('PC_MaxRat',math.radians(8)),('PC_MinRat',-math.radians(8))]:a.replace_discon(dest/'DISCON.IN',k,f'{v:.10f}')
 env=os.environ.copy();env.update(ROSCO_FF_FILE=str(dest/'preview.txt'),ROSCO_FF_CURVE=str(a.CURVE),ROSCO_FF_GAIN_DEG_PER_MS=str(gain))
 start=time.monotonic()
 with (dest/'openfast.log').open('w') as f:
  try:rc=subprocess.run([str(b.FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1500).returncode
  except subprocess.TimeoutExpired:rc=-999
 result=dict(seed=seed,delta_s=delta,gain=gain,rc=rc,wall_s=round(time.monotonic()-start,2),protocol='B2 16m/s NTM-A 600s, std 100–600s, 7x7, 0.5s, BTS prepend 7s; shift positive = preview moved earlier')
 if rc==0:result['RotSpeed_std_rpm']=out_std(dest/'NREL-5MW.out')
 else:result['log_tail']=(dest/'openfast.log').read_text(errors='replace')[-1200:]
 with (P/'timing_metrics.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
 print('SCAN_CASE',json.dumps(result),flush=True)
 return result
if __name__=='__main__':
 for d,g in [(d,1.) for d in (-6,-4,-2,0,2,4,6)]+[(0,.5)]:
  x=run(112,d,g)
  if x['rc']:break
 print('SCAN_DONE',flush=True)
