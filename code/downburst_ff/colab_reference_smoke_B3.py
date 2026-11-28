"""Probe Task52 wrapper with OpenFAST5 InflowWind Lidar on Colab."""
from pathlib import Path
import tarfile,shutil,subprocess,sys,math,json,time
P=Path('/content/a3_b3_1015'); B=P/'a3_b_1014';sys.path.insert(0,str(B/'code'))
import segment_a_run as a
D=P/'refchain'
if not D.exists():
 D.mkdir()
 with tarfile.open('/content/refchain_B3.tar.gz') as f:f.extractall(D,filter='data')
for name in ('libWRAPPER.so','libLDP_v1.so','libFFP_v1.so','libROSCO26.so'):(D/name).chmod(0o755)
# Inspect modern InflowWind channels and test ABI in the shortest possible run.
source=B/'base/ff_smoke_feedback';run=P/'reference_smoke_s112_curve22';shutil.copytree(source,run,ignore=shutil.ignore_patterns('*.out','*.outb','*.sum','*.dbg','*.ech','*.log','*.wnd','preview.txt'))
wind=P/'scan_runs/s112_dm6_g1.0/wind.bts'
assert wind.exists(), 'wind missing; wait for first timing case'
shutil.copyfile(wind,run/'wind.bts')
a.replace_key(run/'NREL-5MW.fst','TMax','20.0');a.replace_key(run/'NREL-5MW.fst','TStart','0.0');a.replace_key(run/'NREL-5MW.fst','OutFileFmt','1')
q=run/'NRELOffshrBsline5MW_Onshore_ServoDyn.dat';a.replace_key(q,'DLL_FileName',f'"{D}/libWRAPPER.so"');a.replace_key(q,'DLL_InFile','"DISCON.IN"')
q=run/'NRELOffshrBsline5MW_InflowWind.dat';a.replace_key(q,'WindType','3');a.replace_key(q,'FileName_BTS','"wind.bts"');a.replace_key(q,'SensorType','1');a.replace_key(q,'NumBeam','1');a.replace_key(q,'FocalDistanceX','-96');a.replace_key(q,'URefLid','16');a.replace_key(q,'MeasurementInterval','0.5')
# Absolute library and parameter paths: wrapper passes paths to sub-DLLs.
shutil.copyfile(D/'LDP_v1.IN',run/'LDP_v1.IN')
(run/'DISCON.IN').write_text('\n'.join(['! Master wrapper','! 3 header lines','! test task52 lidar', '3 ! NumberOfSubDLLs',f'"{D}/libLDP_v1.so" ! SubDLLName','"LDP_v1.IN" ! SubDLLInputName',f'"{D}/libFFP_v1.so" ! SubDLLName','"FFP5MW.IN" ! SubDLLInputName',f'"{D}/libROSCO26.so" ! SubDLLName','"ROSCO26.IN" ! SubDLLInputName'])+'\n')
# Static pitch from NREL 5MW: local curve in degrees -> radians.
import numpy as np
v0=np.loadtxt(B/'base/segment_a_v4_curve.txt',comments='#');assert v0.shape[1]>=2,v0.shape
v=v0[np.unique(np.r_[np.arange(0,17,2),np.arange(18,36,3),np.arange(36,len(v0),11),len(v0)-1])]
# preserve author FFP syntax, updating only curve and filter cut-off (rad/s).
s=(D/'FFP_v1.IN').read_text().splitlines();assert len(s)==11
s[3]='1 ! FlagLPF';s[4]=f'{2*math.pi*.1:.9f} ! f_cutoff [rad/s]';s[5]='3.7 ! T_buffer (6-1/2pi/.1-.22-.5)'
s[8]=f'{len(v)} ! n_StaticPitchCurve';s[9]=' '.join(f'{x:.6f}' for x in v[:,0])+' ! StaticWind m/s';s[10]=' '.join(f'{math.radians(x):.8f}' for x in v[:,1])+' ! StaticPitch rad'
(run/'FFP5MW.IN').write_text('\n'.join(s)+'\n')
s=(D/'ROSCO26.IN').read_text();s=s.replace('0 ! FlagLAC - disabled for ABI-only pilot','1 ! FlagLAC - author rate feedforward');(run/'ROSCO26.IN').write_text(s)
with (run/'openfast.log').open('w') as f:
 try:r=subprocess.run([str(P/'bin/openfast'),'NREL-5MW.fst'],cwd=run,stdout=f,stderr=subprocess.STDOUT,timeout=120)
 except subprocess.TimeoutExpired:r=type('R',(),{'returncode':-999})()
msg={'rc':r.returncode,'log_tail':(run/'openfast.log').read_text(errors='replace')[-3500:],'curve_rows':len(v),'case':'Task52 3-DLL short compatibility test, NREL5MW OpenFAST5, same BTS seed112'}
(P/'reference_smoke_curve22.json').write_text(json.dumps(msg,indent=2));print('REFERENCE_SMOKE',json.dumps(msg),flush=True)
