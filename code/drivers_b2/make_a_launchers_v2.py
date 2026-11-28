#!/usr/bin/env python3
"""Produce immutable B2 budget-v2 A launchers, no scheduler operation."""
from pathlib import Path
import hashlib
here=Path(__file__).resolve().parent
src=here/'a_launchers_v1'
out=here/'a_launchers_v2';out.mkdir(exist_ok=True)
for event in ('N8','N9','N10'):
 name=f'submit_{event}_72h_A_v1.sh'
 s=(src/name).read_text()
 s=s.replace(f'ops_{event}_72h_A_v1',f'ops_{event}_72h_A_v2').replace('run_crc_inputs_b1.py','run_crc_inputs_b2_v2.py')
 assert 'ops_'+event+'_72h_A_v2' in s and 'run_crc_inputs_b2_v2.py' in s
 p=out/name.replace('_v1.sh','_v2.sh')
 if p.exists():assert p.read_text()==s
 else:p.write_text(s)
 print(p,hashlib.sha256(s.encode()).hexdigest())
