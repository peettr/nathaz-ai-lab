"""Materialize versioned v3 scripts from vetted v2, without modifying v2."""
from pathlib import Path
base=Path('./23_AI_Weather/06_Logs/k_gc37_preflight')
out=Path(__file__).resolve().parent
assert not any((out/n).exists() for n in ('run_gc37_raw_v3.py','infer_gc37_v3.py','stage_gc37_weights_v3.py','build_gc37_wps_crc_cpu_v3.py','transfer_gc37_cycle_v3.py'))
s=(base/'run_gc37_raw_v2.py').read_text().replace('r234c_gc37_v2','r234c_gc37_v3')
s=s.replace("arr['reg_mean_sea_level_pressure']=", "arr['reg_2m_temperature']=np.asarray(reg['2m_temperature'].values).squeeze().astype('float32')\n   arr['reg_10m_u_component_of_wind']=np.asarray(reg['10m_u_component_of_wind'].values).squeeze().astype('float32')\n   arr['reg_10m_v_component_of_wind']=np.asarray(reg['10m_v_component_of_wind'].values).squeeze().astype('float32')\n   arr['reg_mean_sea_level_pressure']=")
(out/'run_gc37_raw_v3.py').write_text(s)
s=(base/'infer_gc37_v2.py').read_text().replace('v2','v3')
(out/'infer_gc37_v3.py').write_text(s)
s=(base/'stage_gc37_weights_v2.py').read_text().replace('r234c_gc37_v2','r234c_gc37_v3')
(out/'stage_gc37_weights_v3.py').write_text(s)
s=(base/'build_gc37_wps_crc_cpu_v2.py').read_text().replace('drivers_gc37_v2','drivers_gc37_v3').replace('gc37_raw_v2','gc37_raw_v3')
s=s.replace("gsurf={k:v for k,v in soil.items() if k[0] in ('TT','UU','VV')}","gsurf={k:v for k,v in soil.items() if k[0] in ('TT','UU','VV')} if step==0 else {k:(get(g,short),'K' if short=='2t' else 'm s-1','GFS forecast '+short) for k,short in [(('TT',200100),'2t'),(('UU',200100),'10u'),(('VV',200100),'10v')]}")
s=s.replace("asurf={k:v for k,v in gsurf.items() if k[0]!='PMSL'}", "asurf={('TT',200100):(z['reg_2m_temperature'].astype('float32'),'K','GraphCast forecast 2t'),('UU',200100):(z['reg_10m_u_component_of_wind'].astype('float32'),'m s-1','GraphCast forecast 10u'),('VV',200100):(z['reg_10m_v_component_of_wind'].astype('float32'),'m s-1','GraphCast forecast 10v')}\n    # The corresponding near-surface fields differ intentionally; terrain, land, soil, snow and skin remain frozen.")
s=s.replace("   # Same-cycle GFS f000 near-surface fields, but model-predicted MSLP.\n   asurf", "   # Use own predicted near-surface fields and MSLP.\n   with np.load(f) as z:\n    asurf")
# Avoid opening the forecast NPZ twice for otherwise identical extraction.
(out/'build_gc37_wps_crc_cpu_v3.py').write_text(s)
s=(base/'transfer_gc37_cycle_v2.py').read_text().replace('v2','v3')
(out/'transfer_gc37_cycle_v3.py').write_text(s)
print('created',*[str(p) for p in sorted(out.glob('*_v3.py'))],sep='\n')
