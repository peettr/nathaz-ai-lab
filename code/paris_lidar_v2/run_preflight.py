import sys
sys.path.insert(0,'/content/paris_a1_v2')
import run_verify as v
obs,fc,stations=v.load()
print('LOAD_OK',len(obs),len(fc),stations.to_dict('records'),flush=True)
s=fc[fc.source=='GFS'].iloc[0]
print('FIRST_GFS',s[['fc_u','fc_v','fc_u100','fc_v100']].to_dict(),flush=True)
print('OBS_MONTH',obs[obs.station=='PALUPD'].groupby([obs.valid_utc.dt.strftime('%Y-%m'),'target_agl']).size().to_dict(),flush=True)
