import pathlib, subprocess, os
r=pathlib.Path('/content/r234c_gc37_E2E3')
print('root',r.exists())
for name in ['infer_crc_inputs_resume_v3.log','infer_crc_inputs_resume_v3.done','infer_crc_inputs_resume_v3.failed','weights.log','infer_crc_inputs_v2.log','infer_crc_inputs_v2.done','infer_crc_inputs_v2.failed','infer_crc_inputs.done','infer_crc_inputs.failed','INPUT_NETCDF_MANIFEST.json','INPUT_NUMERIC_GATE_E2E3_CRC_V2_SUMMARY.json']:
 p=r/name
 print(name,p.exists(),p.stat().st_size if p.exists() else '')
 if (name.endswith('.log') or name.endswith('.failed')) and p.exists(): print(p.read_text()[-1600:])
print('processes')
subprocess.run(['ps','-eo','pid,etime,args'],check=False)
