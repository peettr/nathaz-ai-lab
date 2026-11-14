#!/usr/bin/env python3
"""Independent CRC WPS framing/field-byte readback; no driver mutation."""
import collections
import datetime as dt
import hashlib
import json
import pathlib
import struct
import sys

ROOT=pathlib.Path('/groups/kareem/[用户]/WRF/petw_runs/lab_K_gc37/drivers_gc37_v1')
OPS=ROOT/'ops_cpu_v1'
LEVELS=[int(x) for x in (OPS/'COMMON_LEVELS.txt').read_text().strip().split(',')]
CYCLES={'2020060806':6,'2020060706':10,'2020060606':14}
FIELDS={'GHT','TT','UU','VV','SPECHUMD'}

def wps(path):
    raw=path.read_bytes(); pos=0; out=[]; chunks={}
    while pos<len(raw):
        rec=[]
        for _ in range(5):
            assert pos+8<=len(raw),(path,'trunc')
            n=struct.unpack_from('>I',raw,pos)[0]
            assert n<500000000,(path,n)
            end=pos+4+n
            assert end+4<=len(raw) and raw[end:end+4]==raw[pos:pos+4],(path,'framing')
            rec.append(raw[pos+4:end]);pos=end+4
        v,h,proj,wind,data=rec
        assert v==struct.pack('>I',5) and len(h)==156 and len(proj)==28 and len(wind)==4
        assert proj[:8]==b'SWCORNER'
        lev,nx,ny,iproj=struct.unpack('>fiii',h[140:156])
        assert iproj==0 and (nx,ny)==(105,89) and len(data)==nx*ny*4,(path,nx,ny)
        import numpy as np
        vals=np.frombuffer(data,dtype='>f4')
        assert np.isfinite(vals).all(),(path,'nonfinite')
        field=h[60:69].decode('ascii').strip();level=int(round(lev))
        out.append((field,level))
        if level>=200000 and field not in ('PMSL','SPECHUMD'):
            key=(field,level)
            assert key not in chunks,(path,key)
            chunks[key]=hashlib.sha256(data).hexdigest()
    assert pos==len(raw)
    return out,chunks,hashlib.sha256(raw).hexdigest()

def main():
    assert (OPS/'run.exitcode').read_text().strip()=='0'
    result={'cycles':{},'shared_surface_field_rule':'all level>=200000 except PMSL and SPECHUMD (Q2) compared as exact binary slabs','readback':'WPS format-5 Fortran framing, 105x89 grids, all finite; five high-air fields at each of 31 levels'}
    manifest=[]; all_pairs=0; fills={}
    for cycle,n in CYCLES.items():
        entries=json.loads((OPS/f'WPS_{cycle}_REPORT.json').read_text())
        assert len(entries)==2*n,(cycle,len(entries))
        ledger=json.loads((OPS/f'SOIL_FILL_SNOWFIX_{cycle}.json').read_text())
        fill_counts=dict(collections.Counter(x['field'] for x in ledger))
        assert all('target_lat_lon_east' in x and 'donor_lat_lon_east' in x and 'filled_value' in x for x in ledger)
        fills[cycle]=fill_counts
        start=dt.datetime.strptime(cycle,'%Y%m%d%H')
        assert (start+dt.timedelta(hours=(n-1)*6)).strftime('%Y%m%d%H')=='2020060912'
        step_results={}; seen=set()
        for entry in entries:
            arm=entry['arm'];lead=entry['lead'];rel=entry['file']
            assert arm in ('AI','GFS') and lead in range(0,n*6,6) and (arm,lead) not in seen
            seen.add((arm,lead))
            assert rel==f'{arm}/{cycle}/FILE:{(start+dt.timedelta(hours=lead)):%Y-%m-%d_%H}'
            path=ROOT/rel
            assert path.is_file(),path
            fields,chunks,digest=wps(path)
            counts={name:sorted(lev for field,lev in fields if field==name and lev<200000) for name in FIELDS}
            assert all(val==sorted(lev*100 for lev in LEVELS) for val in counts.values()),(rel,counts)
            assert len(fields)==172 and entry['records']==172 and digest==entry['sha256'],rel
            assert all(x[0]!='PSFC' for x in fields)
            step_results[(arm,lead)]=chunks
            manifest.append(f'{digest}  {rel}')
        for lead in range(0,n*6,6):
            assert step_results[('AI',lead)]==step_results[('GFS',lead)],(cycle,lead,'shared_surface_byte_mismatch')
            assert len(step_results[('AI',lead)])==15,(cycle,lead,len(step_results[('AI',lead)]))
            all_pairs+=1
        result['cycles'][cycle]={'times_per_arm':n,'files':2*n,'records_per_file':172,'high_air_levels':LEVELS,'shared_surface_fields':15,'byte_identical_pairs':n,'fill_count_by_field':fill_counts,'fill_ledger':str((OPS/f'SOIL_FILL_SNOWFIX_{cycle}.json')),'build_report':str(OPS/f'WPS_{cycle}_REPORT.json')}
    assert len(manifest)==60 and all_pairs==30
    result['totals']={'files':len(manifest),'paired_times':all_pairs,'all_shared_surface_binary_equal':True,'filled_cells_by_cycle':fills}
    report=OPS/'READBACK_GC37_V1.json'; sums=ROOT/'SHA256SUMS'
    assert not report.exists() and not sums.exists(),('refuse_overwrite',report,sums)
    with report.open('x') as f:json.dump(result,f,indent=2)
    with sums.open('x') as f:f.write('\n'.join(sorted(manifest))+'\n')
    print(json.dumps({'report':str(report),'sha256sums':str(sums),'totals':result['totals'],'cycles':{k:{a:v[a] for a in ('files','byte_identical_pairs','fill_count_by_field')} for k,v in result['cycles'].items()}},indent=2))
if __name__=='__main__':main()
