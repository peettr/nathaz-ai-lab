#!/usr/bin/env python3
"""Fail closed on missing/mismatched OpenFOAM patch fields (ASCII text)."""
import argparse
import re
from pathlib import Path


def blocks(text, section=None):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    if section:
        m = re.search(r'\b'+re.escape(section)+r'\s*\{', text)
        if not m:
            raise ValueError('missing section '+section)
        text = text[m.end():]
    pattern = re.compile(r'("[^"]+"|[A-Za-z_][\w.]*)\s*\{')
    pos = 0
    while (m := pattern.search(text, pos)):
        depth = 1
        i = m.end()
        while i < len(text) and depth:
            depth += (text[i] == '{') - (text[i] == '}')
            i += 1
        if depth:
            raise ValueError('unclosed block '+m[1])
        yield m[1].strip('"'), text[m.end():i-1]
        pos = i


def verify(case):
    boundary = case/'constant/polyMesh/boundary'
    if not boundary.is_file():
        raise FileNotFoundError(boundary)
    patches = {}
    for name, body in blocks(boundary.read_text()):
        typ = re.search(r'\btype\s+(\w+)\s*;', body)
        if typ:
            patches[name] = typ[1]
    if not patches:
        raise ValueError('no boundary patches parsed')
    fields = sorted(p for p in (case/'0').iterdir() if p.is_file() and re.search(r'\bclass\s+vol(?:Scalar|Vector|Tensor|SymmTensor)Field\s*;', p.read_text()[:1024]))
    if not fields:
        raise ValueError('no vol fields in 0/')
    errors = []
    for field in fields:
        entries = list(blocks(field.read_text(), 'boundaryField'))
        matched = {}
        for patch, mesh_type in patches.items():
            hits = [(key, body) for key, body in entries if key == patch or (key != patch and re.fullmatch(key, patch))]
            if len(hits) != 1:
                errors.append(f'{field.name}:{patch} matches {len(hits)} entries')
                continue
            key, body = hits[0]
            field_type = re.search(r'\btype\s+(\w+)\s*;', body)
            if not field_type:
                errors.append(f'{field.name}:{patch} missing type')
                continue
            matched[patch] = field_type[1]
            if mesh_type in ('symmetryPlane','empty','cyclic','wedge') and field_type[1] != mesh_type:
                errors.append(f'{field.name}:{patch} mesh={mesh_type} field={field_type[1]}')
            if mesh_type == 'wall' and field_type[1] in ('symmetryPlane','empty','cyclic'):
                errors.append(f'{field.name}:{patch} wall incompatible field={field_type[1]}')
        print(f'{case.name}/{field.name}: {len(matched)}/{len(patches)} patches; bottom={matched.get("bottom","MISSING")}')
    print('mesh patches:', ', '.join(f'{p}:{t}' for p,t in patches.items()))
    for error in errors:
        print('ERROR', error)
    return not errors


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cases', nargs='+', type=Path)
    args = ap.parse_args()
    ok = True
    for case in args.cases:
        try:
            ok = verify(case) and ok
        except Exception as e:
            print('ERROR', case, type(e).__name__, str(e))
            ok = False
    raise SystemExit(0 if ok else 1)
