"""Replot verified summary with reserved footer room; leave first figure intact."""
import json,pathlib
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=pathlib.Path(__file__).parent;stats=json.loads((R/'summary.json').read_text())
ks=['MUCAPE','MLCAPE','DCAPE','shear06','shear01'];models=['PANG','GRAP']
fig,axs=plt.subplots(5,2,figsize=(12,16));fig.subplots_adjust(bottom=.065,top=.97,hspace=.57,wspace=.3)
for i,k in enumerate(ks):
 for j,m in enumerate(models):
  a=axs[i,j];rr=sorted((x for x in stats if x['model']==m and x['parameter']==k),key=lambda x:x['lead_h'])
  a.plot([x['lead_h'] for x in rr],[x['median_ai_ae'] for x in rr],'-o',label='AIWP GFS')
  a.plot([x['lead_h'] for x in rr],[x['median_p_ae'] for x in rr],'--s',label='ERA5 persistence')
  a.set(xlabel='Lead (h)',ylabel=f'Median AE ({"J/kg" if i<3 else "m/s"})',title=f'{m} {k}')
  a.legend(fontsize=8)
fig.text(.5,.022,'Sources: NOAA-CIRA AWS AIWP GFS reforecasts; Google ARCO-ERA5 (13 pressure levels); NOAA NCEI Storm Events ASOS.',ha='center',fontsize=8)
fig.savefig(R/'errors_by_parameter_sources_v2.png',dpi=150)
