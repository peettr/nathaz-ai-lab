#!/usr/bin/env python3
from pathlib import Path
root=Path(__file__).parent
src=root/'run_gate_v1c_recovery.py'; dst=root/'run_gate_v1d.py'
assert not dst.exists()
s=src.read_text()
s=s.replace('envcheck_gc37x_v1c','envcheck_gc37x_v1d').replace('VALIDITY_GATE_v1c_raw_recovery_20261128.json','VALIDITY_GATE_v1d_raw_20261128.json')
s=s.replace("data[f].tobytes() for f in m.FIELDS)+slabs['SOILHGT',200100].tobytes()", "data[f].tobytes() for f in m.FIELDS)+b''.join(slabs[f,200100].tobytes() for f in ('SOILHGT','UU','VV'))")
s=s.replace("float(slabs['SOILHGT',200100][j]),events)", "float(slabs['SOILHGT',200100][j]),events,surface_wind=(slabs['UU',200100][j],slabs['VV',200100][j]))")
s=s.replace("soil,events)", "soil,events,surface_wind=(fields['UU',200100][0],fields['VV',200100][0]))")
s=s.replace("'删失（坏剖面）':0}", "'删失（坏剖面）':0,'饱和气块删失':0}")
s=s.replace("total['其他越界/插值告警删失']+=int('warning' in str(e).lower())", "total['其他越界/插值告警删失']+=int('warning' in str(e).lower())\n                if 'warning' in str(e).lower() and 'Td_K' in str(e):\n                    import ast\n                    try:\n                        parcel=ast.literal_eval(str(e).split('; ',1)[1]); total['饱和气块删失']+=int(parcel['Td_K']>=parcel['T_K'])\n                    except (ValueError,IndexError,SyntaxError,KeyError): pass")
s=s.replace("out['t0'].append(entry)", "out['t0'].append(entry)")
s=s.replace("output=E/'VALIDITY_GATE_v1d_raw_20261128.json'", "out['saturated_per_file']=[{'cycle':v['cycle'],'source':arm,'count':v['counts'][i]['饱和气块删失'],'grid_count':v['grid_count'],'fraction':v['counts'][i]['饱和气块删失']/v['grid_count']} for v in out['t0'] for i,arm in enumerate(('AI','GFS'))]\noutput=E/'VALIDITY_GATE_v1d_raw_20261128.json'")
assert s!=src.read_text();dst.write_text(s)
print(dst)
