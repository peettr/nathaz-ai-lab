"""Task52 author-chain NTM gate, 600s, 3 matched seeds, Colab only."""
from pathlib import Path
import sys,math,struct,shutil,subprocess,json,time
import numpy as np
P=Path('/content/a3_b3_1015');B=P/'a3_b_1014';sys.path.insert(0,str(B/'code'))
import segment_a_run as a
R=P/'reference_runs_v2';R.mkdir(exist_ok=True)
def wind(seed):
 old=P/'scan_runs/s112_dm6_g1.0/wind.bts'
 if seed==112:return old
 wr=P/f'ref_turb16_s{seed}';wr.mkdir(exist_ok=True);inp=wr/'TurbSim.inp';raw=(P/'TurbSim_template_B2.inp').read_text()
 changes={'RandSeed1':str(seed),'NumGrid_Z':'7','NumGrid_Y':'7','TimeStep':'0.5','AnalysisTime':'660','UsableTime':'"ALL"','HubHt':'90','GridHeight':'168','GridWidth':'168','TurbModel':'"IECKAI"','IECturbc':'"A"','IEC_WindType':'"NTM"','URef':'16','WrADFF':'True'}
 lines=[]
 for line in raw.splitlines():
  parts=line.split()
  if len(parts)>1 and parts[1] in changes:line=changes[parts[1]]+'   '+line[line.find(parts[1]):]
  lines.append(line)
 if not inp.exists():inp.write_text('\n'.join(lines)+'\n')
 original=wr/'TurbSim.bts'
 if not original.exists():
  with (wr/'turbsim.log').open('w') as f:rc=subprocess.run([str(P/'bin/turbsim'),str(inp)],cwd=wr,stdout=f,stderr=subprocess.STDOUT,timeout=600).returncode
  assert rc==0,(wr/'turbsim.log').read_text()[-1000:]
 target=wr/'wind.bts';data=original.read_bytes();ident,nz,ny,ntwr,nt=struct.unpack('<h4l',data[:18]);info=struct.unpack('<l',data[66:70])[0];off=70+info;frame=2*(3*ny*nz+3*ntwr)
 assert ident in (7,8) and ntwr==0 and len(data)==off+nt*frame
 if not target.exists():
  with target.open('wb') as f:f.write(struct.pack('<h4l',ident,nz,ny,ntwr,nt+14));f.write(data[18:off]);f.write(data[off:off+frame]*14);f.write(data[off:])
 return target
def std(path):
 with path.open() as f:
  for _ in range(6):next(f)
  names=next(f).split()
 d=np.loadtxt(path,skiprows=8,usecols=[names.index('RotSpeed')],ndmin=1)
 return float(np.std(d))
def run(seed,group):
 dst=R/f's{seed}_{group}';assert not dst.exists(),dst
 src=P/'reference_smoke_s112_bridge';shutil.copytree(src,dst,ignore=shutil.ignore_patterns('*.out','*.outb','*.sum','*.dbg','*.ech','*.log','*.bts'))
 shutil.copyfile(wind(seed),dst/'wind.bts')
 a.replace_key(dst/'NREL-5MW.fst','TMax','600.0');a.replace_key(dst/'NREL-5MW.fst','TStart','100.0')
 txt=(dst/'ROSCO26.IN').read_text(); assert '1 ! FlagLAC - author rate feedforward' in txt
 if group=='FB':(dst/'ROSCO26.IN').write_text(txt.replace('1 ! FlagLAC - author rate feedforward','0 ! FlagLAC - feedback'))
 for k,v in [('PC_MaxRat',math.radians(8)),('PC_MinRat',-math.radians(8))]:a.replace_discon(dst/'ROSCO26.IN',k,f'{v:.10f}')
 start=time.monotonic()
 with (dst/'openfast.log').open('w') as f:
  try:rc=subprocess.run([str(P/'bin/openfast'),'NREL-5MW.fst'],cwd=dst,stdout=f,stderr=subprocess.STDOUT,timeout=1500).returncode
  except subprocess.TimeoutExpired:rc=-999
 result={'seed':seed,'group':group,'rc':rc,'wall_s':round(time.monotonic()-start,2),'protocol':'Task52 MIT LDP_v1-FFP_v1-modified ROSCO2.6; bridge OpenFAST5 2005 to legacy 2103; NTM-A 16m/s 600s, std 100–600s'}
 if rc==0:
  result['RotSpeed_std_rpm']=std(dst/'NREL-5MW.out'); d=np.loadtxt(dst/'NREL-5MW.RO.dbg',skiprows=3);result['FF_PitchRate_absmax_rad_s']=float(np.max(np.abs(d[:,25])));result['REWS_range_ms']=[float(np.min(d[:,26])),float(np.max(d[:,26]))]
 else:result['log_tail']=(dst/'openfast.log').read_text(errors='replace')[-1300:]
 with (P/'reference_metrics_v2.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
 print('REF_CASE',json.dumps(result),flush=True)
 return result
if __name__=='__main__':
 for seed in (112,203,317):
  pair=[run(seed,g) for g in ('FB','FF')]
  if any(x['rc'] for x in pair):break
  print('REF_PAIR',seed,'ratio',pair[1]['RotSpeed_std_rpm']/pair[0]['RotSpeed_std_rpm'],flush=True)
 print('REF_DONE',flush=True)
