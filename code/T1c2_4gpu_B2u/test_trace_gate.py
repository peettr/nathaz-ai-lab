#!/usr/bin/env python3
"""Exercise actual comparator from drive_t1c.py without launching solver."""
import ast,csv,hashlib,io,json,os,pathlib,shutil,tempfile
ROOT=pathlib.Path(__file__).resolve().parent
BASE=ROOT.parent
src=(ROOT/'drive_t1c.py').read_text()
tree=ast.parse(src)
funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('digest','compare')]
namespace={'csv':csv,'hashlib':hashlib,'json':json,'math':__import__('math'),'pathlib':pathlib}
with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
 r=pathlib.Path(tmp);namespace['r']=r
 exec(compile(ast.Module(body=funcs,type_ignores=[]),str(ROOT/'drive_t1c.py'),'exec'),namespace)
 reference=BASE.parent/'method_study/B2u_scalar_mean/B2u_trace.csv'
 actual=BASE/'T1c_4gpu_B2u/T1c_trace_first2000.csv'
 shutil.copyfile(reference,r/'B2u_trace.csv');shutil.copyfile(actual,r/'trace.csv')
 assert hashlib.sha256(actual.read_bytes()).hexdigest()==hashlib.sha256((r/'trace.csv').read_bytes()).hexdigest()
 zero=namespace['compare'](r/'trace.csv');assert zero['passed'] and zero['max_relative']==0 and zero['rows']==40
 rows=list(csv.DictReader((r/'trace.csv').open(newline='')))
 key=next(k for k in rows[0] if k!='step' and rows[0][k] and float(rows[0][k])!=0)
 before=float(rows[0][key]);rows[0][key]=str(before*1.01)
 with (r/'trace.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
 bad=namespace['compare'](r/'trace.csv');assert not bad['passed'] and bad['max_relative']>1e-4
 print(json.dumps({'source':str(actual),'reference':str(reference),'all_zero':zero,'perturbed':{'field':key,'step':rows[0]['step'],'before':before,'after':float(rows[0][key]),'max_relative':bad['max_relative'],'passed':bad['passed']}},indent=2))
