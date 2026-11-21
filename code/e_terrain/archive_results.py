from pathlib import Path
import zipfile
r=Path('/content/e_terrain');d=r/'analysis_v1'
files=[d/x for x in ['wn_errors.json','strong_mae_by_terrain.png','metrics.json','full_metrics_baselines.csv','paired_strong_cases.csv','mos_coefficients.csv','strong_metrics.csv']]+[r/'analysis.log',r/'full_forecast.log']
with zipfile.ZipFile(r/'analysis_results.zip','x',zipfile.ZIP_DEFLATED) as z:
 for p in files:z.write(p,p.name)
print('ARCHIVED',len(files),[(p.name,p.stat().st_size) for p in files])
