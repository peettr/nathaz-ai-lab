#!/usr/bin/env python3
"""Mechanical, no-edit extraction of complete t02.py from raw tool-free replies."""
import json
from pathlib import Path
import sys

TOOLS = Path('./22_Lab/06_Logs/l22_6/sessions/tools')
sys.path.insert(0, str(TOOLS))
from blocks import blocks

BASE = Path(__file__).resolve().parent

def extract(identity):
    d = BASE / identity
    gpt = identity.startswith('gpt_')
    raw = d / ('R1.json' if gpt else 'A1.jsonl')
    if not raw.exists():
        return {'id': identity, 'state': 'pending'}
    obj = json.loads(raw.read_text().splitlines()[-1] if not gpt else raw.read_text())
    response = obj.get('text' if gpt else 'response')
    if obj.get('status') not in (('completed',) if gpt else ('ok',)) or not isinstance(response, str):
        return {'id': identity, 'state': 'generation_failure', 'model': obj.get('model'), 'status': obj.get('status')}
    reply = d / 'reply_R1.txt'
    if reply.exists() and reply.read_text() != response:
        raise RuntimeError(f'existing reply mismatch: {reply}')
    if not reply.exists():
        reply.write_text(response)
    candidates = [b for b in blocks(response) if b['lang'].lower() in ('python', 'python3', 'py', '')]
    named = [b for b in candidates if 't02.py' in ' '.join(b['ctx']) or b['code'].splitlines()[0].strip().endswith('t02.py')]
    selected = (named or candidates)[:1]
    complete = bool(selected and 'import' in selected[0]['code'] and len(selected[0]['code'].encode()) > 100)
    cdir = d / 'cand_R1'
    cdir.mkdir(exist_ok=True)
    target = cdir / 't02.py'
    if complete:
        if target.exists() and target.read_text() != selected[0]['code']:
            raise RuntimeError(f'existing candidate mismatch: {target}')
        if not target.exists():
            target.write_text(selected[0]['code'])
    record = {'id': identity, 'state': 'extracted' if complete else 'no_complete_source',
              'model': obj.get('model'), 'usage': obj.get('usage'),
              'duration_s': obj.get('elapsed_s', obj.get('duration_seconds')),
              'raw_path': str(raw), 'reply_path': str(reply),
              'candidate_path': str(target) if complete else None,
              'block_line': selected[0]['start'] if selected else None,
              'block_count': len(candidates)}
    out = d / 'extract_R1.json'
    if out.exists() and json.loads(out.read_text()) != record:
        raise RuntimeError(f'existing extraction mismatch: {out}')
    if not out.exists():
        out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record

if __name__ == '__main__':
    for identity in sys.argv[1:]:
        row = extract(identity)
        print(identity, row['state'], row.get('model'), row.get('block_line'))
