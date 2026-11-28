#!/usr/bin/env python3
"""Prepare a NEW, isolated 10s 5MW controller ABI pilot, not a load test."""
from pathlib import Path
import shutil
import re

base = Path('./lab_a3')
src = base/'run_nrel5mw_rosco_14ms_v2_60s'
repo = base/'downburst_ff/LidarAssistedControl'
upstream = base/'downburst_ff/rosco_2_6_upstream/Test_Cases/NREL-5MW'
out = base/'downburst_ff/pilot_chain10_v4'
if out.exists():
    raise SystemExit(f'Refusing to overwrite {out}')
shutil.copytree(src,out,ignore=shutil.ignore_patterns('*.out','*.outb','*.sum','*.dbg','*.ech'))
shutil.copy2(upstream/'DISCON.IN',out/'ROSCO26.IN')
cfg=(out/'ROSCO26.IN'); s=cfg.read_text(); key='!------- External Controller Interface'; assert s.count(key)==1; cfg.write_text(s.replace(key,'!------- Lidar-Assisted Control ------------\n1 ! FlagLAC - enabled for chain pilot\n\n'+key))
shutil.copy2(upstream/'Cp_Ct_Cq.NREL5MW.txt',out/'Cp_Ct_Cq.NREL5MW.txt')
fn=out/'NREL-5MW.fst'; txt=fn.read_text(); txt=re.sub(r'^\s*60\s+TMax', '        10   TMax',txt, count=1,flags=re.M); fn.write_text(txt)
servo=out/'NRELOffshrBsline5MW_Onshore_ServoDyn.dat'; txt=servo.read_text(); txt=re.sub(r'^.*\bDLL_FileName\b.*$',f'"{base}/downburst_ff/build_WRAPPER/libWRAPPER.so" DLL_FileName - Linux LAC wrapper pilot',txt, count=1,flags=re.M); txt=re.sub(r'^.*\bDLL_InFile\b.*$', '"DISCON.IN" DLL_InFile - local wrapper input',txt, count=1,flags=re.M); servo.write_text(txt)
(out/'DISCON.IN').write_text('! Master wrapper input\n! Three header lines required\n! local chain\n3 ! NumberOfSubDLLs\n"'+str(base/'downburst_ff/build_LDP_v1/libLDP_v1.so')+'" ! SubDLLName\n"LDP.IN" ! SubDLLInputName\n"'+str(base/'downburst_ff/build_FFP_v1/libFFP_v1.so')+'" ! SubDLLName\n"FFP.IN" ! SubDLLInputName\n"'+str(base/'downburst_ff/build_ROSCO/libdiscon.so')+'" ! SubDLLName\n"ROSCO26.IN" ! SubDLLInputName\n')
shutil.copy2(repo/'Release/IEA-15-240-RWT-Monopile/LDP_v1_CircularCW.IN',out/'LDP.IN')
shutil.copy2(repo/'Release/IEA15MW_02/FFP_v1.IN',out/'FFP.IN')
inflow=out/'NRELOffshrBsline5MW_InflowWind.dat'; s=inflow.read_text(); s=re.sub(r'^\s*0\s+SensorType\b','1 SensorType',s,flags=re.M); s=re.sub(r'^\s*0\s+NumBeam\b','1 NumBeam',s,flags=re.M); inflow.write_text(s)
print(out)
