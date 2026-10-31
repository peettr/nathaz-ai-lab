#!/usr/bin/env python3
"""T03 protocol-v2 CRC grader: candidate Make -> clean OF10 case -> probes -> L0–L3.
Run within an allocated compute job. Never submit qsub from this script.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from analyze_T03 import load, compare

LIB = 'libturbulentDFMVeerInlet'


def rating(candidate, baseline):
    vals = compare(candidate, baseline)
    checks = {}
    for z, row in vals.items():
        checks[z] = {
            'direction_abs_error_deg': row['direction_abs_error_target_deg'],
            'mean_speed_abs_relative_error': abs(row['mean_speed_relative_delta']) if row['mean_speed_relative_delta'] is not None else None,
            'R_diagonal_max_abs_relative_error': max(abs(v) for v in row['R_diagonal_relative_delta'].values()),
            'rho_offdiagonal_max_abs_delta': max(row['rho_offdiagonal_abs_delta'].values()),
            'rho_yz_abs_delta': row['rho_offdiagonal_abs_delta']['yz'],
        }
    if len(checks) != 5 or any(any(v is None or not math.isfinite(v) for v in r.values()) for r in checks.values()):
        raise ValueError('nonfinite or missing primary metrics')
    def passes(d, u, r, rho):
        return all(row['direction_abs_error_deg'] <= d and row['mean_speed_abs_relative_error'] <= u and
                   row['R_diagonal_max_abs_relative_error'] <= r and row['rho_offdiagonal_max_abs_delta'] <= rho
                   for row in checks.values())
    level = 'L3' if passes(1.5, .03, .05, .03) else ('L2' if passes(3, .10, .10, .06) else 'L1')
    tag = all(row['direction_abs_error_deg'] <= 3 for row in checks.values()) and any(row['rho_yz_abs_delta'] > .06 for row in checks.values())
    return level, checks, vals, tag


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path, help='candidate source directory with own Make/files and Make/options')
    p.add_argument('--work-root', required=True, type=Path)
    p.add_argument('--baseline-json', required=True, type=Path)
    p.add_argument('--template-case', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    result = {'schema':'L22_6_T03_grade_v2','status':'not_run','level':None,'source':str(a.source),'work_root':str(a.work_root),'steps':{}}
    def save():
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    # Harness prerequisites are never charged to a candidate.
    try:
        if not a.baseline_json.is_file(): raise FileNotFoundError(f'baseline missing: {a.baseline_json}')
        baseline=json.loads(a.baseline_json.read_text())
        if baseline.get('schema')!='L22_6_T03_v1_2' or 'B0' not in baseline: raise ValueError('invalid frozen B0 baseline')
        if not (a.template_case/'0/U').is_file() or not (a.template_case/'constant/boundaryData/inlet/psi').is_file():
            raise FileNotFoundError('clean template or frozen psi missing')
        if (a.template_case/'postProcessing').exists() or (a.template_case/'constant/polyMesh').exists():
            raise ValueError('template case is not clean')
        if a.work_root.exists(): raise FileExistsError(f'work root exists: {a.work_root}')
        if not shutil.which('wmake') or not shutil.which('pimpleFoam'): raise EnvironmentError('OpenFOAM environment missing')
    except (OSError, ValueError, KeyError) as ex:
        result.update(status='harness_fault',error=str(ex)); save(); return 2
    try:
        if not (a.source/'Make/files').is_file() or not (a.source/'Make/options').is_file():
            raise ValueError('candidate Make/files and Make/options required')
        contents=(a.source/'Make/files').read_text()
        if not re.search(r'(?m)^\s*LIB\s*=\s*\$\(FOAM_USER_LIBBIN\)/libturbulentDFMVeerInlet\s*$',contents):
            raise ValueError('candidate Make/files must produce libturbulentDFMVeerInlet')
        # No source-file triad or psi regex gate: the actual compiled BC and measured output decide.
        a.work_root.mkdir(parents=True)
        shutil.copytree(a.source,a.work_root/'src',ignore=shutil.ignore_patterns('linux64*','*.o','*.so','.git','__pycache__'))
        lib=a.work_root/'lib'; lib.mkdir()
        env=os.environ.copy(); env['FOAM_USER_LIBBIN']=str(lib)
        env['LD_LIBRARY_PATH']=str(lib)+':'+env.get('LD_LIBRARY_PATH','')
        env.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
        def run(cmd,cwd,name,timeout=None):
            with (a.work_root/f'{name}.log').open('w') as log:
                try:
                    proc=subprocess.run(cmd,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
                except subprocess.TimeoutExpired:
                    result['steps'][name]='timeout'; save(); raise TimeoutError(f'{name} exceeded 4h')
            result['steps'][name]=proc.returncode; save()
            if proc.returncode: raise RuntimeError(f'{name} failed with {proc.returncode}')
        run(['wmake','libso'],a.work_root/'src','compile')
        if not (lib/(LIB+'.so')).is_file(): raise RuntimeError('compile did not produce requested library')
        case=a.work_root/'case'; shutil.copytree(a.template_case,case)
        u=case/'0/U'; text=u.read_text()
        text,n=re.subn(r'(?m)(\btype\s+)turbulentDFMInlet(\s*;)',r'\1turbulentDFMVeerInlet\2',text,count=1)
        if n!=1: raise ValueError('template 0/U missing inlet type')
        u.write_text(text)
        control=case/'system/controlDict'; text=control.read_text()
        text,n=re.subn(r'libturbulentInflow\.so',LIB+'.so',text)
        if not n: raise ValueError('template controlDict missing library')
        control.write_text(text)
        run(['blockMesh'],case,'blockMesh')
        run(['checkMesh'],case,'checkMesh')
        run(['pimpleFoam'],case,'pimpleFoam',timeout=4*3600)
        candidate=load(case,lambda z:20*z/1.8)
        level,checks,delta,tag=rating(candidate,baseline['B0'])
        result.update(status='scored',level=level,primary_by_height=checks,metrics={'candidate':candidate,'candidate_vs_B0':delta},
                      fluctuation_statistics_not_rotated_signature=tag)
        save(); return 0
    except (ValueError, RuntimeError, TimeoutError) as ex:
        result.update(status='L0',level='L0',error=str(ex)); save(); return 0
    except (OSError, KeyError, IndexError) as ex:
        result.update(status='harness_fault',error=str(ex)); save(); return 2

if __name__=='__main__': sys.exit(main())
