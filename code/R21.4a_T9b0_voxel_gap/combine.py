#!/usr/bin/env python3.10
"""Combine two native neighboring planes at exact between-plane sample heights."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from voxel_gap import sources

IDS=(31,39,40,47,48,49,50,51,52,55,65,66,69,74,77,79)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    a=argparse.ArgumentParser();a.add_argument('--coarse',required=True);a.add_argument('--fine',required=True);a.add_argument('--points',required=True);a.add_argument('--widths',required=True);a.add_argument('--out',required=True);arg=a.parse_args()
    c=json.loads(Path(arg.coarse).read_text());f=json.loads(Path(arg.fine).read_text())
    provenance={q['id']:q for q in sources(arg.points,arg.widths)}
    assert len(c['entries'])==len(f['entries'])==32
    by=lambda d,id:sorted((q for q in d['entries'] if q['id']==id),key=lambda q:q['k'])
    rows=[];far=[]
    for id in IDS:
        x,y=by(c,id),by(f,id)
        assert len(x)==len(y)==2 and x[1]['k']==x[0]['k']+1 and y[1]['k']==y[0]['k']+1
        assert x[0]['axis']==y[0]['axis'] and x[0]['width_min_m']==y[0]['width_min_m']
        assert x[0]['xyz_m'][2]==2.5 and y[0]['xyz_m'][2]==2.25
        p=provenance[id]
        assert p['axis']==x[0]['axis'] and p['width_min_m']==x[0]['width_min_m']
        # Measurement labels 2.5/2.25 lie halfway between native planes.
        # Use the lower plane deterministically; retain upper plane and mark disagreements.
        agree_c=x[0]['channel_width_m']==x[1]['channel_width_m'];agree_f=y[0]['channel_width_m']==y[1]['channel_width_m']
        narrowed=lambda c,h:c['narrowing_m']>=1 and h['narrowing_m']<1
        d={'id':id,'width_min_m':x[0]['width_min_m'],'direction':x[0]['axis'],
           'wall_m':p['wall_m'],'obs':p['obs'],'delta_ri':p['delta_ri'],
           'one_m_native_planes':x,'half_m_native_planes':y,
           'one_m_width_m':x[0]['channel_width_m'],
           'half_m_width_m':y[0]['channel_width_m'],
           'one_m_narrowing_m':x[0]['narrowing_m'],
           'half_m_narrowing_m':y[0]['narrowing_m'],
           'voxel_narrowed':narrowed(x[0],y[0]),
           'blocked':x[0]['blocked_le_1_cell'],
           'upper_plane_voxel_narrowed':narrowed(x[1],y[1]),
           'upper_plane_blocked':x[1]['blocked_le_1_cell'],
           'plane_agreement':{'one_m':agree_c,'half_m':agree_f},
           'height_ambiguity':not(agree_c and agree_f)}
        rows.append(d)
        if p['wall_m']>=1:far.append({'id':id,'one_m_width_m':d['one_m_width_m'],'one_m_width_planes_m':[q['channel_width_m'] for q in x],'delta_ri':p['delta_ri']})
    assert len(far)==11
    out=Path(arg.out);assert not out.exists()
    out.write_text(json.dumps({'sources':{'coarse':{'path':arg.coarse,'sha256':sha(arg.coarse)},'fine':{'path':arg.fine,'sha256':sha(arg.fine)},'points':{'path':arg.points,'sha256':sha(arg.points)},'widths':{'path':arg.widths,'sha256':sha(arg.widths)}},'rows':rows,'far11_width_delta_ri':far},indent=2)+'\n')
    print('COMBINE_DONE',len(rows),sha(out))
if __name__=='__main__':main()
