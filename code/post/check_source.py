#!/usr/bin/env python3
"""Fail-closed source log and mean VTK provenance check, read-only."""
import hashlib, json, re, sys
from pathlib import Path
log, vtk = map(Path,sys.argv[1:3])
text=log.read_text(errors='replace')
steps=re.search(r'\|\s*Time Steps\s*\|\s*(\d+)',text)
requested=re.search(r'\|\s*Run steps\s*\|\s*(\d+)',text)
samples=re.search(r'\|\s*Avg samples\s*\|\s*(\d+)',text)
finished='Task finished' in text
nonfinite=re.findall(r'(?<![A-Za-z_])(?:nan|[+-]?inf(?:inity)?)(?![A-Za-z_])',text,re.I)
assert steps and requested and samples and int(steps[1])==int(requested[1])==6400 and int(samples[1])==550 and finished and not nonfinite,(steps,samples,finished,nonfinite[:5])
assert vtk.is_file() and vtk.stat().st_size==7142083
h=hashlib.sha256()
with vtk.open('rb') as f:
 for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
assert h.hexdigest()=='bf8de92f7bccb33440837c99975cd8a6ed30bb813eb1b902a05b4618f804fd18'
print(json.dumps({'log':str(log),'steps':6400,'avg_samples':550,'task_finished':True,'nonfinite_log_tokens':0,'source_vtk':str(vtk),'source_vtk_bytes':vtk.stat().st_size,'source_vtk_sha256':h.hexdigest(),'note':'solver completed but gate-check wrapper failed; finite fields checked by post_v2.py'}))
