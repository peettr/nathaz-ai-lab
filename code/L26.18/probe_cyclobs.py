import requests, csv, io, json, pathlib
root=pathlib.Path('/content/L26_18'); root.mkdir(exist_ok=True)
(root/'.colab_owner').write_text('L26.18-01 second round researchos-qtl-quick qtl-l2618-bc-1110')
base='https://cyclobs.ifremer.fr/app/api/getData'
for sid in ['al092022','al102023','al092024']:
 r=requests.get(base,params={'sid':sid,'include_cols':'all','product_type':'gridded'},timeout=45); print('API',sid,r.status_code,len(r.content),r.text[:200],flush=True);r.raise_for_status()
 rows=list(csv.DictReader(io.StringIO(r.text))); print('ROWS',sid,len(rows),'KEYS',list(rows[0]) if rows else [],flush=True)
 (root/f'meta_{sid}.json').write_text(json.dumps(rows,indent=2))
 for row in rows[:2]:print('SAMPLE',json.dumps({k:v for k,v in row.items() if k in ['data_url','l2_sar_fix_product_url','acquisition_start_time','analysis_rmax','eye_center','eye_in_acq','mission','track_source']},ensure_ascii=False),flush=True)
