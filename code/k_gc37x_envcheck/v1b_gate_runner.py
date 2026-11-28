import pathlib, sys, json, hashlib, datetime, warnings
root=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37x')
base=root/'envcheck_v1'
sys.path.insert(0,str(base))
import envcheck_gc37x_v1b as m
rows=[]
for source in ('AI','GFS'):
    for cycle in ('2024061218','2024061318','2024061418'):
        for path in sorted((root/'drivers_N1_v1'/source/cycle).glob('FILE:*')):
            try:
                slabs,grid=m.records(path)
                idx=m.mask_points(path,38.06,-97.86)
                mins=m.field_qc(slabs,idx,True)
                rows.append({'file':str(path),'min_adjacent_correlation':mins,'qc':'pass','grid_count':len(idx)})
            except Exception as exc:
                rows.append({'file':str(path),'qc':'FAIL','detail':repr(exc)})
            print('FIELD_QC',json.dumps(rows[-1]),flush=True)
print('FIELD_QC_TOTAL',len(rows),'FAIL',sum(row['qc']!='pass' for row in rows),flush=True)
fixtures=[]
for case in ('control','q_constant','nan','wind_reverse'):
    path=base/'fixtures'/'cases'/case/'FILE:2024-06-14_18'
    report=base/'fixtures'/'reports'/f'{case}_v1b.json'
    expected=json.dumps([{'file':f'cases/{case}/{path.name}','sha256':m.sha(path)}])
    if report.exists():
        if report.read_text()!=expected: raise ValueError('existing fixture differs: '+str(report))
    else: report.write_text(expected)
    output=m.assess(path,'N1','2024061418',report,base/'fixtures'/'n1_config.json',True,1)
    fixtures.append({'case':case,'file':str(path),'report':str(report),'report_sha256':m.sha(report),'output':output})
    print('CASE',case,'MetPy version:',m.metpy.__version__,json.dumps(output,ensure_ascii=False), 'SCRIPT_EXIT=0',flush=True)
report=base/'VALIDITY_GATE_v1b_windfix_raw_20261127.json'
if report.exists(): raise FileExistsError(report)
report.write_text(json.dumps({'fields':rows,'fixtures':fixtures},ensure_ascii=False,indent=2))
print('RAW_REPORT',str(report),'SHA256',m.sha(report),flush=True)
