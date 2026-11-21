from pathlib import Path
import tarfile, hashlib
r=Path('/content/r234c_gc37_E2E3')
out=r/'E2E3_six_cycle_small_1115.tar.gz'
assert (r/'infer_crc_inputs_resume_v3.done').exists() and not out.exists()
with tarfile.open(out,'w:gz') as tar:
 for name in ['infer_crc_inputs_resume_v3.log','infer_crc_inputs_resume_v3.done','INPUT_NETCDF_MANIFEST.json','INPUT_NUMERIC_GATE_E2E3_CRC_V2_SUMMARY.json']:
  tar.add(r/name,arcname=name)
 for d in sorted(r.glob('forecast_*')):
  for p in d.glob('*.json'): tar.add(p,arcname=d.name+'/'+p.name)
 for p in sorted(r.glob('infer_20*.log')):tar.add(p,arcname=p.name)
with out.open('rb') as f:print(out,out.stat().st_size,hashlib.file_digest(f,'sha256').hexdigest())
