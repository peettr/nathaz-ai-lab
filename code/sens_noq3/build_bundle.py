"""Create an isolated Colab bundle without changing final2 or sens_q3pk."""
import tarfile,io,hashlib,gzip,json,csv
from pathlib import Path
root=Path(__file__).resolve().parent
base=root.parent
prior=base/'sens_q3pk'
with tarfile.open(root/'source_stage.tar') as t:
    hashes={x.name:hashlib.sha256(t.extractfile(x).read()).hexdigest() for x in t}
receipts=[json.loads(x) for x in (prior/'tacc_raw_receipts.jsonl').read_text().splitlines()]
receipts={r['file'].split('/raw/',1)[1]:r['sha256'] for r in receipts}
assert all(hashes[k]==receipts[k] for k in hashes)
assert len(hashes)==534
print('ARCHIVE_SHA256_VERIFIED',len(hashes))
source=(prior/'qc_sens_retry_colab.py').read_text()
old="    if c['source']=='gust' and sust is not None and v-sust>40:rules.append('Q3')\n"
assert source.count(old)==1
source=source.replace(old,"    # Post-hoc no-Q3 sensitivity: never reject gust or PK WND by sustained-wind contrast.\n")
(root/'qc_noq3_colab.py').write_text(source)
content=(prior/'cached_source.py').read_text().replace('PETW-station-Q3PK-sensitivity/1.0','PETW-station-noQ3-sensitivity/1.0')
(root/'cached_source.py').write_text(content)
# Files are staged within a new CPU Colab session; original files remain read-only.
files={
 'run_colab.py':base.parent/'site_stage_test/run_colab.py',
 'sens2/cached_source.py':root/'cached_source.py',
 'sens2/qc_noq3_colab.py':root/'qc_noq3_colab.py',
 'sens2/source_stage.tar':root/'source_stage.tar',
 'sens2/selected_keys.json':root/'selected_keys.json',
 'sens2/tacc_raw_receipts.jsonl':prior/'tacc_raw_receipts.jsonl',
 'sens2/final2_qc.json':prior/'final2_qc.json',
 'sens2/final2_station_params.csv':base/'final2/station_params.csv',
 'sens2/static_gates.csv':prior/'static_gates.csv',
 'sens2/station_admission.csv':prior/'station_admission.csv',
 'sens2/era_seasons.jsonl':prior/'era_seasons.jsonl',
 'sens2/merge_colab.py':prior/'merge_colab.py',
 'sens2/score_sens_colab_final.py':prior/'score_sens_colab_final.py',
 'sens2/gev_sens_colab_final.py':prior/'gev_sens_colab_final.py',
 'sens2/derive_colab.py':prior/'derive_colab.py',
}
assert all(p.is_file() for p in files.values())
with tarfile.open(root/'bundle.tar','w') as t:
    for arc,p in files.items():t.add(p,arcname=arc)
print('BUNDLE', (root/'bundle.tar').stat().st_size, sorted(files))
