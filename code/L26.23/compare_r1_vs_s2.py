#!/usr/bin/env python3
"""L26.23 frozen §2.2–2.3: compare two unmodified negpeak per_tap_main.csv files."""
import argparse, csv, json, math, pathlib
import numpy as np

EXPECTED=216
SEED=4101009
B=2000

def load(path):
    with open(path,newline='') as f:
        rows=list(csv.DictReader(f))
    ids=[int(r['tap_id']) for r in rows]
    if len(ids)!=360 or len(set(ids))!=360:
        raise ValueError(f'{path}: expected 360 unique integral tap_id')
    return {int(r['tap_id']):r for r in rows}

def evaluate(base, variant):
    a,b=load(base),load(variant)
    if a.keys()!=b.keys() or any(a[i]['zone']!=b[i]['zone'] for i in a):
        raise ValueError('tap_id/zone mismatch; fail closed')
    ids=sorted(i for i in a if a[i]['zone']=='side_separated')
    if len(ids)!=EXPECTED: raise ValueError(f'side_separated count {len(ids)} != {EXPECTED}')
    out={'source_base':str(base),'source_variant':str(variant),'N_side_separated':len(ids),'bootstrap_reps':B,'seed':SEED,'metrics':{}}
    for P in ('50','90'):
        suffix='neg_'+P
        D=[]; n=[]
        for i in ids:
            try:
                vals=[float(row[suffix+'_'+field]) for row in (a[i],b[i]) for field in ('LES','halfA_LES','halfB_LES')]
            except (ValueError,KeyError) as e:
                out['metrics'][P]={'verdict':'不判（数据闸门）','tap_id':i,'reason':str(e)}
                break
            if not all(math.isfinite(v) for v in vals):
                out['metrics'][P]={'verdict':'不判（数据闸门）','tap_id':i,'reason':'nonfinite quantile/half'}
                break
            D.append(vals[3]-vals[0]); n.append(max(abs(vals[1]-vals[2]),abs(vals[4]-vals[5])))
        else:
            x=np.asarray(D)
            rng=np.random.default_rng(SEED)
            draws=np.median(x[rng.integers(0,len(x),size=(B,len(x)))],axis=1)
            lo,hi=map(float,np.quantile(draws,[.05,.95]))
            med=float(np.median(x)); nmed=float(np.median(n))
            # Frozen §2.3: CI excludes zero AND |median D| >= max(.10, median n).
            effect=(hi<0 or lo>0) and abs(med)>=max(.10,nmed)
            # CI entirely contained in closed equivalence interval [-.10,+.10].
            no_effect=lo>=-.10 and hi<=.10
            verdict='有影响' if effect else '无影响' if no_effect else '未分辨'
            out['metrics'][P]={'verdict':verdict,'median_D':med,'CI90':[lo,hi],
                                'median_n':nmed,'max_abs_D':float(np.max(abs(x))),
                                'negative_D_count':int(np.count_nonzero(x<0))}
    vv=[out['metrics'][P]['verdict'] for P in ('50','90')]
    out['verdict']=('不判（数据闸门）' if any(v.startswith('不判') for v in vv) else
                    vv[0] if vv[0]==vv[1] else '未分辨')
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--s2',required=True);p.add_argument('--variant',required=True);p.add_argument('--out')
    a=p.parse_args(); result=evaluate(a.s2,a.variant)
    txt=json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
    if a.out:
        target=pathlib.Path(a.out)
        if target.exists(): raise FileExistsError(target)
        target.write_text(txt)
    print(txt)
if __name__=='__main__': main()
