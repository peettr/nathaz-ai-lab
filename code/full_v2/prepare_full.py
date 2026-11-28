"""D2 immutable full-corpus preparation: t and t-6 only; no future targets."""
import argparse, datetime as dt, hashlib, json, pathlib, random, sys
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent.parent))
from prepare_text import load_pair, regional_reference, summary, templ, PROMPT
SEED=31026
START=dt.datetime(1979,1,1,6); END=dt.datetime(2019,1,1)

def dates():
    return [START+dt.timedelta(hours=6*i) for i in range(int((END-START).total_seconds()//21600))]

def mismatch(ds):
    # Cyclic chronological shift: bijective and every pair >=30 complete days,
    # including at the wrap boundary. Seed fixes a safe displacement.
    n=len(ds); rng=random.Random(SEED)
    shift=rng.randrange(120,n-120)
    result={d.isoformat():ds[(i+shift)%n].isoformat() for i,d in enumerate(ds)}
    assert len(result)==n and len(set(result.values()))==n
    assert all(abs((dt.datetime.fromisoformat(k)-dt.datetime.fromisoformat(v)).total_seconds())>=30*86400 for k,v in result.items())
    return result,shift

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    ds=dates(); mapping,shift=mismatch(ds)
    assert ds[0]==START and ds[-1]==dt.datetime(2018,12,31,18)
    with (a.out/'mismatch_v2.json').open('x') as f: json.dump(mapping,f)
    refs=regional_reference(a.root)
    (a.out/'reference.json').write_text(json.dumps(refs,sort_keys=True))
    count=0
    for ci in range(0,len(ds),1024):
        chunk=a.out/f'inputs_{ci//1024:03d}.jsonl'
        with chunk.open('x') as f:
            for d in ds[ci:ci+1024]:
                s=summary(load_pair(a.root,d),refs)
                f.write(json.dumps({'initialization':d.isoformat(),'summary':s,'template':templ(s),'prompt':PROMPT.format(summary_json=json.dumps(s,ensure_ascii=False,sort_keys=True))},ensure_ascii=False)+'\n')
                count+=1
        print('INPUT_CHUNK',ci//1024,count,flush=True)
    (a.out/'prepare.done').write_text(json.dumps({'count':count,'shift':shift,'first':ds[0].isoformat(),'last':ds[-1].isoformat(),'excluded':'1979-01-01T00:00:00; t-6 missing (1978)'}))
    print('PREP_DONE',count,flush=True)
if __name__=='__main__':main()
