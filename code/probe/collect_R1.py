#!/usr/bin/env python3
"""Mechanical collection of CRC-produced grades; no candidate execution."""
import csv, hashlib, io, json, pathlib, tarfile
P=pathlib.Path(__file__).resolve().parent
archive=P/'probe_R1_results_20261127_01.tar.gz'
rows=[]
with tarfile.open(archive) as tar:
    for model in ('gpt','gemini','claude'):
        for condition in ('W','N'):
            for block in (1,2):
                ident=f'{model}_{condition}_b{block}'
                row={'session':ident,'round':1,'final_level':'','deliverable':'',
                     'model_version':'','duration_s':'','input_tokens':'','output_tokens':'',
                     'total_tokens':'','max_sigma_q_error':'','max_sigma_stroke_error':'',
                     'status':'','note':'','crc_job':''}
                if model=='claude':
                    row.update(status='not_started_quota',note='weekly quota remaining 18% (<20%); no session',deliverable='no')
                else:
                    root=f'L22_6_T02_probe_{ident}_20261127_01'
                    name=f'{root}/grade.json'
                    grade=tar.extractfile(name).read()
                    result=json.loads(grade)
                    dest=P/ident/'grade_R1.json'
                    if dest.exists():
                        assert dest.read_bytes()==grade,dest
                    else:dest.write_bytes(grade)
                    meta=json.loads((P/ident/'extract_R1.json').read_text())
                    assert meta['state']=='extracted'
                    usage=meta.get('usage') or {}
                    row.update(status=result['status'],final_level=result.get('level') or '',
                        deliverable='yes' if result['status']=='scored' else 'no',
                        model_version=meta['model'],duration_s=meta.get('duration_s'),
                        input_tokens=[已隐去]'input',usage.get('input_tokens','')),
                        output_tokens=[已隐去]'output',usage.get('output_tokens','')),
                        total_tokens=[已隐去]'total',usage.get('total_tokens','')),
                        max_sigma_q_error=(result.get('max_absolute_error') or {}).get('sigma_q',''),
                        max_sigma_stroke_error=(result.get('max_absolute_error') or {}).get('sigma_stroke',''))
                    if result['status']=='candidate_failed':
                        feedback=result.get('feedback')
                        assert isinstance(feedback,str)
                        f=P/ident/'fb_R1.txt'
                        if f.exists(): assert f.read_text()==feedback
                        else:f.write_text(feedback)
                rows.append(row)
assert len(rows)==12 and sum(r['status']=='scored' for r in rows)==8
out=P/'probe_levels.csv'
if out.exists():raise RuntimeError(f'Will not overwrite {out}')
with out.open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
print('rows',len(rows),'scored',sum(r['status']=='scored' for r in rows),'out',out)
print('levels',[(r['session'],r['final_level']) for r in rows])
