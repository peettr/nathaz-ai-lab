"""600s IEC NTM TurbSim Kaimal gate on Colab CPU, NREL 5 MW."""
import json,os,sys,shutil,subprocess,time,math,traceback,struct
from pathlib import Path
import numpy as np
P=Path('/content/a3_b2_1014'); B=P/'a3_b_1014';sys.path.insert(0,str(B/'code'))
import segment_b_run as b,segment_a_run as a
from analyze_segment_b import read_out

def gate_read_out(path):
 with path.open() as f:
  for _ in range(6):next(f)
  names=next(f).split()
 selected=[k for k in ('Time','RotSpeed','GenSpeed','TwrBsMyt','BldPitch1') if k in names]
 d=np.loadtxt(path,skiprows=8,usecols=[names.index(k) for k in selected],ndmin=2)
 return dict(zip(selected,d.T))
b.BASE=B/'base';b.ROOT=P/'gate_runs';b.SRC=B/'base/ff_smoke_feedback';b.FAST=P/'bin/openfast';b.LIB=P/'rosco210_ff_build_rate_B2/libdiscon.so';a.CURVE=B/'base/segment_a_v4_curve.txt'
b.ROOT.mkdir(exist_ok=True)

def filter_signal(x,dt=.5,fc=.10):
 y=np.empty_like(x);y[0]=x[0];c=1-np.exp(-2*np.pi*fc*dt)
 for i in range(1,len(x)):y[i]=y[i-1]+c*(x[i]-y[i-1])
 return y

def run_one(seed,group):
 key=f'gate16_s{seed}_{group}';dest=b.ROOT/key
 # A completed preflight solver result is reused read-only, never overwritten.
 prior=b.ROOT/'gate16_s112_FB_attempt3/NREL-5MW.out'
 if seed==112 and group=='FB' and prior.exists():
  d=gate_read_out(prior)
  result={'seed':seed,'group':group,'rc':0,'wall_s':None,'source':'TurbSim IEC Kaimal NTM A 16 m/s; reused completed first solver'}
  for k in ('RotSpeed','GenSpeed','TwrBsMyt','BldPitch1'):
   if k in d:result[k+'_std']=float(np.std(d[k]));result[k+'_max']=float(np.max(d[k]));result[k+'_min']=float(np.min(d[k]))
  with (P/'gate_metrics.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
  print('GATE_CASE_REUSE',result,flush=True)
  return result
 if dest.exists():
  dest=b.ROOT/(key+'_attempt2')
  if dest.exists():dest=b.ROOT/(key+'_attempt3')
  if dest.exists():raise RuntimeError('refuse overwrite '+str(dest))
 shutil.copytree(b.SRC,dest,ignore=shutil.ignore_patterns('*.out','*.outb','*.sum','*.dbg','*.ech','*.log','*.wnd','preview.txt'))
 # One immutable TurbSim realization per seed, reused across FB/FF.
 windroot=b.ROOT/f'turb16_s{seed}';windroot.mkdir(exist_ok=True)
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
  with (windroot/'turbsim.log').open('w') as f: ts=subprocess.run([str(P/'bin/turbsim'),str(inp)],cwd=windroot,stdout=f,stderr=subprocess.STDOUT,timeout=600)
  if ts.returncode:raise RuntimeError('TurbSim failed '+(windroot/'turbsim.log').read_text()[-2500:])
 rawbytes=fieldfile.read_bytes(); ident,nz,ny,ntwr,nt=struct.unpack('<h4l',rawbytes[:18]); info=struct.unpack('<l',rawbytes[66:70])[0]; off=70+info; frame=2*(3*ny*nz+3*ntwr)
 assert ident in (7,8) and ntwr==0 and len(rawbytes)==off+nt*frame
 # Preserve TurbSim v5 BTS ID=8; prepend 7s frames for measured InflowWind lookup.
 with (dest/'wind.bts').open('wb') as f:
  f.write(struct.pack('<h4l',ident,nz,ny,ntwr,nt+14));f.write(rawbytes[18:off]);f.write(rawbytes[off:off+frame]*14);f.write(rawbytes[off:])
 # Decode official TurbSim binary frames for an ideal future rotor-disk proxy.
 rawbytes=fieldfile.read_bytes();ident,nz,ny,ntwr,nt=struct.unpack('<h4l',rawbytes[:18]);assert ident in (7,8) and (ny,nz)==(7,7)
 dt=struct.unpack('<f',rawbytes[26:30])[0]
 scales=struct.unpack('<6f',rawbytes[42:66]);off=70+struct.unpack('<l',rawbytes[66:70])[0]
 ints=np.frombuffer(rawbytes,dtype='<i2',offset=off,count=nt*3*ny*nz).reshape((nt,3,ny,nz),order='C')
 # Each frame is Fortran component,y,z packed; reshape explicitly.
 u=np.empty((nt,ny,nz))
 for j in range(nt):u[j]=(np.frombuffer(rawbytes,dtype='<i2',count=3*ny*nz,offset=off+j*6*ny*nz).reshape((3,ny,nz),order='F')[0]-scales[1])/scales[0]
 y=np.linspace(-84,84,ny);z=np.linspace(6,174,nz);yy,zz2=np.meshgrid(y,z,indexing='ij');mask=(yy**2+(zz2-90)**2)<=63**2
 rotor=u[:,mask].mean(axis=1);t=np.arange(nt)*dt;lead=6.;tf=1/(2*np.pi*.1);buffer=max(0.,lead-tf-.22-.5)
 future=np.interp(t+lead,t,rotor,right=rotor[-1]);filtered=filter_signal(future,dt=dt);sig=np.interp(t-buffer,t,filtered,left=filtered[0])
 with (dest/'preview.txt').open('w') as f:
  f.write('# absolute simulator time [s], ideal preview m/s\n')
  for ti,ui in zip(t,sig):f.write(f'{ti:.3f} {ui:.6f}\n')
 a.replace_key(dest/'NREL-5MW.fst','TMax','600.0');a.replace_key(dest/'NREL-5MW.fst','TStart','100.0');a.replace_key(dest/'NREL-5MW.fst','OutFileFmt','1')
 sd=dest/'NRELOffshrBsline5MW_Onshore_ServoDyn.dat';a.replace_key(sd,'DLL_FileName',f'"{b.LIB}"')
 inflow=dest/'NRELOffshrBsline5MW_InflowWind.dat';a.replace_key(inflow,'WindType','3');a.replace_key(inflow,'FileName_BTS','"wind.bts"')
 cfg=dest/'DISCON.IN';a.replace_discon(cfg,'SD_Mode','0')
 for k,v in [('PC_MaxRat',math.radians(8)),('PC_MinRat',-math.radians(8))]:a.replace_discon(cfg,k,f'{v:.10f}')
 env=os.environ.copy();env.update(ROSCO_FF_FILE=str(dest/'preview.txt'),ROSCO_FF_CURVE=str(a.CURVE),ROSCO_FF_GAIN_DEG_PER_MS='1' if group=='FF' else '0')
 start=time.monotonic()
 with (dest/'openfast.log').open('w') as f:
  try:rc=subprocess.run([str(b.FAST),'NREL-5MW.fst'],cwd=dest,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1500).returncode
  except subprocess.TimeoutExpired:rc=-999
 result={'seed':seed,'group':group,'rc':rc,'wall_s':time.monotonic()-start,'source':'TurbSim 5.0.0 IEC 61400-1 Kaimal NTM A 16 m/s, 7x7, 0.5 s; ideal future disk-mean from same BTS','wind_mean':float(np.mean(rotor))}
 if rc==0:
  d=gate_read_out(dest/'NREL-5MW.out');print('channels',list(d)[:40],flush=True)
  for k in ('RotSpeed','GenSpeed','TwrBsMyt','BldPitch1'):
   if k in d:result[k+'_std']=float(np.std(d[k]));result[k+'_max']=float(np.max(d[k]));result[k+'_min']=float(np.min(d[k]))
 else:result['log_tail']=(dest/'openfast.log').read_text(errors='replace')[-2000:]
 out=P/'gate_metrics.jsonl'
 with out.open('a') as f:f.write(json.dumps(result)+'\n')
 print('GATE_CASE',result,flush=True)
 return result

if __name__=='__main__':
 for seed in (112,203,317):
  vals=[run_one(seed,g) for g in ('FB','FF')]
  if any(x['rc']!=0 for x in vals):break
  print('PAIR',seed,'rot-speed std ratio',vals[1]['RotSpeed_std']/vals[0]['RotSpeed_std'],flush=True)
 print('GATE_DONE',flush=True)
