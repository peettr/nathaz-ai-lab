#!/usr/bin/env python3
"""Compare a 1 m seed-only run to immutable T1c4 at equal wall height."""
import csv, json, pathlib, math
import post_t2 as m
R=pathlib.Path(__file__).resolve().parent
REF=pathlib.Path('/scratch/04448/[用户]/r24_luw/T1c4_4gpu_B2u/case_4gpu/RESULTS/vtk/20251222120000_avg-000031000.vtk')
NEW=R/'case_4gpu/RESULTS/vtk/20251222120000_avg-000031000.vtk'
def main():
    assert REF.is_file() and NEW.is_file()
    a=m.vtk_open(REF);b=m.vtk_open(NEW)
    assert a['dims']==b['dims']==(500,500,270)
    assert a['origin']==b['origin']==(0.,0.,-20.) and a['spacing']==b['spacing']==(1.,1.,1.)
    ref=json.loads((R/'B2u_reference_points.json').read_text())
    with (R/'widths.csv').open() as f: widths=list(csv.DictReader(f))
    pts=ref['rows'];assert len(pts)==len(widths)==80
    result={'definition':'delta_r = mean_i[(Su_new/Uref)/obs_i-(Su_B2u/Uref)/obs_i] over width>=15m; same h, horizontal B2u shift (+1,+1)m; ratio_total = sum(Su/Uref)/sum(obs)', 'source_ref':str(REF),'source_new':str(NEW),'uref':ref['uref'],'heights':{}}
    for h in (1.5,2.,2.5):
        base=[];run=[];detailed=[]
        for p in pts:
            old=m.point_sample(a,p,(1.,1.,h+.5-2.))
            new=m.point_sample(b,p,(1.,1.,h+.5-2.))
            o=p['after'];base.append({'id':p['id'],'obs':o,'Su':old['Su']/ref['uref']})
            run.append({'id':p['id'],'obs':o,'Su_ratio':new['Su']/ref['uref'],'fluid_corners':new['fluid_corners'],'solid_weight':new['solid_weight']})
            detailed.append({'id':p['id'],'old':old,'new':new,'obs':o})
        tab=m.table(run,base,widths)
        result['heights'][str(h)]={'label_z_m':h+.5,'table':tab,'points':detailed}
        print('T2D_HEIGHT',h,'WIDE_DELTA_R',tab['groups']['>=15']['delta_r'],'DELTA_MAE',tab['delta_mae'],flush=True)
    (R/'result.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
