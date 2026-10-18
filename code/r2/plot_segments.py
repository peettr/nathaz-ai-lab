"""Small sourced comparison figure for the frozen ensemble verdict."""
import csv,pathlib,statistics
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=pathlib.Path(__file__).parent;rows=list(csv.DictReader((R/'segment_a_20261015/final_score/scores.csv').open()))
leads=(1,2,3);events={lead:[x for x in rows if x['lead_h']==str(lead) and x['group']!='control'] for lead in leads}
fig,axs=plt.subplots(1,2,figsize=(10,4.4))
for label,key,style in [('StormCast gust proxy','wide_ai_obs_ratio','o-'),('HRRR GUST','wide_hrrr_gust_obs_ratio','s-'),('HRRR 10m x same factor','wide_hrrr10_xcoef_obs_ratio','^-')]:
 axs[0].plot(leads,[statistics.median(float(x[key]) for x in events[t]) for t in leads],style,label=label)
axs[0].set(xlabel='Lead (h)',ylabel='Median forecast / observed gust',xticks=leads,title='25 km, +/-1 h | 20 events');axs[0].grid(alpha=.3);axs[0].legend(fontsize=8)
for label,key,style in [('StormCast P>=0.3','wide_ai_hit','o-'),('HRRR GUST','wide_hrrr_hit','s-')]:
 axs[1].plot(leads,[sum(int(x[key]) for x in events[t]) for t in leads],style,label=label)
axs[1].set(xlabel='Lead (h)',ylabel='Hits at >=25.7 m/s (of 20)',xticks=leads,ylim=(0,20),title='20 events; 10 controls: both 0 false alarms');axs[1].grid(alpha=.3);axs[1].legend(fontsize=8)
fig.text(.5,.01,'Sources: NOAA HRRR / Storm Events, IEM ASOS; NVIDIA StormCast V1; ARCO-ERA5.\nGust proxy = 10 m speed x 1.6677 (2022 fit); retrospective ERA5, not operational.',ha='center',fontsize=8)
fig.tight_layout(rect=[0,.11,1,1]);target=R/'segment_a_20261015/v1_verdict.png';assert not target.exists();fig.savefig(target,dpi=170);print(target)
