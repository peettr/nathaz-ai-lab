import hashlib,json,pathlib,sys
root=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
ops=root/'drivers_N9_v1/ops_N9_72h_GFS_b2'
p=ops/'WPS_2022060706_GFS_REPORT.json'
rows=json.loads(p.read_text())
print('report',p,'count',len(rows),'leads',[r.get('lead') for r in rows])
errors=[]
for r in rows:
    f=root/'drivers_N9_v1'/r['file']
    if not f.is_file(): errors.append((str(f),'missing'));continue
    h=hashlib.sha256(f.read_bytes()).hexdigest()
    if h!=r['sha256'] or r['records']!=172: errors.append((str(f),'hash_or_count',h,r['sha256'],r['records']))
print('verified',len(rows)-len(errors),'errors',errors[:5]);sys.exit(bool(errors))
