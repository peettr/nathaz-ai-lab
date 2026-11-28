#!/usr/bin/env python3
"""Read-only CRC smoke evidence extraction; run via SSH stdin."""
import pathlib,re,math,json,statistics,os
R=pathlib.Path('/groups/kareem/[用户]/L26_23_NEARWALL_R1')
S=pathlib.Path('/groups/kareem/[用户]/petw_runs/ubwp/r25_2_chew/S2_coarse/production')
T=re.compile(r'^Time = ([\d.eE+-]+)s?$')
C=re.compile(r'^Courant Number mean: ([\d.eE+-]+) max: ([\d.eE+-]+)')
E=re.compile(r'^ExecutionTime = ([\d.eE+-]+) s\s+ClockTime = ([\d.eE+-]+) s')
def read_log(path):
    pairs=[]; exe=[]; lastco=None; tim=None; bad=[]; tail=[]; starts=0
    with path.open(errors='replace') as f:
        for lineno,line in enumerate(f,1):
            line=line.strip(); m=C.match(line)
            if m: lastco=(float(m[1]),float(m[2]))
            m=T.match(line)
            if m:
                tim=float(m[1]); starts+=1
                if tim>0.501: break
                if lastco is not None: pairs.append((tim,*lastco))
            m=E.match(line)
            if m and tim is not None and tim<=0.501: exe.append((tim,float(m[1]),float(m[2])))
            if tim is not None and tim<=0.501 and re.search(r'(^|[^a-z])(nan|inf|sigfpe)([^a-z]|$)|FOAM FATAL|floating point exception',line,re.I) and 'FOAM_SIGFPE' not in line and 'sigFpe : Enabling' not in line: bad.append((lineno,line[:160]))
            if path==R/'smoke/log.pimpleFoam': tail.append(line)
    def window(a,b):
        p=[x[2] for x in pairs if a<x[0]<=b]
        if not p:return None
        p.sort(); return {'n':len(p),'max':p[-1],'p99':p[math.ceil(.99*len(p))-1],'first':next(x[0] for x in pairs if a<x[0]<=b),'last':max(x[0] for x in pairs if a<x[0]<=b)}
    e=[x for x in exe if x[0]<=.5]
    return {'path':str(path),'time_count':starts,'windows':{'full':window(0,.5),'late':window(.25,.5)},'first_exec':e[0] if e else None,'last_exec':e[-1] if e else None,'bad_count':len(bad),'bad_first':bad[:10], 'end':('End' in tail[-30:] if tail else None),'finalising':('Finalising parallel run' in tail[-30:] if tail else None)}
for p in [R/'smoke/log.pimpleFoam',S/'log.pimpleFoam']:
 print('LOG',json.dumps(read_log(p)))
case=R/'smoke/case'
for p in [case/'postProcessing',case/'processor0/postProcessing']:
 print('POSTROOT',str(p), 'exists',p.exists(),'symlink',p.is_symlink())
 if p.exists():
  for f in sorted(p.rglob('*')):
   if f.is_file():
    print('POSTFILE',str(f),f.stat().st_size)
for d in [case/'processor0',case/'processor47']:
 print('TIMES',str(d),[(x.name, x.is_dir()) for x in sorted(d.iterdir()) if x.is_dir() and (re.match(r'^\d',x.name) or x.name=='postProcessing')])
print('ROOT_SIZE_BYTES',sum(f.stat().st_size for f in R.rglob('*') if f.is_file() and not f.is_symlink()))
for nm in ['BuildingTaps','REF2']:
 p=case/'postProcessing'/nm/'0'/'p'
 with p.open(errors='replace') as f:
  headers=[]; first=None; last=None; count=0; finite=True; unequal=True; widths={}
  for line in f:
   if line.startswith('#'):
    headers.append(line.strip()[:250]);continue
   cells=line.split()
   if not cells:continue
   count+=1; widths[len(cells)]=widths.get(len(cells),0)+1
   try: vals=list(map(float,cells))
   except ValueError:finite=False;continue
   if not all(math.isfinite(v) for v in vals):finite=False
   if len(vals)>2 and max(vals[1:])==min(vals[1:]):unequal=False
   if first is None:first=vals
   last=vals
 print('PROBES',nm,json.dumps({'headers':headers[:6],'rows':count,'widths':widths,'finite':finite,'nonconstant_each_row':unequal,'first':first[:8] if first else None,'last':last[:8] if last else None,'last_distinct_columns':len(set(last[1:])) if last else None}))
for p in [S/'case/system/controlDict',R/'smoke/case/system/controlDict']:
 print('WRITE_DICT',p,[(x.strip()) for x in p.read_text().splitlines() if re.match(r'^(writeControl|writeInterval|purgeWrite)\b',x.strip())][:6])
for p in [S/'case/processor0',S/'case/processor47']:
 print('BASE_TIMES',p, [(x.name, sum(y.stat().st_size for y in x.rglob('*') if y.is_file())) for x in p.iterdir() if x.is_dir() and re.match(r'^\d',x.name)][:8])
