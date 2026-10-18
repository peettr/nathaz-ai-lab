#!/usr/bin/env python3
"""Manual annotation transcription: each line below was individually read from gold_review_sheet.txt.
The labels are narrative-only; magnitude type is NEVER consulted for label assignment.
Tuple: structure types, severity, speed value/unit/kind/source, site, rating.
"""
import csv,json,pathlib
p=pathlib.Path(__file__).parent
R={}
def add(ids,types,sev='moderate',speed=None,unit=None,kind='none',source='none',site=None,rating=None):
 for i in ids.split():
  assert i not in R,i
  R[i]=(types.split(',') if types else [],sev,speed,unit,kind,source,site,rating)
# Thunderstorm, hand read 20 independent narratives; radar in 1091854/909987/907469 dates TIME only.
add('903930','tree','minor')
add('1133662 1133150','tree,power')
add('780424','tree')
add('1091854','tree,power')
add('850227','barn,tree','severe')
add('839572','tree')
add('766209','power')
add('1030387','commercial','severe')
add('1046359','tree')
add('909987','tree,power')
add('1040950 1126214 960947 1012388','tree')
add('827245','tree,power','severe')
add('745016 902011 907469','tree')
add('836067','tree,power')
# Tropical, event-local numeric winds distinguished from storm climatology/rainfall.
add('1125591','tree')
add('1058660','house','destroyed',111,'mph','gust','estimated_unspecified') # reported gust, measurement not asserted
add('907683','tree,power','moderate',None,None,'sustained','measured','KGED')
add('903162','tree','moderate',None,None,'gust','measured','Long Neck Mesonet')
add('913730','mobile_home,house,barn,tree,power,vehicle','destroyed',None,None,'none','none') # proxy observations + storm peak conflict
add('1051095','house','moderate',67,'mph','gust','measured','SAUF1 C-man') # house flooding, not wind damage
add('846032','mobile_home,house,tree')
add('816105','tree,other','severe',200,'mph','gust','damage_inferred')
add('916529','house','moderate')
add('969534','tree')
add('925854','tree,power', 'moderate',65,'mph','gust','estimated_unspecified')
add('925026','tree,power,house,vehicle','moderate',70,'mph','gust','estimated_unspecified')
add('980665','tree,power')
add('857631','tree,power,house','severe',68,'mph','gust','measured','Ocean Park')
add('924082','tree,power','moderate',45,'mph','gust','estimated_unspecified')
add('789361','house,tree','severe',47,'mph','gust','measured','McEntire JNGB')
add('789609','tree,other')
add('974378','tree,power','moderate',67,'mph','gust','measured','Bude RAWS')
add('924057','tree,power','moderate',50,'mph','gust','estimated_unspecified')
add('925293','tree,power,house,commercial','severe',112,'mph','gust','measured','Bayou Bienvenue Weatherflow')
# High Wind, winter months; explicitly reported sensor versus EG metadata kept separate.
add('1093969','tree','moderate',40,'mph','gust','estimated_unspecified')
add('861637','tree,power','moderate',66,'mph','gust','measured','Athens mesonet')
add('1154261','tree','moderate',87,'mph','gust','measured','South Douglas Harbor profiler')
add('998904','tree,power')
add('878039','tree,power')
add('999192','power','severe')
add('1017280 808023','tree')
add('995019','', 'none')
add('743033','tree,power','moderate',60,'mph','gust','estimated_unspecified')
add('865782 859517','tree,power')
add('1060311','', 'none',60,'mph','gust','measured') # recorded 50–60 mph; bounds supplied below
add('929398','', 'none',69,'mph','gust','measured','Broken Bow ASOS')
add('881784','', 'none',None,None,'gust','measured','Department of Highways sensor')
add('744516','vehicle,other,tree','severe')
add('1001361','tree,barn','moderate',None,None,'gust','measured')
add('944379','tree,power')
add('989641','tree,power','moderate',60,'mph','gust','measured','Green Bay airport')
add('801608','tree,power,other','severe')
ids=json.loads((p/'gold_ids.json').read_text()); assert set(ids)==set(R),(len(ids),len(R),set(ids)-set(R))
rows={r['EVENT_ID']:r for i in range(1,4) for r in csv.DictReader(open(p/f'sample_{i}.csv'))}
with open(p/'gold_60.jsonl','w') as f:
 for i in ids:
  types,sev,v,u,k,src,site,rating=R[i];r=rows[i]
  f.write(json.dumps(dict(event_id=i,hazard=r['hazard'],structure_type=types,damage_severity=sev,wind_speed_value=v,wind_speed_lower=50 if i=='1060311' else None,wind_speed_upper=60 if i=='1060311' else None,wind_speed_unit=u,wind_speed_mps=round(v*(.44704 if u=='mph' else .514444),3) if v is not None else None,wind_speed_kind=k,wind_speed_source=src,instrument_or_site=site,ef_damage_rating=rating,annotation_basis='EVENT_NARRATIVE only; manual'),ensure_ascii=False)+'\n')
print('manual gold',len(R))
