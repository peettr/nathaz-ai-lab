#!/usr/bin/env python3
"""Post-solver frozen T1c trace and 80-point gates; no solver control."""
import argparse, csv, hashlib, json, math, pathlib, statistics, sys

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def trace_gate(reference, candidate):
    with open(reference,newline='') as f:
        reader=csv.DictReader(f);keys=reader.fieldnames
        assert keys and 'step' in keys
        refs={int(q['step']):q for q in reader}
    with open(candidate,newline='') as f:
        reader=csv.DictReader(f)
        assert reader.fieldnames==keys,('schema',reader.fieldnames,keys)
        rows=[q for q in reader if int(q['step'])<=2000]
    assert [int(q['step']) for q in rows]==list(range(50,2001,50))
    diffs={};nums=0
    for q in rows:
        step=int(q['step']);assert step in refs
        for key in keys:
            if key=='step':continue
            value=q[key];value0=refs[step][key]
            if value=='' and value0=='':continue
            assert value and value0,('missing',step,key)
            try:v=float(value);v0=float(value0)
            except ValueError:
                assert value==value0,('non-numeric',step,key)
                continue
            assert math.isfinite(v) and math.isfinite(v0),('nonfinite',step,key)
            d=abs(v-v0)/max(abs(v0),1e-12)
            diffs[key]=max(d,diffs.get(key,0.));nums+=1
    assert nums>300
    maximum=max(diffs.values(),default=0.)
    return {'rows':len(rows),'numeric_compared':nums,'max_relative_by_field':diffs,'max_relative':maximum,'passed':maximum<=1e-4,'reference_sha256':digest(reference),'candidate_sha256':digest(candidate)}

def points_gate(reference, candidate=None):
    ref=json.loads(pathlib.Path(reference).read_text())
    assert len(ref['rows'])==80
    old={int(q['id']):q['sample']['plus_dx']['Su_ratio'] for q in ref['rows']}
    obs={int(q['id']):q['after'] for q in ref['rows']}
    if candidate is None:
        rows=[{'id':i,'Su':s,'obs':obs[i]} for i,s in old.items()]
    else:
        obj=json.loads(pathlib.Path(candidate).read_text());rows=obj['rows']
    assert len(rows)==80 and {int(q['id']) for q in rows}==set(range(1,81))
    assert all(math.isfinite(float(q['Su'])) and math.isfinite(float(q['obs'])) and abs(float(q['obs'])-obs[int(q['id'])])<=1e-10 for q in rows)
    mae=statistics.mean(abs(float(q['Su'])-obs[int(q['id'])]) for q in rows)
    base=statistics.mean(abs(old[i]-obs[i]) for i in old)
    delta=statistics.median(abs(float(q['Su'])-old[int(q['id'])]) for q in rows)
    return {'rows':80,'mae':mae,'baseline_mae':base,'mae_delta_abs':abs(mae-base),'point_delta_median':delta,'passed':abs(mae-base)<=.005 and delta<=.01,'reference_sha256':digest(reference),'candidate_sha256':digest(candidate) if candidate else 'reference-as-candidate'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('--trace');ap.add_argument('--reference-as-candidate',action='store_true');args=ap.parse_args()
    r=pathlib.Path(args.root)
    try:
        a=trace_gate(r/'B2u_trace.csv',pathlib.Path(args.trace) if args.trace else r/'case_4gpu/RESULTS/city_stability.csv')
        b=points_gate(r/'B2u_reference_points.json',None if args.reference_as_candidate else r/'points_80_t1c.json')
        result={'trace':a,'points':b,'passed':a['passed'] and b['passed']}
        (r/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
        print('COMPARE',json.dumps(result),flush=True)
        return 0 if result['passed'] else 72
    except Exception as e:
        result={'passed':False,'error':repr(e)}
        (r/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
        print('COMPARE_ERROR',repr(e),file=sys.stderr,flush=True)
        return 73
if __name__=='__main__':sys.exit(main())
