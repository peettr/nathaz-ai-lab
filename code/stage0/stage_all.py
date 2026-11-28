#!/usr/bin/env python3
"""CRC file-only staging; never runs a solver or submits to scheduler."""
import csv, json, re, shutil, subprocess, sys
from pathlib import Path
BASE=Path('/groups/kareem/[用户]/L22_6')
ROOT0=BASE/'L22_6_v3S0_DBG_01_20261127'
BASECASE=BASE/'L22_6_T03_v12_B0_20261021_02'
CI=BASE/'L22_6_T03_private_CI_v3'
REF=BASE/'L22_6_T03_private_ref_v2/src'
P=Path(__file__).resolve().parent
NUM=r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?'
JOBS=([(g,i) for g,k in [('B0',6),('REF',6),('CI',8),('PSI0',1),('D1',3),('D2',3),('D3',3),('D4',3),('P_CI',3),('P_REF',3),('P_CIminus',3)] for i in range(1,k+1)])
assert len(JOBS)==42

def edit_once(path,old,new):
    text=path.read_text()
    if text.count(old)!=1: raise ValueError(f'{path}: expected exactly one {old!r}; got {text.count(old)}')
    path.write_text(text.replace(old,new))

def d4_adjust(case):
    bd=case/'constant/boundaryData/inlet'
    points=[list(map(float,re.findall(NUM,line))) for line in (bd/'points').read_text().splitlines() if line.lstrip().startswith('(') and len(re.findall(NUM,line))==3]
    rp=bd/'R'; lines=rp.read_text().splitlines(keepends=True)
    indexed=[(i,list(map(float,re.findall(NUM,s)))) for i,s in enumerate(lines) if s.lstrip().startswith('(') and len(re.findall(NUM,s))==6]
    if len(points)!=164 or len(indexed)!=164: raise ValueError('D4 expected 164 points/R')
    for (z,(li,r)) in zip((p[2] for p in points),indexed):
        if z < .9-1e-7: continue
        rho=r[2]/(r[0]*r[5])**.5
        if abs(rho)<.7: continue
        r[2]=r[2]*(.7/abs(rho))
        lines[li]='('+' '.join(f'{v:.12g}' for v in r)+')\n'
    rp.write_text(''.join(lines))

def stage(group,seq):
    tag=f'{group}_{seq:02d}'
    root=BASE/f'L22_6_v3S0_{tag}_20261127'
    if root.exists(): raise FileExistsError(root)
    root.mkdir(mode=0o700)
    kind=('CIminus' if 'CIminus' in group else 'CI' if 'CI' in group or group=='PSI0' else 'REF')
    source={'CI':CI/'CI_fixed_01','CIminus':CI/'CIminus_fixed_01','REF':REF}[kind]
    shutil.copytree(source,root/'src',ignore=shutil.ignore_patterns('linux64*','lnInclude','*.o','*.so','.git','__pycache__'))
    bc='B0' if group=='B0' or group.startswith('D') else 'Veer'
    psi=0 if group=='PSI0' else 45 if group.startswith('P_') else 20
    subprocess.run([sys.executable,str(ROOT0/'prepare_case_v3.py'),str(BASECASE),str(root/'case'),'--bc',bc,'--psi-top',str(psi)],check=True,stdout=subprocess.DEVNULL)
    control=root/'case/system/controlDict'
    if kind=='REF': edit_once(control,'libturbulentInflow.so' if bc=='B0' else 'libturbulentDFMVeerInlet.so','libT03PrivateRef.so')
    if group in ('D1','D2','D3'):
        c=root/'src/turbulentDFMInlet/turbulentDFMInletFvPatchVectorField.C'
        if group=='D1': edit_once(c,'        U *= fCorr;','        // D1: flow correction disabled; U *= fCorr;')
        if group=='D2': edit_once(c,'L0_[label] = inv(E)&L_[label];','L0_[label] = L_[label]; // D2 direct untransformed scale')
        if group=='D3': edit_once(c,'const vector L = vector(L_[faceI].xx(), L_[faceI].yx(), L_[faceI].zx());','const vector L = vector(L_[faceI].xx(), L_[faceI].xx(), L_[faceI].xx()); // D3 common time scale')
    if group=='D4': d4_adjust(root/'case')
    template=(ROOT0/'run_debug01.sh').read_text()
    template=template.replace('L22_6_v3S0_DBG01',f'L22_6_v3S0_{tag}').replace(str(ROOT0),str(root))
    template=template.replace('headnevermatch','headnevermatch')
    template += '\npython3 "$ROOT/analyze_v3.py" "$ROOT/case" "$ROOT/metrics.json" > "$ROOT/analyze.log" 2>&1\n'
    script=root/'run.sh';script.write_text(template);script.chmod(0o700)
    shutil.copy2(ROOT0/'analyze_v3.py',root/'analyze_v3.py')
    shutil.copy2(ROOT0/'EXPERIMENT_CARD.md',root/'EXPERIMENT_CARD.md')
    return {'group':group,'seq':seq,'tag':tag,'root':str(root),'source_kind':kind,'psi_top_deg':psi,'bc':bc,'script':'run.sh','case':str(root/'case')}

def main():
    manifest=P/'prepared_jobs.jsonl'
    if manifest.exists(): raise FileExistsError(manifest)
    with manifest.open('x') as out:
        for group,seq in JOBS:
            row=stage(group,seq)
            out.write(json.dumps(row)+'\n');out.flush()
            print(row['tag'],row['root'],flush=True)
if __name__=='__main__': main()
