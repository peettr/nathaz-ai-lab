#!/usr/bin/env python3.10
"""Frozen T5 paired metrics on host-verified 80-point JSONs."""
import pathlib,json,csv,math,hashlib
R=pathlib.Path(__file__).resolve().parent;E=R/'evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 widths={int(x['id']):x for x in csv.DictReader((R/'widths.csv').open())};assert len(widths)==80
 near=(50,51,52,54,55,74);out={'definition':{'MAE':'mean|Su/Uref-obs| over 80','delta_mae':'MAE(on)-MAE(off), paired seed','delta_r_wide':'mean[(Su_on/Uref)/obs-(Su_off/Uref)/obs], width_min_m>=15m (64)','ratio_total':'sum(Su/Uref)/sum(obs)','FAC2':'fraction with 0.5<=prediction/observation<=2','near_ids':near},'seeds':{}}
 for seed in (101,102):
  rows={};metrics={}
  for mode in ('off','on'):
   label=f'E_s{seed}_{mode}';p=E/f'{label}_points80.json';h=sha(p)
   assert (E/f'{label}_points80.json.sha256').read_text().strip()==h
   d=json.loads(p.read_text());assert d['label']==label and d['uref']==3.9286416 and len(d['rows'])==80
   rows[mode]={int(r['id']):r for r in d['rows']};assert set(rows[mode])==set(range(1,81))
   rr=rows[mode];assert all(math.isfinite(x['Su_ratio']) and math.isfinite(x['obs']) and x['obs']>0 for x in rr.values())
   metrics[mode]={'MAE':sum(abs(x['Su_ratio']-x['obs']) for x in rr.values())/80,'ratio_total':sum(x['Su_ratio'] for x in rr.values())/sum(x['obs'] for x in rr.values()),'FAC2':sum(.5<=x['Su_ratio']/x['obs']<=2 for x in rr.values())/80,'points80_sha256':h,'points80_path':str(p)}
  a,b=rows['off'],rows['on'];assert all(a[i]['obs']==b[i]['obs'] and a[i]['xyz_m']==b[i]['xyz_m'] for i in a)
  wide=[i for i in a if widths[i]['width_min_m']!='' and float(widths[i]['width_min_m'])>=15.];assert len(wide)==64
  delta=metrics['on']['MAE']-metrics['off']['MAE'];dw=sum((b[i]['Su_ratio']-a[i]['Su_ratio'])/a[i]['obs'] for i in wide)/64
  out['seeds'][str(seed)]={'off':metrics['off'],'on':metrics['on'],'delta_mae':delta,'wide_delta_r':dw,'near_points':[{ 'id':i,'obs':a[i]['obs'],'off':a[i]['Su_ratio'],'on':b[i]['Su_ratio'],'wall_m':float(widths[i]['wall_m']),'off_solid_weight':a[i]['solid_weight'],'on_solid_weight':b[i]['solid_weight']} for i in near]}
 ds=[v['delta_mae'] for v in out['seeds'].values()]
 out['verdict']='改善' if all(d<=-.01 for d in ds) else '变差' if all(d>=.01 for d in ds) else '在种子变化内' if all(abs(d)<.01 for d in ds) else '不判'
 p=R/'T5_verdict.json';assert not p.exists();p.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
