#!/usr/bin/env python3
"""Preserve interrupted O: workaround artifacts under the restored home root."""
import json,shutil,hashlib
from pathlib import Path
src=Path('./ftkb_figures');dst=Path.home()/'ftkb_figures/recovery_O_20261016'
if dst.exists():raise FileExistsError(dst)
expected={'tmp','read_only_50.jsonl','p14_pdfs_manifest.jsonl','check_staged_readonly.py','old_stage_audit.jsonl','verify_p14_pdfs_windows.py','p14_pdfs'}
items=list(src.iterdir())
if {x.name for x in items}-expected:raise RuntimeError('Unexpected O: entries: '+str({x.name for x in items}-expected))
dst.mkdir()
for p in items:
    target=dst/p.name
    if p.is_file():
        a=hashlib.sha256(p.read_bytes()).hexdigest();shutil.move(str(p),str(target));b=hashlib.sha256(target.read_bytes()).hexdigest()
        if a!=b:raise RuntimeError('hash mismatch '+str(p))
    else:shutil.move(str(p),str(target))
    print('archived',p.name,flush=True)
# Interrupted transfer is quarantined, not counted as committed PDF staging.
(src/'RECOVERY_NOTE_20261016.txt').write_text('Interrupted O: workaround archived under ./ftkb_figures/recovery_O_20261016. This contains unverified partial windows_0000 PDF staging; never count it in p14_pdfs_manifest.jsonl. New verified staging and all full-run outputs are on the restored home root.\n')
print('remaining_on_O',[(x.name,x.stat().st_size) for x in src.iterdir()],flush=True)
