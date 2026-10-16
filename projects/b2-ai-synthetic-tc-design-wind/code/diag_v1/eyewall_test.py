"""Paired observed-node H08 static eyewall test with pdelta=1010-Pc and zero tendency/translation."""
import csv,numpy as np,json,pathlib
P=pathlib.Path(__file__).resolve().parent
r=[x for x in csv.DictReader(open(P/'obs_inputs.csv')) if int(x['vmax'])>=114 and x['pc']!='' and x['rmw']!='']
v=np.array([float(x['vmax']) for x in r]);la=np.array([float(x['lat']) for x in r]);pc=np.array([float(x['pc']) for x in r]);pr=1030.222-.730*v
def h08_static(p):
 dp=np.maximum(0,1010-p);b=np.clip(-4.4e-5*dp**2+.01*dp-.014*np.abs(la)+1,.81,2.025)
 rad=np.array([float(x['rmw']) for x in r])*1852
 cp=2*7.29e-5*np.sin(np.radians(la));centr=rad*cp/2
 return np.sqrt(b*dp*100/(1.15*np.e)+centr**2)-centr
actual=h08_static(pc);linear=h08_static(pr);ratio=linear/actual-1
result=dict(n=len(r),vmax_range=[v.min(),v.max()],obs_pc_median=float(np.median(pc)),raft_pc_median=float(np.median(pr)),pc_bias_median=float(np.median(pr-pc)),loss_pct_median=float(-100*np.median(ratio)),loss_pct_q10_q90=(-100*np.quantile(ratio,[.9,.1])).tolist(),fraction_loss_10_15=float(np.mean((-ratio>=.10)&(-ratio<=.15))))
(P/'eyewall_test.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
