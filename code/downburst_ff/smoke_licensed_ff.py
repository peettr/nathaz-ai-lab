#!/usr/bin/env python3
"""Create independent, no-overwrite licensed ROSCO FF ABI checks."""
from pathlib import Path
import shutil,re
b=Path('./lab_a3')
src=b/'run_nrel5mw_rosco_14ms_v2_60s'
for label in ('feedback','feedforward'):
    out=b/'downburst_ff'/f'ff_smoke_{label}'
    if out.exists(): raise SystemExit(f'refuse overwrite {out}')
    shutil.copytree(src,out,ignore=shutil.ignore_patterns('*.out','*.outb','*.sum','*.dbg','*.ech','*.log'))
    fst=out/'NREL-5MW.fst'; text=fst.read_text(); text,n=re.subn(r'^\s*60\s+TMax', '        30   TMax',text,count=1,flags=re.M); assert n==1; fst.write_text(text)
    servo=out/'NRELOffshrBsline5MW_Onshore_ServoDyn.dat'; text=servo.read_text(); text,n=re.subn(r'^.*\bDLL_FileName\b.*$',f'"{b}/downburst_ff/rosco210_ff_build/libdiscon.so" DLL_FileName - A3 licensed local FF',text,count=1,flags=re.M); assert n==1; servo.write_text(text)
    cfg=out/'DISCON.IN'; text=cfg.read_text(); text,n=re.subn(r'^.*! PC_MaxRat\b.*$', '0.13962634 ! PC_MaxRat - 8 deg/s A3',text,count=1,flags=re.M); assert n==1; text,n=re.subn(r'^.*! PC_MinRat\b.*$', '-0.13962634 ! PC_MinRat - -8 deg/s A3',text,count=1,flags=re.M); assert n==1; cfg.write_text(text)
    # Preview input is artificially perturbed while rotor inflow remains 14 m/s:
    # ABI test only, not a real lidar/downburst scenario.
    (out/'preview.txt').write_text('# arrival time[s]  preview_wind[m/s]\n0 14\n9 14\n10 18\n17 18\n18 14\n30 14\n')
    print(out)
