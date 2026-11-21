#!/usr/bin/env python3
"""At owned-session cutoff, archive only verified complete forecast units and observations."""
import hashlib,json,pathlib,zipfile
R=pathlib.Path('/content/p1')
items=[]
for csv in sorted((R/'forecast_parts').glob('*.csv')):
    meta=csv.with_suffix('.json')
    if not meta.exists():continue
    try:
        digest=hashlib.sha256(csv.read_bytes()).hexdigest()
        if json.loads(meta.read_text())['sha256']!=digest:continue
    except (OSError,ValueError,KeyError):continue
    items.extend((csv,meta))
for sub in ('obs',):
    items.extend(sorted(x for x in (R/sub).glob('*.csv') if x.is_file()))
for name in ('stations_p2_frozen.csv','freeze_manifest.json','inventory_all.json','archive_availability.jsonl','oscar_height_metadata.csv','forecast_progress.jsonl','gfs_progress.jsonl','ai_full.log','gfs_full.log','oscar2.log','stage1_attempt2.log','stage2_aiwp.py','stage2_gfs.py','build_pairs.py'):
    f=R/name
    if f.is_file():items.append(f)
manifest={str(f.relative_to(R)):{'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in items}
archive=R/'p1_cutoff_archive.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
    for f in items:z.write(f,str(f.relative_to(R)))
    z.writestr('checkpoint_archive_manifest.json',json.dumps(manifest,indent=2))
print(json.dumps({'archive':str(archive),'units':sum(x.startswith('forecast_parts/') and x.endswith('.csv') for x in manifest),'files':len(manifest),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}),flush=True)
