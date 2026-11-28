from pathlib import Path
p=Path('./23_AI_Weather/06_Logs/ai_climate_emulator')
out=p/'site_stage_qc/sens_q3pk'
s=(p/'site_stage_qc/qc_final2_colab.py').read_text()
s=s.replace("'/content/site_stage_qc/final2'","'/content/sens'")
s=s.replace("import run_colab as core","import run_colab as core\nimport cached_source; cached_source.setup(core,ROOT)" ) if False else s
# Insert override after ROOT is defined and imports are available.
s=s.replace("ROOT=Path('/content/sens');ROOT.mkdir(exist_ok=True)","ROOT=Path('/content/sens');ROOT.mkdir(exist_ok=True)\nimport cached_source; cached_source.setup(core,ROOT)")
s=s.replace("for y in range(2007,2022):\n  try:","for y in range(2007,2022):\n  if (st,y) not in cached_source.KEYS:continue\n  try:")
s=s.replace("if sust is not None and v-sust>40:rules.append('Q3')","if c['source']=='gust' and sust is not None and v-sust>40:rules.append('Q3')")
s=s.replace("assert sum(1 for _ in out.open())==435","assert sum(1 for _ in out.open())==len(cached_source.KEYS)")
s=s.replace("'rows':435","'rows':len(cached_source.KEYS)")
# q5 uses archived response when available, and fetches only previously uncached candidate dates.
s=s.replace("with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'PETW-station-QC/1.0'}),timeout=60) as z:raw=z.read()","raw=cached_source.isd_response(url)")
(out/'qc_sens_colab.py').write_text(s)
for old,new in [('final2_score_corrected_colab.py','score_sens_colab.py'),('final2_gev_corrected_colab.py','gev_sens_colab.py')]:
 s=(p/'site_stage_qc'/old).read_text().replace("'/content/site_stage_qc/final2'","'/content/sens'")
 (out/new).write_text(s)
print('generated')
