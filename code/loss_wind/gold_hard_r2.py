#!/usr/bin/env python3
"""Hand-collated narrative-only source gold; each event ID assigned explicitly."""
import csv,json,pathlib,collections,random
P=pathlib.Path(__file__).parent
# Independently read EVENT_NARRATIVE. These labels do not use MAGNITUDE_TYPE or selection-stratum as truth.
LABELS={
 'estimated_unspecified':'969321 965318 967369 965865 1015501 1120801 903239 1135595 1128973 896322 998580 762117 1044218 823940 825773',
 'measured':'1078836 810667 862589 1123019 969828 1021317 742693 969416 904645 756298 1054536 1032897 977217 787346 915990 1051086 1143123 857588 908164 1141750 791291 1058012 1057131 963874 846625 963870 1057203 886119 1002869 1008617 764448 796009 1010706 874908 989927 989653 732458',
 'observer_estimate':'746263 1022350',
 'damage_inferred':'1112785 954704 975490 976555 979361 985286 976648 976639 976253 982087 976643 1000842 988481 994189 1095670 953276',
}
byid={id:label for label,ids in LABELS.items() for id in ids.split()}
rows=list(csv.DictReader((P/'sample_hard_70_v2.csv').open()));assert len(rows)==70 and set(byid)=={r['EVENT_ID'] for r in rows},(len(byid),set(byid)^{r['EVENT_ID'] for r in rows})
with (P/'gold_hard_70.jsonl').open('w') as f:
 for r in rows:
  f.write(json.dumps({'event_id':r['EVENT_ID'],'primary_source':byid[r['EVENT_ID']],'label_basis':'Manual narrative-only; magnitude/type not used; damage inference only when wording connects method to damage, including surveyed damage outcome.','stratum':r['stratum']})+'\n')
with (P/'questions_hard_70.jsonl').open('w') as f:
 for r in rows:f.write(json.dumps({'id':r['EVENT_ID'],'prompt':'EVENT_NARRATIVE:\n'+r['EVENT_NARRATIVE']},ensure_ascii=False)+'\n')
rng=random.Random(20261017);(P/'review_ids_hard_70.json').write_text(json.dumps(rng.sample([r['EVENT_ID'] for r in rows],7),indent=2)+'\n')
print(collections.Counter(byid.values()),'review',json.loads((P/'review_ids_hard_70.json').read_text()))
