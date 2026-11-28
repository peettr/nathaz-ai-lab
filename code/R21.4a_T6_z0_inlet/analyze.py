#!/usr/bin/env python3.10
"""T6 frozen same-seed metrics against host-verified T5 off/on files."""
import pathlib,json,csv,hashlib,math
R=pathlib.Path(__file__).resolve().parent;E=R/'evidence'; L=R.parent
sources={('101','off'):L/'R21.4a_T5_caseE_WM_retry1/evidence',('102','off'):L/'R21.4a_T5_caseE_WM_retry2/evidence',('101','t5on'):L/'R21.4a_T5_caseE_WM_retry1/evidence',('102','t5on'):L/'R21.4a_T5_caseE_WM/evidence',('101','t6on'):E,('102','t6on'):E}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 widths={int(x['id']):x for x in csv.DictReader((R/'widths.csv').open())};assert len(widths)==80
 out={'definition':{'delta_mae':'MAE(T6 enabled)-MAE(T5 disabled), paired seed','t6_minus_t5on_mae':'MAE(T6 enabled)-MAE(T5 enabled)','MAE':'mean|Su/Uref-obs| over 80','wide_delta_r':'mean[T6_ratio/obs-T5off_ratio/obs] for width_min_m>=15m, N=64','ratio_total':'sum(Su/Uref)/sum(obs)','FAC2':'fraction with 0.5<=prediction/observation<=2'},'seeds':{}}
 for s in ('101','102'):
  rows={};metrics={}
  for mode in ('off','t5on','t6on'):
   label=f'E_s{s}_{"off" if mode=="off" else "on"}';folder=sources[(s,mode)];p=folder/f'{label}_points80.json'
   h=sha(p);assert (folder/f'{label}_points80.json.sha256').read_text().strip()==h
   d=json.loads(p.read_text());assert d['label']==label and d['uref']==3.9286416 and len(d['rows'])==80
   rows[mode]={int(x['id']):x for x in d['rows']};assert set(rows[mode])==set(range(1,81))
   rr=rows[mode];assert all(math.isfinite(x['Su_ratio']) and x['obs']>0 for x in rr.values())
   metrics[mode]={'MAE':sum(abs(x['Su_ratio']-x['obs']) for x in rr.values())/80,'ratio_total':sum(x['Su_ratio'] for x in rr.values())/sum(x['obs'] for x in rr.values()),'FAC2':sum(.5<=x['Su_ratio']/x['obs']<=2 for x in rr.values())/80,'points80_sha256':h,'points80_path':str(p)}
  a,b,c=rows['off'],rows['t5on'],rows['t6on'];assert all(a[i]['obs']==b[i]['obs']==c[i]['obs'] and a[i]['xyz_m']==b[i]['xyz_m']==c[i]['xyz_m'] for i in a)
  wide=[i for i in a if widths[i]['width_min_m'] and float(widths[i]['width_min_m'])>=15.];assert len(wide)==64
  out['seeds'][s]={**metrics,'delta_mae':metrics['t6on']['MAE']-metrics['off']['MAE'],'t6_minus_t5on_mae':metrics['t6on']['MAE']-metrics['t5on']['MAE'],'wide_delta_r':sum((c[i]['Su_ratio']-a[i]['Su_ratio'])/a[i]['obs'] for i in wide)/64,'near_points':[{'id':i,'obs':a[i]['obs'],'off':a[i]['Su_ratio'],'t5on':b[i]['Su_ratio'],'t6on':c[i]['Su_ratio'],'wall_m':float(widths[i]['wall_m']),'t6_solid_weight':c[i]['solid_weight']} for i in (50,51,52,54,55,74)]}
 ds=[v['delta_mae'] for v in out['seeds'].values()]
 out['verdict']='改善' if all(d<=-.01 for d in ds) else '变差' if all(d>=.01 for d in ds) else '在种子变化内' if all(abs(d)<.01 for d in ds) else '不判'
 p=R/'T6_verdict.json';assert not p.exists();p.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
