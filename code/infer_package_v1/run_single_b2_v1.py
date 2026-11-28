#!/usr/bin/env python3
import argparse, importlib.util, json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--event',required=True,choices=('N8','N9','N10'));p.add_argument('--lead',required=True,choices=('24h','48h','72h'));a=p.parse_args()
spec=importlib.util.spec_from_file_location('science',ROOT/'infer_b2_science_v1.py');science=importlib.util.module_from_spec(spec);spec.loader.exec_module(science)
science.ROOT=ROOT
assert science.sha(science.PARAM)==science.EXPECTED
assert any(d.platform=='gpu' for d in science.jax.devices())
config=json.loads((ROOT/'event_times_bbox_gc37x.json').read_text())['events'];v=config[a.event]['leads'][a.lead];cycle=v['t0'].replace('-','').replace(':','').replace('T','')[:10]
science.run_one(a.event,a.lead,cycle,int(v['length_h']//6),config[a.event]['domain'])
