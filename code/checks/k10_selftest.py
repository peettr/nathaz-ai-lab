"""K10: the L1 checker must pass known-good runs and block known-bad copies.
Usage: python k10_selftest.py <good_A_dir> <good_B_dir>
Bad copies: A with air viscosity 1.7894e-5 in the audit and cd x3; B with criterion 1e-3 and residual rows above 1e-5.
"""
import json, re, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from l1_check import check

goodA, goodB = Path(sys.argv[1]), Path(sys.argv[2])
tmp = Path(tempfile.mkdtemp())
res = {}
res['good_A'] = check(goodA, 'A')
res['good_B'] = check(goodB, 'B')
bA = tmp / 'bad_A'; shutil.copytree(goodA, bA)
log = (bA / 'run.log').read_text()
log = log.replace("'air_viscosity': 4.545454545454545e-05", "'air_viscosity': 1.7894e-05")
(bA / 'run.log').write_text(log)
cd = (bA / 'out' / 'cd.out').read_text().splitlines()
out = []
for line in cd:
    parts = line.split()
    try:
        nums = [float(x) for x in parts]
        out.append(f"{parts[0]} {nums[1]*3}")
    except (ValueError, IndexError):
        out.append(line)
(bA / 'out' / 'cd.out').write_text('\n'.join(out) + '\n')
res['bad_A'] = check(bA, 'A')
bB = tmp / 'bad_B'; shutil.copytree(goodB, bB)
log = (bB / 'run.log').read_text().replace("'absolute_criteria': 1e-05", "'absolute_criteria': 0.001")
log = re.sub(r'(?m)^(\s*\d+\s+)([0-9.]+e-0[6-9])', lambda m: m.group(1) + '5.0000e-04', log)
(bB / 'run.log').write_text(log)
res['bad_B'] = check(bB, 'B')
ok = (res['good_A']['l1'] == 'pass' and res['good_B']['l1'] == 'pass' and
      res['bad_A']['l1'] == 'block' and res['bad_B']['l1'] == 'block' and res['bad_A']['l2'] == 'block')
src = (Path(__file__).resolve().parent / 'l1_check.py').read_text()
const = re.findall(r'return\s+(True|\'pass\'|"pass")\s*$', src, re.M)  # a checker that can only say yes
print(json.dumps({k: {'l1': v['l1'], 'l2': v['l2'], 'failed': v['l1_failed']} for k, v in res.items()}, indent=1))
print('constant_returns', const)
print('K10', 'PASS' if ok and not const else 'FAIL')
