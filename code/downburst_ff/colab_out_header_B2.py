from pathlib import Path
p=Path('/content/a3_b2_1014/gate_runs/gate16_s112_FB_attempt3/NREL-5MW.out')
for i,line in enumerate(p.open()):
 print(i,repr(line[:500]))
 if i>=9:break
