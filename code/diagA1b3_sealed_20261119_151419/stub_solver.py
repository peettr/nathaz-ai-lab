#!/usr/bin/env python3
"""Fixture only. Produces synthetic ledger solely for orchestration testing."""
import csv,os,pathlib
if os.getenv('LUW_COMPILE_ONLY'):
 print('T15 COMPILE_ONLY PASS fixture');raise SystemExit(0)
p=pathlib.Path(os.environ['T17_LEDGER_CSV']);steps=int(os.environ['T17_DIAGNOSTIC_STEPS']);force=1.98624260355e-7
print('T17 force_per_volume_lattice=0.000000198624 half_turnover_steps=8975.0')
print('NVIDIA A100 fixture STUB NOT HARDWARE')
with p.open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['step','mass_fluid_lattice','px_fluid_lattice','ground_drag_snapshot','eligible_native_columns','ground_drag_integral_10','ground_drag_integral_50'])
 for s in list(range(101))+list(range(110,steps+1,10)):
  w.writerow([s,2097152,1000,0,32768,0,0])

with pathlib.Path(os.environ["T17_LAYER_CSV"]).open("w",newline="") as f:
 w=csv.writer(f);w.writerow(["step","z","px_lattice","mass_lattice"])
 for s in list(range(101))+list(range(110,steps+1,10)):
  for z in range(1,65):w.writerow([s,z,0,32768])
